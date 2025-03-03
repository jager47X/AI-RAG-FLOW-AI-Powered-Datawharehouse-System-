import numpy as np
from annoy import AnnoyIndex
from pymongo import MongoClient
from chatgpt import rephrase_query
import openai
import tiktoken  # pip install tiktoken
from config import EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, MONGO_URI, OPENAI_API_KEY,THRESHOLD_QUERY_SEARCH ,TOP_QUERY_RESULT,LIMIT
import datetime
openai.api_key = OPENAI_API_KEY

# Use the shortened embedding dimension as the vector size for Annoy.
VECTOR_SIZE = EMBEDDING_DIMENSIONS
ANNOY_INDEX_PATH = "corpus.ann"
ANNOY_TREE_COUNT = 10
# Define the maximum total tokens for the content
MAX_TOTAL_TOKENS = 8000

def truncate_text(text, max_tokens=MAX_TOTAL_TOKENS, model=EMBEDDING_MODEL):
    """
    Encodes the entire text using the tokenizer for the specified model.
    If the token count exceeds max_tokens, it truncates the text to max_tokens.
    """
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)
    if len(tokens) > max_tokens:
        print(f"Text is too long ({len(tokens)} tokens). Truncating to {max_tokens} tokens.")
        tokens = tokens[:max_tokens]
        text = encoding.decode(tokens)
    return text

def get_openai_embedding(text):
    # Truncate the entire text to a maximum of 8000 tokens.
    text = truncate_text(text)
    
    print("Generating embedding for text...")
    try:
        response = openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
    except Exception as e:
        print("Error generating embedding:", e)
        raise e

    # Access embedding using dot notation.
    embedding = response.data[0].embedding
    print("Embedding generated.")
    return np.array(embedding)

def get_or_create_query_embedding(query):
    """
    Checks if the query embedding already exists in the 'queries' collection.
    If it exists, returns the cached embedding; otherwise, computes it, stores it, and returns it.
    """
    client = MongoClient(MONGO_URI)
    db = client['rag_db']
    query_collection = db['queries']
    
    # Look up the query in the database.
    doc = query_collection.find_one({"query": query})
    if doc and "embedding" in doc:
        print("Using cached embedding for query.")
        embedding = doc["embedding"]
    else:
        print("Computing new embedding for query.")
        embedding = get_openai_embedding(query).tolist()
        query_collection.insert_one({"query": query, "embedding": embedding})
    client.close()
    return np.array(embedding)



def build_annoy_index():
    """
    Build an Annoy index from documents in MongoDB that have embeddings.
    Returns the Annoy index and a mapping from index positions to MongoDB document _id.
    """
    client = MongoClient(MONGO_URI)
    db = client['rag_db']
    corpus_collection = db['corpus']
    
    docs = list(corpus_collection.find({"embedding": {"$exists": True}}))
    index = AnnoyIndex(VECTOR_SIZE, 'angular')
    id_map = {}
    
    for i, doc in enumerate(docs):
        emb = doc.get("embedding")
        if emb is not None:
            index.add_item(i, emb)
            id_map[i] = doc["_id"]
    
    index.build(ANNOY_TREE_COUNT)
    index.save(ANNOY_INDEX_PATH)
    client.close()
    return index, id_map

def search_similar(query_embedding, top_n=10, threshold=0.7):
    """
    Given a query embedding, search the Annoy index for similar documents.
    Returns a list of tuples (document, similarity_score) with similarity above the threshold.
    """
    client = MongoClient(MONGO_URI)
    index, id_map = build_annoy_index()
    indices, distances = index.get_nns_by_vector(query_embedding, top_n, include_distances=True)
    results = []
    
    # Convert Annoy's angular distance to cosine similarity: similarity = 1 - (distance / 2)
    for idx, dist in zip(indices, distances):
        similarity = 1 - dist / 2
        if similarity >= threshold:
            doc = client['rag_db']['corpus'].find_one({"_id": id_map[idx]})
            if doc:
                results.append((doc, similarity))
    client.close()
    results.sort(key=lambda x: x[1], reverse=True)
    return results
