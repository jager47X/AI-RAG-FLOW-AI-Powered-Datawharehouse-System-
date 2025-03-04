import openai
import numpy as np
import logging
import datetime
import tiktoken  # Ensure you have installed the tiktoken package
from config import OPENAI_API_KEY, EMBEDDING_MODEL, LIMIT
MAX_TOTAL_TOKENS = 8000 

# Set OpenAI API key.
openai.api_key = OPENAI_API_KEY

# Configure logging.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class ChatGPT:
    def __init__(self, db, preprocess=False):
        """
        Initialize ChatGPT service.
        
        :param db: MongoDB database instance (for search limits, etc.)
        """
        self.chat_model = "gpt-4o"  # Chat model to use for completions
        self.embedding_model = EMBEDDING_MODEL
        self.db = db
        self.preprocess=preprocess
        # Optionally, set a default unique field; this can be overwritten externally.
        self.unique_field = "title"

    def summarize_cases(self, case):
        """
        Summarizes a single case document using ChatGPT.
        If a summary already exists in the case, returns it.
        Otherwise, generates a summary, updates the document in the database,
        stores it in the case dictionary, and returns it.
        """
        if case.get("summary"):
            logger.info("Summary already exists for case with %s: %s", 
                        self.unique_field, case.get(self.unique_field))
            return case["summary"]

        context = f"context:\n{case.get('text')}"
        prompt = (
            f"Summarize the following case and highlight the top insights:\n\n"
            f"{context}\n\nSummary:"
        )

        logger.info("Generating summary for case with %s: %s", 
                    self.unique_field, case.get(self.unique_field))
        try:
            response = openai.chat.completions.create(
                model=self.chat_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            summary = response.choices[0].message.content.strip()
            logger.info("Summary generated successfully for case with _id: %s", case.get("_id"))
        except Exception as e:
            logger.error("Error generating summary: %s", e)
            summary = ""
        
        # Update the summary in the document stored in the annoy collection.
        try:
            # Update the document with the generated summary.
            # Adjust the collection name as necessary.
            self.db["us_constitution_annoy"].update_one(
                {"_id": case["_id"]},
                {"$set": {"summary": summary}}
            )
            logger.info("Updated summary in database for case with _id: %s", case.get("_id"))
        except Exception as e:
            logger.error("Failed to update summary in database: %s", e)
        
        # Also update the case dictionary locally.
        case["summary"] = summary
        # Increment the search count (if needed).
        self.increment_search_count(self.can_search_today()[1])
        return summary

    def rephrase_query(self, query, avoid_list):
        """
        Rephrases the input query using ChatGPT to generate a more effective version,
        while avoiding any phrases provided in avoid_list.
        """
        query_allowed, usage = self.can_search_today(limit=LIMIT)
        if not query_allowed:
            logger.warning("Reached the daily search limit.")
            return None
        avoid_text = ""
        if avoid_list:
            avoid_text = "\nAvoid using any of the following phrases: " + ", ".join(avoid_list)
        
        prompt = (
            f"Rephrase the following query to improve its clarity and effectiveness:\n\n"
            f"Query: {query}\n"
            f"{avoid_text}\n\n"
            f"Rephrased Query:"
        )
        
        logger.info("Rephrasing query: %s", query)
        try:
            response = openai.chat.completions.create(
                model=self.chat_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150
            )
            rephrased_query = response.choices[0].message.content.strip()
            logger.info("Rephrased query generated successfully.")
        except Exception as e:
            logger.error("Error rephrasing query: %s", e)
            rephrased_query = None
        
        self.increment_search_count(usage)
        return rephrased_query

    def get_openai_embedding(self, text, model=EMBEDDING_MODEL):
        """
        Generates an embedding for the given text (after truncation).
        """
        query_allowed, usage = self.can_search_today(limit=LIMIT)
        if not query_allowed:
            logger.warning("Reached the daily search limit.")
            return None
        text = self.truncate_text(text, max_tokens=MAX_TOTAL_TOKENS, model=model)
        logger.info("Generating embedding for text...")
        try:
            response = openai.embeddings.create(
                model=model,
                input=text
            )
        except Exception as e:
            logger.error("Error generating embedding: %s", e)
            raise e

        # DO NOT CHANGE THE METHOD CALL TO OPEN AI.
        embedding = response.data[0].embedding
        logger.info("Embedding generated.")
        self.increment_search_count(usage)
        return np.array(embedding)

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

    def get_today_str(self):
        """Return today's date as an ISO string."""
        today_str = datetime.date.today().isoformat()
        logger.info("Today's date: %s", today_str)
        return today_str

    def can_search_today(self, limit=100):
        """
        Returns True if today's search count is below the given limit.
        Also returns the current count.
        """
        if not self.preprocess:
            today = self.get_today_str()
            record = self.db.search_limits.find_one({"date": today})
            if record is None:
                new_record = {"date": today, "OpenAPI_Request": 0}
                self.db.search_limits.insert_one(new_record)
                logger.info("Usage of today: 0.")
                return True, 0
            usage_today = record.get("OpenAPI_Request", 0)
            logger.info("Usage of today: %d", usage_today)
            return usage_today < limit, usage_today
        return True,0

    def increment_search_count(self, count):
        """Increment today's search count by one."""
        if not self.preprocess:
            today = self.get_today_str()
            new_count = count + 1  # calculate new count for logging
            logger.info("Updated usage of today to %d.", new_count)
            # Use $inc with 1 so that it increments by one, regardless of count
            self.db.search_limits.update_one(
                {"date": today},
                {"$inc": {"OpenAPI_Request": 1}},
                upsert=True
            )