# Agentic Retail Chatbot

A small FastAPI + LangGraph backend with Streamlit front-ends for a retail assistant. It answers product, order, and return policy questions using:

- SQLite (products, orders)
- ChromaDB RAG (return policy docs)
- Groq LLM (via `langchain-groq`)

## Prerequisites

- Python 3.11
- A Groq API key (get one from console.groq.com)

## Quick start (Windows PowerShell)

1. Clone and enter the project directory, then create/activate a virtualenv:

```powershell
python -m venv .venv
."\.venv\Scripts\Activate.ps1"
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Configure environment variables (create a `.env` or set in the shell). Minimal required:

```powershell
# Set for current session
$env:GROQ_API_KEY = "<your_groq_api_key>"

# Optional overrides (defaults shown)
# $env:DB_PATH = "db/retail.db"
# $env:RAG_DIR = "rag_db"
# $env:EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

4. Initialize data (only if you need to regenerate):

```powershell
# SQLite (creates db/retail.db from data/*.csv)
python app/setup/init_sqlite.py

# RAG (embeds data/return_policy.txt into rag_db/)
python app/setup/init_rag.py
```

Note: This repository already includes `db/retail.db` and `rag_db/`. You can skip step 4 unless you want to rebuild.

5. Run the backend API (FastAPI on http://127.0.0.1:8000):

```powershell
python app/main.py
```

Health check: visit http://127.0.0.1:8000/health

6. In a new terminal, run the Streamlit chat UI:

```powershell
."\.venv\Scripts\Activate.ps1"; streamlit run .\streamlit_chat.py
```

7. (Optional) In another terminal, run the metrics dashboard:

```powershell
."\.venv\Scripts\Activate.ps1"; streamlit run .\streamlit_dashboard.py
```

## Troubleshooting

- Missing DB: Run `python app/setup/init_sqlite.py`.
- Missing RAG vectors: Run `python app/setup/init_rag.py` (requires internet to download the embedding model on first run).
- 500 errors from `/chat`: Ensure `$env:GROQ_API_KEY` is set and valid.
- Port in use: Change FastAPI port in `app/main.py` or run Streamlit with `--server.port`.
