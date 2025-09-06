import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Ensure .env variables (e.g., GROQ_API_KEY) are loaded
load_dotenv()

def load_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in environment/.env")

    # Default to a currently supported Groq LLM; override with GROQ_MODEL
    model = os.getenv("GROQ_MODEL")
    return ChatGroq(api_key=api_key, model_name=model)
