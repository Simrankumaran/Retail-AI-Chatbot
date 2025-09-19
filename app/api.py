from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.agent import get_agent

# === Request schema ===
class ChatRequest(BaseModel):
    query: str

# === Response schema ===
class ChatResponse(BaseModel):
    response: str

# === Create agent on startup ===
app = FastAPI(title="Agentic Retail Chatbot")
agent = get_agent()

# === POST /chat ===
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        response = agent(req.query) 
        return {"response": response}
    except Exception as e:
        import traceback
        print("Agent error:", e)
        print(traceback.format_exc())
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
