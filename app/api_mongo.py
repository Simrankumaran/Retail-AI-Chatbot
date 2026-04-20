"""API with MongoDB for chat storage."""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.agent_mongo import get_agent_mongo
from app.auth import (
    LoginRequest, LoginResponse, login_user,
    get_current_user, get_optional_user, get_default_user
)
from app.models import AgentRequest, AgentResponse, UserFeedback
from app.utils.db import init_db_schema
from app.utils.session_mongo import (
    init_mongo_collections,
    get_user_sessions,
    get_session_messages,
    get_session,
    get_user_stats,
    search_messages,
    delete_session
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Retail AI Chatbot API (MongoDB)")
    init_db_schema()  # SQLite for orders/products
    init_mongo_collections()  # MongoDB for chat
    logger.info("Database schemas initialized (SQLite + MongoDB)")
    yield
    logger.info("Shutting down Retail AI Chatbot API")


app = FastAPI(
    title="Retail AI Chatbot API (MongoDB)",
    description="AI-powered retail assistant with MongoDB chat storage",
    version="3.0.0-mongo",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get agent instance
agent = get_agent_mongo()

# In-memory feedback storage (can also move to MongoDB)
feedback_store = []


# ==================== Authentication Endpoints ====================

@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login and get access token."""
    try:
        response = login_user(request.user_id)
        logger.info("User logged in: %s", request.user_id)
        return response
    except Exception as e:
        logger.error("Login error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/me")
async def get_current_user_info(user_id: str = Depends(get_current_user)):
    """Get current authenticated user info."""
    return {"user_id": user_id, "authenticated": True}


# ==================== Chat Endpoints ====================

@app.post("/chat", response_model=AgentResponse)
async def chat(
    query: str,
    session_id: str = None,
    include_history: bool = True,
    user_id: str = Depends(get_current_user)
):
    """
    Process a chat query (AUTHENTICATED).
    Chat stored in MongoDB.
    """
    try:
        request = AgentRequest(
            query=query,
            user_id=user_id,
            session_id=session_id,
            include_history=include_history
        )
        logger.info("Chat request (MongoDB) from user %s: %s", user_id, query[:50])
        response = agent.run(request)
        return response
    except Exception as e:
        logger.error("Chat endpoint error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.post("/chat/demo", response_model=AgentResponse)
async def chat_demo(
    query: str,
    user_id: str = None,
    session_id: str = None,
    include_history: bool = True
):
    """
    Process a chat query (DEMO MODE - no auth).
    Chat stored in MongoDB.
    """
    try:
        effective_user_id = user_id or get_default_user()
        
        request = AgentRequest(
            query=query,
            user_id=effective_user_id,
            session_id=session_id,
            include_history=include_history
        )
        logger.info("Demo chat (MongoDB) from user %s: %s", effective_user_id, query[:50])
        response = agent.run(request)
        return response
    except Exception as e:
        logger.error("Demo chat error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


# ==================== Session Management (MongoDB) ====================

@app.get("/sessions")
async def list_user_sessions(
    limit: int = 20,
    user_id: str = Depends(get_current_user)
):
    """Get all chat sessions for the authenticated user from MongoDB."""
    try:
        sessions = get_user_sessions(user_id, limit)
        return {
            "user_id": user_id,
            "session_count": len(sessions),
            "sessions": sessions,
            "storage": "MongoDB"
        }
    except Exception as e:
        logger.error("Sessions list error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}/messages")
async def get_session_history(
    session_id: str,
    limit: int = 100,
    user_id: str = Depends(get_current_user)
):
    """Get all messages in a session from MongoDB."""
    try:
        # Verify session belongs to user
        session = get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if session["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        messages = get_session_messages(session_id, limit)
        return {
            "session_id": session_id,
            "message_count": len(messages),
            "messages": messages,
            "storage": "MongoDB"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Session messages error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
async def delete_user_session(
    session_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete a session and all its messages from MongoDB."""
    try:
        # Verify session belongs to user
        session = get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if session["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        deleted = delete_session(session_id)
        if deleted:
            return {"status": "deleted", "session_id": session_id}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Delete session error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/search")
async def search_user_messages(
    q: str,
    limit: int = 50,
    user_id: str = Depends(get_current_user)
):
    """Search messages by content in MongoDB."""
    try:
        results = search_messages(user_id, q, limit)
        return {
            "query": q,
            "result_count": len(results),
            "results": results
        }
    except Exception as e:
        logger.error("Search error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_user_statistics(user_id: str = Depends(get_current_user)):
    """Get user statistics from MongoDB."""
    try:
        stats = get_user_stats(user_id)
        return stats
    except Exception as e:
        logger.error("Stats error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Feedback ====================

@app.post("/feedback")
async def submit_feedback(
    feedback: UserFeedback,
    user_id: str = Depends(get_current_user)
):
    """Submit user feedback."""
    try:
        feedback_data = feedback.dict()
        feedback_data["user_id"] = user_id
        feedback_store.append(feedback_data)
        
        logger.info(
            "Feedback from user %s - session: %s, rating: %d",
            user_id,
            feedback.session_id,
            feedback.rating
        )
        return {"status": "success", "message": "Feedback recorded"}
    except Exception as e:
        logger.error("Feedback error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Health & Metrics ====================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "retail-ai-chatbot",
        "version": "3.0.0-mongo",
        "features": ["authentication", "MongoDB", "sessions", "search"]
    }


@app.get("/metrics")
async def metrics(user_id: str = Depends(get_optional_user)):
    """Get system metrics."""
    try:
        base_metrics = {
            "total_feedback": len(feedback_store),
            "avg_rating": sum(f["rating"] for f in feedback_store) / len(feedback_store) if feedback_store else 0,
            "storage": "MongoDB"
        }
        
        if user_id:
            user_stats = get_user_stats(user_id)
            base_metrics.update(user_stats)
        
        return base_metrics
    except Exception as e:
        logger.error("Metrics error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
