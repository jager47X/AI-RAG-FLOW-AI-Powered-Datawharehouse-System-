import json
from pymongo import MongoClient
from config import MONGO_URI, JSONL_PATH

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

def ingest_jsonl_to_mongodb(skip_lines=0):
    client = MongoClient(MONGO_URI)
    db = client['rag_db']
    corpus_collection = db['corpus']

    processed = 0
    skipped = 0
    duplicates = 0

    print("Starting ingestion of JSONL data into MongoDB...")

    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for _ in range(skip_lines):
            skipped += 1
            next(f, None)  # Skip the specified number of lines

        for line in f:
            try:
                doc = parse_jsonl_line(line)
                unique_id = doc.get("version_id")

                if not unique_id:
                    print("Skipping document: 'version_id' is missing.")
                    skipped += 1
                    continue

                # Check if the document already exists
                existing_doc = corpus_collection.find_one({"version_id": unique_id})
                if existing_doc:
                    print(f"Skipping duplicate document: version_id = {unique_id}")
                    duplicates += 1
                    continue

                # Insert new document if it does not exist
                corpus_collection.insert_one(doc)
                processed += 1
                print(f"Ingested document {processed}: version_id = {unique_id}")

            except Exception as e:
                skipped += 1
                print(f"Skipping invalid JSON line (Total Skipped: {skipped}): {line.strip()}\nError: {e}")

    print("JSONL data ingestion complete.")
    print(f"Processed: {processed} new documents.")
    print(f"Skipped: {skipped} invalid or pre-skipped lines.")
    print(f"Duplicates: {duplicates} already existed and were not inserted.")
    
    client.close()

if __name__ == "__main__":
    num_skip = int(input("Enter the number of lines to skip before ingestion starts: "))
    ingest_jsonl_to_mongodb(skip_lines=num_skip)
