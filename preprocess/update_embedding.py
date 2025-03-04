import json
import logging
from pymongo import MongoClient
import openai
import tiktoken  # pip install tiktoken
from config import MONGO_URI, EMBEDDING_MODEL, COLLECTION
import datetime
from openai_service import ChatGPT

# Global constant for max tokens.
MAX_TOTAL_TOKENS = 8000

# Configure logging.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def update_corpus_embeddings(config):
    """
    For each document in the corpus (as specified in config),
    compute the embedding using OpenAI and update the document.
    The user is prompted to choose whether to resume processing documents
    that lack an 'embedding' field, or reprocess all documents.
    """
    logger.info("Connecting to the database...")

    with MongoClient(MONGO_URI) as client:
        db = client[config["db_name"]]
        embedding_collection = db[config["embedding_collection_name"]]
        logger.info("Connected to the database.")
        total_count = embedding_collection.count_documents({})

        count_missing = embedding_collection.count_documents({"embedding": {"$exists": False}})
        logger.info(f"Total documents in collection: {total_count}")
        logger.info(f"Documents missing embeddings: {count_missing}")

        # Prompt user to choose processing mode.
        logger.info("Choose processing mode:")
        logger.info("  [c] Continue processing missing embeddings only")
        logger.info("  [b] Start from beginning (process all documents)")
        mode = input("Enter your choice (c/b): ").strip().lower()

        if mode not in ['c', 'b']:
            logger.warning("Invalid input. Defaulting to 'continue' mode.")
            mode = 'c'

        if mode == 'c':
            docs = embedding_collection.find({"embedding": {"$exists": False}})
            # We'll update the running count based on only the new embeddings.
            processed = total_count - count_missing
        else:  # mode == 'b'
            docs = embedding_collection.find({})
            # Optionally, you might want to remove the existing embeddings.
            result = embedding_collection.update_many({}, {"$unset": {"embedding": ""}})
            logger.info("Removed existing embeddings from %d documents.", result.modified_count)
            processed = 0  # starting fresh

        logger.info("Starting embedding update...")

        openAI_Embeddings = ChatGPT(db, preprocess=True)

        # Confirm with the user before starting.
        user_input = input("Proceed with embedding update? (y/n): ").strip().lower()
        if user_input != 'y':
            logger.warning("Skipping embedding update as per user input.")
            return

        for doc in docs:
            text = doc.get("text", "").strip()
            if text:
                try:
                    embedding = openAI_Embeddings.get_openai_embedding(text)
                    # Convert to list if necessary.
                    embedding_list = embedding.tolist() if hasattr(embedding, "tolist") else embedding

                    # Update using the unique field specified in the config.
                    unique_field = config.get("unique_index", "title")  # Default to "title"
                    embedding_collection.update_one(
                        {unique_field: doc[unique_field]},
                        {"$set": {"embedding": embedding_list}}
                    )

                    processed += 1
                    percentage = (processed / total_count) * 100 if total_count > 0 else 100
                    # Log progress every ~1% progress.
                    if processed % max(1, int(total_count / 100)) == 0:
                        logger.info(f"Progress: {percentage:.2f}% completed")

                    logger.debug("Updated embedding for document with %s: %s", unique_field, doc.get(unique_field))

                except Exception as e:
                    logger.error("Error updating embedding for document with %s: %s. Error: %s",
                                 unique_field, doc.get(unique_field), str(e))

        logger.info("Successfully completed embedding updates in the database.")

if __name__ == "__main__":
    # List available configurations.
    keys = list(COLLECTION.keys())
    logger.info("Available configurations:")
    for i, key in enumerate(keys, start=1):
        doc_type = COLLECTION[key].get("document_type", "Unknown")
        logger.info("%d: %s", i, doc_type)

    try:
        selected_num = int(input("Enter configuration number: ").strip())
        if selected_num < 1 or selected_num > len(keys):
            raise ValueError("Selection out of range")
    except Exception as e:
        logger.warning("Invalid configuration number provided. Defaulting to 1.")
        selected_num = 1

    config = COLLECTION[keys[selected_num - 1]]
    logger.info("Using configuration: %s", config["document_type"])
    logger.info("Selected configuration details: %s", json.dumps(config, indent=4))

    update_corpus_embeddings(config)
