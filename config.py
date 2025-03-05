# config.py
import os
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv()  # Load variables from .env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
CHATMODEL="gpt-4o"
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS"))
THRESHOLD_QUERY_SEARCH = 0.45 # Threshold of the cosine simialrity of the search
TOP_QUERY_RESULT= 10 # Number of query retiriveted at once
LIMIT=10000 # Limit of request per day
AUSLEGAL_DOCUMENT_PATH = os.getenv("AUSLEGAL_DOCUMENT_PATH")
USCON_DOCUMENT_PATH = os.getenv("USCON_DOCUMENT_PATH") 
DB_NAME = "ai_rag_db"
QUERY_COLLECTION_NAME = "User_queries"
  # For Dataset
COLLECTION = {
    "US_CONSTITUTION_SET": {
        "db_name": DB_NAME ,
        "query_collection_name": QUERY_COLLECTION_NAME,
        "embedding_collection_name": "us_constitution_embedding",
        "annoy_collection_name": "us_constitution_annoy",
        "annoy_index_path": "./annoy/usc.ann",
        "id_map_path": "./annoy/usc_id_map.pkl",
        "document_type": "US Constitution",  # Type of the document
        "unique_index": "title"
    },
    "AUS_LAW_SET": {
        "db_name": DB_NAME,
        "query_collection_name": QUERY_COLLECTION_NAME,
        "embedding_collection_name": "Australian_Law_2024_embedding",
        "annoy_collection_name": "Australian_Law_2024_annoy",
        "annoy_index_path": "./annoy/auslaw.ann",
        "id_map_path": "./annoy/aus_id_map.pkl",
        "document_type": "Australia Laws 2024",  # Type of the document
        "unique_index": "version_id"
    }
}