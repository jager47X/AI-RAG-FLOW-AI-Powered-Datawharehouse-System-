import os
import json
import pickle
import logging
import datetime
from pymongo import MongoClient, WriteConcern
from annoy import AnnoyIndex
from config import MONGO_URI, EMBEDDING_DIMENSIONS, COLLECTION

# Configure logging.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Global constants.
VECTOR_SIZE = EMBEDDING_DIMENSIONS
ANNOY_TREE_COUNT = 1000  # Adjust based on desired accuracy

def prebuild_annoy_index(config):
    ANNOY_INDEX_PATH = config["annoy_index_path"]
    ID_MAP_PATH = config["id_map_path"]
    logger.info("ANNOY_INDEX_PATH: %s", ANNOY_INDEX_PATH)
    logger.info("ID_MAP_PATH: %s", ID_MAP_PATH)
    
    client = MongoClient(MONGO_URI)
    db = client[config["db_name"]]
    
    # Use the embedding collection for reading the documents.
    embedding_collection = db[config["embedding_collection_name"]]
    # Use the annoy collection for storing the copied documents.
    annoy_collection = db[config["annoy_collection_name"]]
    
    # Fetch all documents that have embeddings.
    docs = list(embedding_collection.find({"embedding": {"$exists": True}}))
    logger.info("Fetched %d documents with embeddings from '%s'.", len(docs), config["embedding_collection_name"])
    
    # Create Annoy index and build an id mapping.
    index = AnnoyIndex(VECTOR_SIZE, 'angular')
    id_map = {}
    copied_docs = []  # List to hold documents to be inserted into annoy_collection.
    
    for i, doc in enumerate(docs):
        emb = doc.get("embedding")
        if emb is not None:
            index.add_item(i, emb)
            id_map[i] = str(doc["_id"])  # Store original ObjectId as string.
            # Create a new document without the embedding field.
            new_doc = {k: v for k, v in doc.items() if k != "embedding"}
            # Add the "map_id" field.
            new_doc["map_id"] = str(i)
            copied_docs.append(new_doc)
    
    # Ensure the directory for the Annoy index exists.
    index_dir = os.path.dirname(ANNOY_INDEX_PATH)
    if not os.path.exists(index_dir):
        os.makedirs(index_dir)
        logger.info("Created directory for Annoy index: %s", index_dir)
    
    # Build and save the Annoy index.
    index.build(ANNOY_TREE_COUNT)
    index.save(ANNOY_INDEX_PATH)
    logger.info("Annoy index built and saved to %s", ANNOY_INDEX_PATH)
    
    # Save the id mapping to file (as fallback).
    with open(ID_MAP_PATH, "wb") as f:
        pickle.dump(id_map, f)
    logger.info("ID map saved to file: %s", ID_MAP_PATH)
    
    # For the annoy collection, clear previous data to avoid duplicates.
    annoy_collection.delete_many({})
    logger.info("Cleared previous documents from collection '%s'.", config["annoy_collection_name"])
    
    # Insert the copied documents into the annoy collection.
    if copied_docs:
        result = annoy_collection.insert_many(copied_docs, ordered=False)
        logger.info("Inserted %d documents into '%s'.", len(result.inserted_ids), config["annoy_collection_name"])
    else:
        logger.warning("No documents to copy into '%s'.", config["annoy_collection_name"])
    
    client.close()
    logger.info("MongoDB connection closed.")

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
    
    prebuild_annoy_index(config)
