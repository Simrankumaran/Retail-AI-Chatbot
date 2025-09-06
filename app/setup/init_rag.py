import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter

import chromadb
from chromadb.utils import embedding_functions

load_dotenv()

# Load env vars or defaults
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
RAG_DIR = os.getenv("RAG_DIR", "rag_db")
COLLECTION_NAME = os.getenv("RAG_COLLECTION", "return_policy")

# Paths
policy_path = Path("data/return_policy.txt").resolve()
if not policy_path.exists():
    raise FileNotFoundError(f"Policy file not found at: {policy_path}")

# Step 1: Load and chunk the policy document
loader = TextLoader(str(policy_path))
documents = loader.load()
splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(documents)

# Step 2: Create ChromaDB Persistent Client and collection with embedding fn
client = chromadb.PersistentClient(path=str(RAG_DIR))
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

# Create or reset collection to ensure a clean build
try:
    client.delete_collection(COLLECTION_NAME)
except Exception:
    # ok if it doesn't exist yet
    pass

collection = client.create_collection(name=COLLECTION_NAME, embedding_function=embedding_fn)

# Step 3: Add chunked documents
ids = [f"policy-{i}" for i in range(len(chunks))]
docs = [c.page_content for c in chunks]
metas = [
    {"source": "return_policy.txt", "chunk": i, "path": str(policy_path)}
    for i in range(len(chunks))
]

collection.add(ids=ids, documents=docs, metadatas=metas)

count = collection.count()
print(f"RAG setup complete. {count} chunks stored in collection '{COLLECTION_NAME}' at: {RAG_DIR}")