def rephrase_query(query, avoid_list):
    """
    Rephrases the input query using ChatGPT to generate a more effective version.
    It also avoids reusing any phrases in avoid_list.
    """
    avoid_text = ""
    if avoid_list:
        avoid_text = "\nAvoid using any of the following phrases: " + ", ".join(avoid_list)
    
    prompt = (
        f"Rephrase the following query to improve its clarity and effectiveness:\n\n"
        f"Query: {query}\n"
        f"{avoid_text}\n\n"
        f"Rephrased Query:"
    )
    
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150
    )
    rephrased_query = response.choices[0].message.content.strip()
    return rephrased_query

def get_today_str():
    """Return today's date as an ISO string, e.g., '2025-03-02'."""
    print(datetime.date.today().isoformat())
    return datetime.date.today().isoformat()

# FIXED: Ensure that 'db' is the first parameter.
def can_search_today(db, limit=100):
    """Return True if today's search count is below the given limit."""
    today = get_today_str()
    record = db.search_limits.find_one({"date": today})
    Usage_today=record.get("count", 0)
    print(f"usage of today:{Usage_today}.")
    if record is None:
        return True
    return record.get("count", 0) < limit,Usage_today

def increment_search_count(db,count):
    """Increment today's search count by one."""
    today = get_today_str()
    count+=1
    print(f"updated usage of today to {count}.")
    
    db.search_limits.update_one(
        {"date": today},
        {"$inc": {"count": count}},
        upsert=True
    )


def process_query(query):
    query_processed = False
    # Connect to MongoDB and get the queries collection.
    client = MongoClient(MONGO_URI)
    db = client['rag_db']
    query_collection = db['queries']

    # Check if the daily search limit is reached.
    query_processed,usage=can_search_today(db, limit=LIMIT)
    if not query_processed:
        client.close()
        return None, query_processed

    # List to keep track of all rephrased queries to avoid duplicates.
    previous_rephrases = []
    rephrase_attempt = 0
    similar_cases = None  # Initialize similar_cases
    query_processed = True

    # Loop up to 5 times: use original query on first attempt, then rephrase if needed.
    while rephrase_attempt < 5:
        if rephrase_attempt == 0:
            current_query = query  # Use the user's original input.
        else:
            print(f"No similar cases found above the threshold. Rephrasing query (attempt {rephrase_attempt + 1}/5)...")
            current_query = rephrase_query(query, previous_rephrases)
            print(f"New query: {current_query}")
            previous_rephrases.append(current_query)
            query = current_query  # Update query with the new rephrasing.

        # Check if the current query already exists in MongoDB.
        existing_doc = query_collection.find_one({"query": current_query})
        if existing_doc and "embedding" in existing_doc:
            query_embedding = np.array(existing_doc["embedding"])
            print("Using cached query embedding.")
        else:
            # If it doesn't exist, compute the embedding.
            query_embedding = get_openai_embedding(current_query)
            # Store the new query and its embedding in MongoDB.
            document = {
                "query": current_query,
                "embedding": query_embedding.tolist(),  # Convert numpy array to list for storage.
                "timestamp": datetime.datetime.utcnow()
            }
            query_collection.insert_one(document)
            print("Stored new query embedding in MongoDB.")

        # Search the vector database for similar cases.
        print(f"Searching in the vector database up to {TOP_QUERY_RESULT} results.")
        similar_cases = search_similar(query_embedding, top_n=TOP_QUERY_RESULT, threshold=THRESHOLD_QUERY_SEARCH)
        if similar_cases:
            break  # Similar cases found, exit loop

        rephrase_attempt += 1

    if not similar_cases:
        print("No similar cases found after rephrasing 5 times.")
        client.close()
        return None, query_processed
    # Increment the daily search counter.
    increment_search_count(db,usage)

    client.close()
    return similar_cases, query_processed
