import pickle
import json
import logging
from pymongo import MongoClient
from annoy import AnnoyIndex
from bson import ObjectId  # Needed to convert string ID to ObjectId
from config import MONGO_URI, EMBEDDING_DIMENSIONS, THRESHOLD_QUERY_SEARCH, TOP_QUERY_RESULT

# Configure logging.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class AnnoySearch:
    """Class to manage Annoy index search and MongoDB retrieval."""
    
    def __init__(self, annoy_index_path, id_map_path, db_name, collection_name):
        """
        Initialize AnnoySearch class.
        
        :param annoy_index_path: Path to the saved Annoy index file.
        :param id_map_path: Path to the saved ID mapping file.
        :param db_name: Name of the MongoDB database.
        :param collection_name: Name of the MongoDB collection.
        """
        self.vector_size = EMBEDDING_DIMENSIONS
        self.annoy_index_path = annoy_index_path
        self.id_map_path = id_map_path
        self.db_name = db_name
        self.collection_name = collection_name
        self.index, self.id_map = self._load_annoy_index()
        logger.info("Annoy index and ID map loaded successfully.")
    
    def _load_annoy_index(self):
        """Load the Annoy index and ID mapping from disk."""
        index = AnnoyIndex(self.vector_size, 'angular')
        try:
            index.load(self.annoy_index_path)
            logger.info("Annoy index loaded from %s", self.annoy_index_path)
        except Exception as e:
            logger.error("Failed to load Annoy index from %s: %s", self.annoy_index_path, e)
            raise e
        try:
            with open(self.id_map_path, "rb") as f:
                id_map = pickle.load(f)
            logger.info("ID map loaded from %s", self.id_map_path)
        except Exception as e:
            logger.error("Failed to load ID map from %s: %s", self.id_map_path, e)
            raise e
        return index, id_map
    
    def search_similar(self, query_embedding):
        """
        Search for similar documents using the Annoy index.
        
        :param query_embedding: The embedding vector for the query.
        :return: A list of tuples (document, similarity_score).
        """
        logger.info("Searching for similar documents...")
        indices, distances = self.index.get_nns_by_vector(query_embedding, TOP_QUERY_RESULT, include_distances=True)
        logger.info("Annoy returned %d indices.", len(indices))
        results = []
        
        # Connect to MongoDB.
        client = MongoClient(MONGO_URI)
        db = client[self.db_name]
        collection = db[self.collection_name]
        
        for idx, dist in zip(indices, distances):
            similarity = 1 - dist / 2  # Convert angular distance to cosine similarity.
            logger.debug("Index: %d, Distance: %.4f, Similarity: %.4f", idx, dist, similarity)
            if similarity >= THRESHOLD_QUERY_SEARCH:
                try:
                    # Convert stored string ID to ObjectId.
                    doc_id = ObjectId(self.id_map[idx])
                except Exception as e:
                    logger.error("Error converting ID %s to ObjectId: %s", self.id_map[idx], e)
                    continue
                doc = collection.find_one({"_id": doc_id}, {"embedding": 0})  # Exclude embedding field.
                if doc:
                    results.append((doc, similarity))
                    logger.debug("Found document with ID %s, similarity %.4f", self.id_map[idx], similarity)
                else:
                    logger.warning("No document found for ID %s", self.id_map[idx])
            else:
                logger.debug("Index %d similarity %.4f below threshold %.4f", idx, similarity, THRESHOLD_QUERY_SEARCH)
        
        client.close()
        results.sort(key=lambda x: x[1], reverse=True)
        logger.info("Search complete. %d documents returned.", len(results))
        return results
