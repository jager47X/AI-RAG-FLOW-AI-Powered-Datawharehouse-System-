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
    For each document in the corpus (as specified in config) that lacks an 'embedding' field,
    compute the embedding using OpenAI and update the document using the unique field provided in the config.
    """
    logger.info("Connecting to the database...")
    with MongoClient(MONGO_URI) as client:
        db = client[config["db_name"]]
        embedding_collection = db[config["embedding_collection_name"]]
        logger.info("Connected to the database.")
        logger.info("Counting the number of the documents to add embeddings.")
        # Count documents missing an embedding.
        count_docs = embedding_collection.count_documents({"embedding": {"$exists": False}})
        logger.info("Number of documents to add embeddings: %d", count_docs)
        logger.info("Counting the number of the documents to add embeddings.")
        docs = embedding_collection.find({"embedding": {"$exists": False}})
        unique_field = config.get("unique_index", "title")  # default to "title"

        openAI_Embeddings=ChatGPT(db)
        for doc in docs:
            text = doc.get("text", "").strip()
            if text:
                embedding = openAI_Embeddings.get_openai_embedding(text)
                embedding_list = embedding.tolist() if hasattr(embedding, "tolist") else embedding

                # Update using the unique field from the configuration.
                embedding_collection.update_one(
                    {unique_field: doc[unique_field]},
                    {"$set": {"embedding": embedding_list}}
                )
                logger.info("Updated embedding for document with %s: %s", unique_field, doc.get(unique_field))
    logger.info("Database connection closed.")

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
