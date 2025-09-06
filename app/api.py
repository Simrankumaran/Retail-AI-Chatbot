from fastapi import FastAPI, Request, HTTPException
import traceback
from pydantic import BaseModel
from app.agent import get_agent
from app.logger import log_interaction
import re
from app.utils.order_service import order_by_id, orders_by_status
from app.utils.order_service import orders_by_product_name

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
        # Fast-paths: handle direct order lookups and status filters without invoking the agent
        q = req.query.strip()
        q_low = q.lower()

        # 1) Order ID lookup: e.g. "status of order 12345" or "order #12345"
        m = re.search(r"order\s*(?:number|no\.|#)?\s*(\d+)", q_low)
        if m:
            order_id = m.group(1)
            response = order_by_id(order_id)
            log_interaction(req.query, response)
            return {"response": response}

        # 2) Orders by status: e.g. "which orders are pending" or "orders pending"
        statuses = ["pending", "processing", "shipped", "delivered", "cancelled", "returned"]
        for s in statuses:
            if re.search(rf"\b{s}\b", q_low):
                response = orders_by_status(s)
                log_interaction(req.query, response)
                return {"response": response}

        # 3) Product name lookup: e.g. "status of 'blue hoodie'" or "where is my blue hoodie"
        # If the query mentions a product name, return matching orders with product details.
        # This is a heuristic: detect quoted product names or phrases after 'my' or 'for'.
        m_quote = re.search(r"\'([\w\s-]+)\'|\"([\w\s-]+)\"", req.query)
        if m_quote:
            product = (m_quote.group(1) or m_quote.group(2)).strip()
            response = orders_by_product_name(product, limit=5)
            log_interaction(req.query, response)
            return {"response": response}

        # simple heuristic: 'my <product>' or 'for <product>'
        m_my = re.search(r"(?:my|for)\s+([\w\s-]{3,40})", q_low)
        if m_my:
            product = m_my.group(1).strip()
            response = orders_by_product_name(product, limit=5)
            log_interaction(req.query, response)
            return {"response": response}

        # Fallback to agent for other queries
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
