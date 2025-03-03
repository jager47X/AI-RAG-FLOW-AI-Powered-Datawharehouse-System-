# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
JSONL_PATH = os.getenv("JSONL_PATH")  # Now points to a JSONL file
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS"))
THRESHOLD_QUERY_SEARCH = 0.40 # Threshold of the cosine simialrity of the search
TOP_QUERY_RESULT= 100 # Number of query retiriveted at once
DOCUMENT_TYPE = "Legal Cases" # Type of the document
LIMIT=100 #  limit of Search per day
USE_OPENAI_EMBEDDINGS = True # or False, to use the custom model