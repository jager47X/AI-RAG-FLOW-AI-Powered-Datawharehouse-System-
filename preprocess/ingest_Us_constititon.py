import os
import json
import logging
from pymongo import MongoClient, WriteConcern
from pymongo.errors import BulkWriteError
from config import MONGO_URI, USCON_DOCUMENT_PATH  # USCON_DOCUMENT_PATH should be the path to your JSON file

# Configure logging at module level.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def load_json_file():
    """Check if the JSON file exists and load it."""
    if not os.path.exists(USCON_DOCUMENT_PATH):
        logger.error("File does not exist: %s", USCON_DOCUMENT_PATH)
        return None

    try:
        with open(USCON_DOCUMENT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.error("Error reading the file: %s", e)
        return None

def ingest_json_to_mongodb():
    """
    Ingest JSON data into MongoDB:
      - Connects with write concern w=0 (for faster writes).
      - Drops non-critical indexes.
      - Loads the JSON file.
      - Extracts the articles.
      - Filters out documents missing 'title'.
      - Filters out documents that would duplicate an existing title.
      - Performs bulk insertion (unordered).
      - Re-creates a unique index on 'title'.
    """
    try:
        # Connect to MongoDB with a write concern of w=0.
        client = MongoClient(MONGO_URI)
        db = client['ai_rag_db']
        collection = db.get_collection('us_constitution_embedding', write_concern=WriteConcern(w=0))
        logger.info("Connected to MongoDB with write concern w=0.")

        # Drop all indexes except the default _id index.
        existing_indexes = collection.index_information()
        indexes_to_drop = [name for name in existing_indexes if name != '_id']
        for index_name in indexes_to_drop:
            collection.drop_index(index_name)
            logger.info("Dropped index: %s", index_name)
        logger.info("Indexes dropped temporarily.")

        # Load the JSON file.
        data = load_json_file()
        if data is None:
            logger.error("No data loaded from JSON file.")
            return

        # Extract articles from the JSON structure.
        articles = data.get("data", {}).get("constitution", {}).get("articles", [])
        if not articles:
            logger.warning("No articles found in the JSON file.")
            return

        # Filter out documents missing 'title'.
        valid_docs = [doc for doc in articles if doc.get("title")]
        initial_count = len(valid_docs)
        logger.info("Found %d documents with a title.", initial_count)
        if initial_count == 0:
            logger.info("No valid documents to insert.")
            return

        # Retrieve the set of titles already in the collection.
        existing_titles = set()
        for doc in collection.find({}, {"title": 1}):
            if "title" in doc:
                existing_titles.add(doc["title"])
        logger.info("Found %d existing titles in the collection.", len(existing_titles))

        # Filter out documents that would be duplicates.
        unique_docs = [doc for doc in valid_docs if doc["title"] not in existing_titles]
        duplicates_count = initial_count - len(unique_docs)
        if duplicates_count > 0:
            logger.warning("Skipped %d documents due to duplicates (based on title).", duplicates_count)
        if not unique_docs:
            logger.info("No new documents to insert after filtering duplicates.")
            return

        # Use insert_many with unordered insertion for better performance.
        try:
            result = collection.insert_many(unique_docs, ordered=False)
            processed = len(result.inserted_ids)
            logger.info("Inserted %d new documents using bulk unordered insert.", processed)
        except BulkWriteError as bwe:
            processed = bwe.details.get("nInserted", 0)
            logger.warning("Bulk insertion encountered errors. Inserted %d documents.", processed)

        # Re-create necessary indexes after ingestion.
        try:
            collection.create_index("title", unique=True)
            logger.info("Re-created unique index on 'title'.")
        except Exception as e:
            logger.error("Error re-creating index on 'title': %s", e)

        logger.info("JSON data ingestion complete.")
        logger.info("Processed: %d new documents.", processed)
        logger.info("Skipped: %d documents with missing 'title' or duplicates.", duplicates_count)
    except Exception as e:
        logger.error("Error during ingestion: %s", e)
    finally:
        client.close()
        logger.info("MongoDB connection closed.")

if __name__ == '__main__':
    ingest_json_to_mongodb()
