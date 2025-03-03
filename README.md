# AI-RAG FLOW -Local AI Powered Datawharehouse System-
🌍[DEMO](https://ai-ragflow.com/)
## 📖 Table of Contents
- [📝 Introduction](#introduction)
- [📊 Features](#features)
- [📂 Project Structure](#project-structure)
- [🔧 Setup Instructions](#setup-instructions)
  - [Clone the Repository](#clone-the-repository)
  - [Install Dependencies](#install-dependencies)
  - [Configure Environment Variables](#configure-environment-variables)
- [✅ Usage](#usage)
- [⚙️ Customization](#customization)
  - [Change the Embedding Model](#change-the-embedding-model)
- [📜 License](#license)
- [🤝 Contributing](#contributing)
- [📬 Contact](#contact)


## 📝 Introduction
### 🚀 Motivation

Currently, we rely on ChatGPT for searching, but it presents several issues:

#### ⚠️ Problems:
- 🔍 **Hallucination** – The model sometimes generates inaccurate or misleading information.
- 📉 **Incomplete Results** – It does not retrieve all relevant matches.

#### ✅ Solution:
This project is a **Retrieval-Augmented Generation (RAG) system** designed to handle large datasets, specifically for **legal text analysis and retrieval**. It leverages:
- 🗄️ **MongoDB** for document storage and retrieval.
- 🧠 **OpenAI embeddings** for semantic search.
- ⚡ **Annoy-based vector search** for efficient similarity-based matching.

### 🔥 Key Improvements:
- 🛡️ **Reduced Hallucination** – By restricting searches to a **local domain**, we drastically lower the chances of misinformation.
- 🎯 **Higher Accuracy** – Utilizing the **latest OpenAI embedding model**, we aim to surpass existing solutions in precision and relevance.
- 💰 **Optimized API Usage** – By caching and saving search queries, we **reduce API costs** while maintaining efficient retrieval.


### 📂 Dataset Used
For testing, this system utilizes the Open Australian Legal Corpus, available on Kaggle:🔗 [Open Australian Legal Corpus](https://www.kaggle.com/datasets/umarbutler/open-australian-legal-corpus)
## 📊 Features
### 🔹 Key Features
- ✅ Scalable Large-Scale Data Processing – Designed for handling extensive datasets efficiently.
- 🔥 ChatGPT API with the Latest Embedding Model – Ensures high-accuracy text search and retrieval.
- ⚡ Optimized RAG Pipeline – Balances retrieval accuracy and generation quality for better responses.
- 💾 Local Vector Database Storage – Saves embeddings locally to minimize API calls, reducing cost and improving speed.
- 🏗 Customizable & Extendable – Easily tweak settings, vector database configurations, and embeddings.
### 💡 How It Works
- Preprocess Large Datasets : Loads and processes structured or unstructured data.
- Generate & Store Embeddings : Uses ChatGPT embeddings and saves them locally for vector-based search.
- Efficient Retrieval & Augmentation : Quickly fetches relevant data using an optimized vector search engine.
- ChatGPT-Powered Responses : The system refines retrieved results and generates intelligent, context-aware responses.
- API Optimization : By caching embeddings and search results, the system reduces redundant API calls.

### 🔹 Data Processing & Storage
- ✅ Data Ingestion – Reads and loads structured/unstructured documents from a JSONL file into MongoDB.
- ✅ Embedding Generation – Uses OpenAI's embedding API to convert text into high-dimensional vector representations for efficient search.

### 🔍 Intelligent Search & Retrieval
- ⚡ Vector Search – Employs Annoy (Approximate Nearest Neighbors) for fast and scalable vector-based document retrieval.
- 📊 Similarity Ranking – Uses cosine similarity to rank and filter the most relevant documents based on the user query.

### 🧠 AI-Powered Summarization
💡 Context-Aware Summarization – Extracts insights from the top 10 retrieved cases and summarizes results using ChatGPT.

### ⚙️ Scalable & Modular Design
#### 🏗 Modular Architecture:
- 📂 Data Ingestion: Reads documents from a JSONL file and stores them in MongoDB.
- 🧠Embedding Generation: Uses OpenAI's embedding API to convert text into high-dimensional vectors.
- ⚡ Vector Search:Utilizes Annoy for efficient, approximate nearest neighbor searches.
- 📊 Similarity Ranking:Applies cosine similarity to filter and rank relevant documents.
- 📝 Summarization:Summarizes the top 10 retrieved cases using ChatGPT.


## 📂 Project Structure

- **config.py**:Loads environment variables (.env) 
- **ingest.py(ingest_legal_Corpus)** :Ingests CSV data into MongoDB 
- **db.py**:ETL query, Embedding computation, Annoy index building, and similarity search
- **summarizer.py** : ChatGPT summarization of retrieved cases
- **main.py**:    Main entry point for user query processing
- **.env**:   Contains sensitive variables (API keys, MongoDB URI, etc.)
- **requirements.txt**:   Python dependencies

## 🔧 Setup Instructions
### 1. 🖥️ Clone the Repository

```bash
git clone https://github.com/yourusername/vector-rag-system.git
cd vector-rag-system
```
### 2. 📦 Install Dependencies

Ensure you have Python installed, then run:
```bash
pip install -r requirements.txt
```
If you do not have MongoDB:
🔗 [Install MongoDB](https://www.mongodb.com/docs/manual/installation/)
### 3. 🔧 Configure Environment Variables

Create a .env file in the project root with the following content:

```bash
OPENAI_API_KEY=your_openai_api_key_here # Get OpenAI'API 
MONGO_URI=mongodb://localhost:27017/   # Local 
JSONL_PATH=your_data.jsonl             # Add the path for the ingesting
EMBEDDING_MODEL=text-embedding-3-large # The latest model
EMBEDDING_DIMENSIONS=1024              # This is the configuration of text-embedding-3-large
```
🔗 [OpenAI'API](https://openai.com/api/)
## ✅ Usage

### 1. 🔄 Prepare Data
- Each Parsing needs to be implmented beforehand, then load your JSONL data into MongoDB by running:
```bash
python ingest.py
```
### 2. ⚡ Process Queries
- Launch the main application to handle user queries:
```bash
python main.py
```
- When prompted, enter your query. The system will:
Compute the embedding for your query.
- Search the Annoy index for similar documents.
- Summarize the top 10 matching cases using ChatGPT.
- Display the summarized insights in the console.

## ⚙️ Customization
- Embedding Model: Change the EMBEDDING_MODEL in your .env file to use a different OpenAI model if needed.
- MongoDB Configuration: Adjust the MONGO_URI in your .env file to connect to a different MongoDB instance.
- Annoy Settings: Tweak parameters such as VECTOR_SIZE and ANNOY_TREE_COUNT in vector_db.py to suit your data and - performance requirements.
- Summarization Prompt: Modify the prompt in summarizer.py to tailor the summarization output.
## 🚀 Future Improvements
- Add More DataSet
- Advanced Vector DBs: Experiment with specialized vector databases like Pinecone, Milvus, or Qdrant for even faster search performance.
## 📜 License
#### ⚠️ This project is licensed under the MIT License.

## 🤝Contributer
### 👤Software Engineer: Yuto Mori (Auther)
### 👤Designer: Ambre Grimault 

## 📬Contact
Contributions, issues, and feature requests are welcome! Please check the issues page for known issues and to submit new ones.
#### 📧Email: contact.ragflow@gmail.com 
