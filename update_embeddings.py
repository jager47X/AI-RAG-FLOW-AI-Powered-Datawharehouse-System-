from pymongo import MongoClient
import openai
from config import (
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    MONGO_URI,
    OPENAI_API_KEY,
    THRESHOLD_QUERY_SEARCH,
    TOP_QUERY_RESULT,
    LIMIT,
    USE_OPENAI_EMBEDDINGS  
)
from db import get_openai_embedding  # Used only when USE_OPENAI_EMBEDDINGS is True
import torch
from sentence_transformers import SentenceTransformer

# If using OpenAI, set the API key
openai.api_key = OPENAI_API_KEY
# If not using OpenAI embeddings, load the custom embedding model.
if not USE_OPENAI_EMBEDDINGS:
    # Check if CUDA is available and set the device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load a SentenceTransformer model that outputs 768-dim embeddings by default.
    custom_model = SentenceTransformer('all-mpnet-base-v2').to(device)

    # Define a projection layer to map 768-dim embeddings to EMBEDDING_DIMENSIONS (e.g., 3072).
    class Projection(torch.nn.Module):
        def __init__(self, input_dim, output_dim):
            super(Projection, self).__init__()
            self.linear = torch.nn.Linear(input_dim, output_dim)
        
        def forward(self, x):
            return self.linear(x)

    input_dim = 768  # Dimension of the base model's output.
    output_dim = EMBEDDING_DIMENSIONS  # Typically set to 3072.
    projection = Projection(input_dim, output_dim).to(device)  # Move to GPU

    def get_custom_embedding(text):
        """
        Compute an embedding for the input text using a SentenceTransformer model
        and then project it to the desired dimensionality.
        
        Note: The projection layer is randomly initialized. For production use,
        you should fine-tune this layer on your specific data.
        """

        print("Generating embedding for text...")
        try:
            # Get the base embedding (768-dim) and move to GPU
            embedding = custom_model.encode(text, convert_to_tensor=True).to(device)
            # Project to EMBEDDING_DIMENSIONS (e.g., 3072-dim)
            embedding_proj = projection(embedding)
        except Exception as e:
            print("Error generating embedding:", e)
            raise e
        # Convert to a NumPy array after moving back to CPU
        return embedding_proj.detach().cpu().numpy()

def update_corpus_embeddings():
    """
    For each document in the corpus that lacks an 'embedding' field,
    compute the embedding using the selected method (OpenAI or custom)
    and update the document.
    """
    print("Connecting to the database....")
    client = MongoClient(MONGO_URI)
    db = client['rag_db']
    corpus_collection = db['corpus']
    print("Connected to the database.")
    
    docs = corpus_collection.find({"embedding": {"$exists": False}})
    for doc in docs:
        text = doc.get("text", "")
        if text:
            if USE_OPENAI_EMBEDDINGS:
                # Use the OpenAI embedding function from db.
                embedding = get_openai_embedding(text).tolist()
            else:
                # Use the custom embedding function.
                embedding = get_custom_embedding(text).tolist()
            corpus_collection.update_one({"_id": doc["_id"]}, {"$set": {"embedding": embedding}})
            print(f"Updated embedding for _id: {doc.get('_id')}")
    client.close()

if __name__ == "__main__":
    update_corpus_embeddings()