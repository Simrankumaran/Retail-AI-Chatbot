from fastapi import FastAPI, Request, HTTPException
import traceback
from pydantic import BaseModel
from app.agent import get_agent
from app.logger import log_interaction

app = FastAPI(title="Agentic Retail Chatbot")

# === Request schema ===
class ChatRequest(BaseModel):
    query: str

# === Response schema ===
class ChatResponse(BaseModel):
    response: str

# === Create agent on startup ===
agent = get_agent()

# === POST /chat ===
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        response = agent(req.query)
        log_interaction(req.query, response)
        return {"response": response}
    except Exception as e:
        # Print full traceback to server logs for debugging
        print("Agent backend error:\n" + traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

# === GET /health ===
@app.get("/health")
def health():
    return {"status": "ok"}

# === GET /metrics (placeholder) ===
@app.get("/metrics")
def metrics():
    return {
        "total_queries": 0,
        "tools_used": {},
        "avg_response_time_ms": 0
    }
