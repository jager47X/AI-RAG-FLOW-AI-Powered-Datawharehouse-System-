import os
import json
import logging
from pymongo import MongoClient, WriteConcern, errors
from config import MONGO_URI, AUSLEGAL_DOCUMENT_PATH

# Set a safe maximum for the text field in bytes (15 MB)
SAFE_TEXT_SIZE = 15 * 1024 * 1024  # 15 MB

def binary_split_text(text, max_bytes):
    """
    Splits a text string into chunks such that the UTF-8 encoded
    size of each chunk does not exceed max_bytes.
    Uses binary search to find the maximal substring length.
    """
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        low = start + 1
        high = n
        best = low
        while low <= high:
            mid = (low + high) // 2
            if len(text[start:mid].encode('utf-8')) <= max_bytes:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        chunks.append(text[start:best])
        start = best
    return chunks

def parse_jsonl_line(line):
    """
    Parses a JSONL line and extracts relevant fields.
    """
    try:
        doc = json.loads(line)
    except json.JSONDecodeError as e:
        raise e

    parsed_doc = {
        "version_id": doc.get("version_id"),
        "type": doc.get("type"),
        "jurisdiction": doc.get("jurisdiction"),
        "source": doc.get("source"),
        "citation": doc.get("citation"),
        "url": doc.get("url"),
        "text": doc.get("text")
    }
    return parsed_doc

def ingest_jsonl_to_mongodb(skip_lines=0, batch_size=1000):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logger = logging.getLogger(__name__)
    
    try:
        client = MongoClient(MONGO_URI)
        db = client['ai_rag_db']
        collection = db.get_collection('Australian_Law_2024_embedding', write_concern=WriteConcern(w=0))
        logger.info("Connected to MongoDB with write concern w=0.")
        
        # Drop all indexes except the default _id index.
        indexes = collection.index_information()
        indexes_to_drop = [name for name in indexes if name != '_id']
        for index in indexes_to_drop:
            collection.drop_index(index)
            logger.info("Dropped index: %s", index)
        
        logger.info("Starting ingestion of JSONL data...")
        
        # Pre-load existing version_ids for duplicate checking.
        existing_ids = set()
        try:
            for doc in collection.find({}, {"version_id": 1, "_id": 0}):
                if 'version_id' in doc:
                    existing_ids.add(doc['version_id'])
            logger.info("Fetched %d existing version_ids.", len(existing_ids))
        except Exception as e:
            logger.error("Error fetching existing version_ids: %s", e)
        
        processed = 0
        skipped = 0
        duplicates = 0
        batch = []
        local_ids = set()  # To track duplicates within this ingestion run.
        
        with open(AUSLEGAL_DOCUMENT_PATH, "r", encoding="utf-8") as f:
            for _ in range(skip_lines):
                next(f, None)
                skipped += 1
                
            for line in f:
                try:
                    doc = parse_jsonl_line(line)
                except Exception as e:
                    logger.warning("Skipping invalid JSON line: %s. Error: %s", line.strip(), e)
                    skipped += 1
                    continue
                
                version_id = doc.get("version_id")
                if not version_id:
                    logger.warning("Skipping document with missing 'version_id'.")
                    skipped += 1
                    continue
                
                # Duplicate check: skip if version_id already exists.
                if version_id in existing_ids or version_id in local_ids:
                    logger.info("Skipping duplicate document: version_id = %s", version_id)
                    duplicates += 1
                    continue
                
                local_ids.add(version_id)
                
                # Check if the text field exceeds the safe size.
                text = doc.get("text", "")
                text_bytes = len(text.encode('utf-8')) if text else 0
                if text and text_bytes > SAFE_TEXT_SIZE:
                    chunks = binary_split_text(text, SAFE_TEXT_SIZE)
                    total_chunks = len(chunks)
                    logger.info("Splitting document version_id %s into %d chunks (text size: %d bytes).",
                                version_id, total_chunks, text_bytes)
                    for idx, chunk in enumerate(chunks):
                        new_doc = doc.copy()
                        new_doc["text"] = chunk
                        new_doc["chunk_index"] = idx
                        new_doc["chunk_total"] = total_chunks
                        batch.append(new_doc)
                else:
                    doc["chunk_index"] = 0
                    doc["chunk_total"] = 1
                    batch.append(doc)
                
                if len(batch) >= batch_size:
                    try:
                        result = collection.insert_many(batch, ordered=False)
                        inserted_count = len(result.inserted_ids)
                        processed += inserted_count
                        logger.info("Inserted batch of %d documents.", inserted_count)
                    except errors.BulkWriteError as bwe:
                        inserted_count = bwe.details.get("nInserted", 0)
                        processed += inserted_count
                        logger.warning("Bulk insert error: inserted %d documents; duplicates may have been skipped.", inserted_count)
                    batch = []
            
            if batch:
                try:
                    result = collection.insert_many(batch, ordered=False)
                    inserted_count = len(result.inserted_ids)
                    processed += inserted_count
                    logger.info("Inserted final batch of %d documents.", inserted_count)
                except errors.BulkWriteError as bwe:
                    inserted_count = bwe.details.get("nInserted", 0)
                    processed += inserted_count
                    logger.warning("Bulk insert error on final batch: inserted %d documents.", inserted_count)
        
        logger.info("JSONL data ingestion complete.")
        logger.info("Processed: %d new documents.", processed)
        logger.info("Skipped: %d invalid or pre-skipped lines.", skipped)
        logger.info("Duplicates: %d documents already existed.", duplicates)
        
        try:
            collection.create_index([("version_id", 1), ("chunk_index", 1)], unique=True)
            logger.info("Re-created compound unique index on ('version_id', 'chunk_index').")
        except Exception as e:
            logger.error("Error re-creating index on ('version_id', 'chunk_index'): %s", e)
        
    except Exception as e:
        logger.error("Error during ingestion: %s", e)
    finally:
        client.close()
        logger.info("MongoDB connection closed.")

if __name__ == "__main__":
    try:
        client = MongoClient(MONGO_URI)
        db = client['ai_rag_db']
        collection = db.get_collection('Australia_Law_2024', write_concern=WriteConcern(w=0))
        num_skip = collection.count_documents({})
        print(f"Detected {num_skip} documents already ingested. Skipping that many lines.")
    except Exception as e:
        print(f"Error retrieving document count: {e}. Starting ingestion from the beginning.")
        num_skip = 0
    finally:
        client.close()

    ingest_jsonl_to_mongodb(skip_lines=num_skip)
