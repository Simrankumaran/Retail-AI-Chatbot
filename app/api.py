from fastapi import FastAPI, Request, HTTPException
import traceback
from pydantic import BaseModel
from app.agent import get_agent
from app.logger import log_interaction
import re
from app.utils.order_service import order_by_id, orders_by_status
from app.utils.order_service import orders_by_product_name, orders_returnable_by_user

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
def chat(req: ChatRequest, request: Request):
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
            # If the user is asking about returns, compute returnability
            if re.search(r"\breturn\b|\brefund\b|\bexchange\b", q_low):
                orders_text = orders_by_product_name(product, limit=5)
                mo = re.search(r"Order\s+(\d+)", orders_text)
                if mo:
                    oid = mo.group(1)
                    from app.utils.order_service import is_returnable
                    eligible = is_returnable(oid)
                    resp = f"{orders_text}\n\nReturnable: {'Yes' if eligible else 'No'}"
                    log_interaction(req.query, resp)
                    return {"response": resp}
            response = orders_by_product_name(product, limit=5)
            log_interaction(req.query, response)
            return {"response": response}

        # simple heuristic: 'my <product>' or 'for <product>'
        m_my = re.search(r"(?:my|for)\s+([\w\s-]{3,40})", q_low)
        if m_my:
            product = m_my.group(1).strip()
            if re.search(r"\breturn\b|\brefund\b|\bexchange\b", q_low):
                orders_text = orders_by_product_name(product, limit=5)
                mo = re.search(r"Order\s+(\d+)", orders_text)
                if mo:
                    oid = mo.group(1)
                    from app.utils.order_service import is_returnable
                    eligible = is_returnable(oid)
                    resp = f"{orders_text}\n\nReturnable: {'Yes' if eligible else 'No'}"
                    log_interaction(req.query, resp)
                    return {"response": resp}
            response = orders_by_product_name(product, limit=5)
            log_interaction(req.query, response)
            return {"response": response}

        # 4) What can I return? (match many phrasings like:
        #    "what are the orders i can return", "what can i return", "which orders can i return")
        if re.search(r"what\b.*\breturn\b|which orders can i return|what can (?:i|we) return", q_low):
            mu = re.search(r"user\s*(?:id\s*)?(\d{1,8})", q_low)
            if mu:
                uid = mu.group(1)
            else:
                # fallback: check headers for an authenticated user id
                hdr = request.headers.get("x-user-id") or request.headers.get("user-id")
                if hdr:
                    uid = hdr.strip()
                else:
                    # Default to user 2001 when no id is provided
                    uid = "2001"
            response = orders_returnable_by_user(uid)
            log_interaction(req.query, response)
            return {"response": response}

        # Fallback to agent for other queries. Guard against graph recursion errors
        # so we can return a helpful message instead of a 500 traceback.
        try:
            response = agent(req.query)
        except Exception as ex:
            # Try to detect langgraph GraphRecursionError without failing the import
            is_graph_recursion = False
            try:
                from langgraph.errors import GraphRecursionError
                is_graph_recursion = isinstance(ex, GraphRecursionError)
            except Exception:
                is_graph_recursion = False

            if is_graph_recursion:
                resp = (
                    "Sorry — the agent failed to complete your request due to an internal recursion. "
                    "Please try again, or ask with a specific order ID (for example: 'order 12345')."
                )
                log_interaction(req.query, resp)
                return {"response": resp}

            # re-raise non-graph errors to be handled by the outer exception block
            raise

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
