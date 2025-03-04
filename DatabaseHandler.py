import numpy as np
import datetime
import logging
from pymongo import MongoClient
from annoySearch import AnnoySearch  # Use your pre-built Annoy search module
from openai_service import ChatGPT  # Service for embeddings, rephrasing, etc.
import tiktoken  # pip install tiktoken
from config import (
    MONGO_URI,
    TOP_QUERY_RESULT,
    LIMIT,
    COLLECTION,
    EMBEDDING_MODEL,
)

# Configure logging.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Global constant for max tokens.
MAX_TOTAL_TOKENS = 8000

class DatabaseHandler:
    def __init__(self, config, mongo_uri=MONGO_URI):
        """
        Initialize the database connection using the provided configuration dictionary.
        
        :param config: Dictionary containing keys:
            - "db_name"
            - "query_collection_name"
            - "embedding_collection_name"
            - "annoy_collection_name"
            - "annoy_index_path"
            - "id_map_path"
            - "document_type"
            - "unique_index" (e.g., "title" or "version_id")
        :param mongo_uri: The MongoDB connection URI.
        """
        # Unpack the config dictionary.
        self.db_name = config["db_name"]
        self.query_collection_name = config["query_collection_name"]
        self.embedding_collection_name = config["embedding_collection_name"]
        self.annoy_collection_name = config["annoy_collection_name"]
        self.annoy_index_path = config["annoy_index_path"]
        self.id_map_path = config["id_map_path"]
        self.document_type = config["document_type"]
        self.unique_field = config.get("unique_index", "title")

        # Connect to MongoDB.
        self.client = MongoClient(mongo_uri)
        self.db = self.client[self.db_name]
        self.query_collection = self.db[self.query_collection_name]
        self.embedding_collection = self.db[self.embedding_collection_name]
        self.annoy_collection = self.db[self.annoy_collection_name]
        # Instantiate the Annoy search module and ChatGPT service.
        self.searchEngine = AnnoySearch(self.annoy_index_path, self.id_map_path, self.db_name,self.annoy_collection_name) # Make sure passing NAME of db and collection
        self.openAI = ChatGPT(db=self.db )

        # Also set the embedding model from config.
        self.embedding_model = EMBEDDING_MODEL

        logger.info("DatabaseHandler initialized with configuration: %s", self.document_type)

    def truncate_text(self, text, max_tokens=MAX_TOTAL_TOKENS, model=EMBEDDING_MODEL):
        """
        Encodes the entire text using the tokenizer for the specified model.
        If the token count exceeds max_tokens, truncates the text.
        """
        encoding = tiktoken.encoding_for_model(model)
        tokens = encoding.encode(text)
        if len(tokens) > max_tokens:
            logger.info("Text is too long (%d tokens). Truncating to %d tokens.", len(tokens), max_tokens)
            tokens = tokens[:max_tokens]
            text = encoding.decode(tokens)
        return text

    def get_openai_embedding(self, text, model=EMBEDDING_MODEL):
        """
        Generates an embedding for the given text (after truncation).
        """
        text = self.truncate_text(text, model=model)
        logger.info("Generating embedding for text...")
        try:
            response = self.openAI.embeddings.create(
                model=model,
                input=text
            )
        except Exception as e:
            logger.error("Error generating embedding: %s", e)
            raise e

        # Use dictionary indexing (or dot notation) to access the embedding.
        embedding = response['data'][0]['embedding']
        logger.info("Embedding generated.")
        return np.array(embedding)

    def get_or_create_query_embedding(self, query):
        """
        Checks if the query embedding exists in the 'queries' collection.
        If it exists, returns the cached embedding; otherwise, computes it,
        stores it, and returns it.
        """
        doc = self.query_collection.find_one({"query": query})
        if doc and "embedding" in doc:
            logger.info("Using cached embedding for query.")
            embedding = doc["embedding"]
        else:
            logger.info("Computing new embedding for query.")
            embedding = self.openAI.get_openai_embedding(query).tolist()
            self.query_collection.insert_one({
                "query": query,
                "embedding": embedding,
                "timestamp": datetime.datetime.now()
            })
        return np.array(embedding)

    def process_query(self, query):
        """
        Processes the query by checking usage limits, obtaining or caching its embedding,
        and searching for similar cases using the pre-built Annoy index.
        Rephrases the query if necessary.
        """
        logger.info("User query: %s", query)

        previous_rephrases = []
        rephrase_attempt = 0
        similar_cases = None
        query_processed = True
        logger.info("Querying...")
        current_query  = query.replace(" ", "").lower()

        while rephrase_attempt < 5 or similar_cases==0:
            if rephrase_attempt > 0:
                logger.info("No similar cases found above threshold. Rephrasing query (attempt %d)...", rephrase_attempt + 1)
                current_query = self.openAI.rephrase_query(query, self.document_type,previous_rephrases)
                logger.info("New query: %s", current_query)
                previous_rephrases.append(current_query)
                query = current_query

            # Check for cached query embedding.
            existing_doc = self.query_collection.find_one({"query": current_query})
            if existing_doc and "embedding" in existing_doc:
                query_embedding = np.array(existing_doc["embedding"])
                logger.info("Using cached query embedding.")
            else:
                query_embedding = self.openAI.get_openai_embedding(current_query)
                document = {
                    "query": current_query,
                    "embedding": query_embedding.tolist(),
                    "timestamp": datetime.datetime.now()
                }
                self.query_collection.insert_one(document)
                logger.info("Stored new query embedding in MongoDB.")

            logger.info("Searching in the vector database for up to %d results.", TOP_QUERY_RESULT)
            similar_cases = self.searchEngine.search_similar(query_embedding)
            if similar_cases:
                break
            rephrase_attempt += 1

        if not similar_cases:
            logger.warning("No similar cases found after rephrasing 5 times.")
            self.client.close()
            return None, query_processed


        # Log details for each similar case including similarity.
        for doc, similarity in similar_cases:
            logger.info("Query: %s | Document [%s]: %s | Similarity: %.2f",
                        current_query, self.unique_field, doc.get(self.unique_field), similarity)
        return similar_cases, query_processed

    def close(self):
        self.client.close()

# For testing purposes:
if __name__ == "__main__":
    # For testing, select a configuration. Here we hardcode using the US Constitution config.
    # (Adjust this to allow selection by number or any other method.)
    config = COLLECTION["US_CONSITITON_SET"]
    logger.info("Using configuration: %s", config["document_type"])
    handler = DatabaseHandler(config)
    sample_query = input("Enter a query: ").strip()
    results, processed = handler.process_query(sample_query)
    if results:
        for doc, sim in results:
            logger.info("Result: %s | Similarity: %.2f", doc.get(handler.unique_field), sim)
    else:
        logger.info("No results found or search limit reached.")
