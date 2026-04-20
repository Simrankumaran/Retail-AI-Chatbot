"""Production-ready API with authentication and database persistence."""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.agent_db import get_agent_db
from app.auth import (
    LoginRequest, LoginResponse, login_user,
    get_current_user, get_optional_user, get_default_user
)
from app.models import AgentRequest, AgentResponse, UserFeedback
from app.utils.db import init_db_schema
from app.utils.session_db import init_session_schema, get_user_sessions, get_session_messages

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Retail AI Chatbot API (with Auth + DB)")
    init_db_schema()
    init_session_schema()
    logger.info("Database schemas initialized")
    yield
    logger.info("Shutting down Retail AI Chatbot API")


app = FastAPI(
    title="Retail AI Chatbot API",
    description="AI-powered retail assistant with authentication and session persistence",
    version="3.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get agent instance
agent = get_agent_db()

# In-memory feedback storage (move to session_db.py later)
feedback_store = []


# ==================== Authentication Endpoints ====================

@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login and get access token.
    
    In production, this would verify password, etc.
    For demo: accepts any 4-digit user_id.
    
    Example:
    ```
    POST /auth/login
    {
        "user_id": "2001"
    }
    
    Returns:
    {
        "access_token": "abc123...",
        "token_type": "bearer",
        "user_id": "2001",
        "expires_in": 3600
    }
    ```
    """
    try:
        response = login_user(request.user_id)
        logger.info("User logged in: %s", request.user_id)
        return response
    except Exception as e:
        logger.error("Login error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/me")
async def get_current_user_info(user_id: str = Depends(get_current_user)):
    """
    Get current authenticated user info.
    Requires: Authorization: Bearer <token>
    """
    return {"user_id": user_id, "authenticated": True}


# ==================== Chat Endpoints ====================

@app.post("/chat", response_model=AgentResponse)
async def chat(
    query: str,
    session_id: str = None,
    include_history: bool = True,
    user_id: str = Depends(get_current_user)  # 🔑 Automatically extracts user from token!
):
    """
    Process a chat query (AUTHENTICATED).
    
    Requires: Authorization: Bearer <token>
    
    The user_id is automatically extracted from your auth token,
    so you don't need to pass it in the request!
    
    Example:
    ```
    POST /chat
    Headers: Authorization: Bearer abc123...
    Body: {
        "query": "Show me my orders"
    }
    ```
    """
    try:
        request = AgentRequest(
            query=query,
            user_id=user_id,  # Comes from token!
            session_id=session_id,
            include_history=include_history
        )
        logger.info("Chat request from authenticated user %s: %s", user_id, query[:50])
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
    Process a chat query (DEMO MODE - no authentication).
    
    Use this for testing without authentication.
    If user_id is not provided, defaults to "2001" (your original approach).
    
    Example:
    ```
    POST /chat/demo
    Body: {
        "query": "Show me laptops",
        "user_id": "2001"  # Optional, defaults to 2001
    }
    ```
    """
    try:
        # Use provided user_id or default to 2001
        effective_user_id = user_id or get_default_user()
        
        request = AgentRequest(
            query=query,
            user_id=effective_user_id,
            session_id=session_id,
            include_history=include_history
        )
        logger.info("Demo chat request from user %s: %s", effective_user_id, query[:50])
        response = agent.run(request)
        return response
    except Exception as e:
        logger.error("Demo chat endpoint error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


# ==================== Session Management ====================

@app.get("/sessions")
async def list_user_sessions(
    limit: int = 20,
    user_id: str = Depends(get_current_user)
):
    """
    Get all chat sessions for the authenticated user.
    
    Requires: Authorization: Bearer <token>
    """
    try:
        sessions = get_user_sessions(user_id, limit)
        return {
            "user_id": user_id,
            "session_count": len(sessions),
            "sessions": sessions
        }
    except Exception as e:
        logger.error("Sessions list error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}/messages")
async def get_session_history(
    session_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get all messages in a session.
    
    Requires: Authorization: Bearer <token>
    Only returns messages if session belongs to authenticated user.
    """
    try:
        # Verify session belongs to user
        from app.utils.session_db import get_session
        session = get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if session["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        messages = get_session_messages(session_id)
        return {
            "session_id": session_id,
            "message_count": len(messages),
            "messages": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Session messages error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Feedback ====================

@app.post("/feedback")
async def submit_feedback(
    feedback: UserFeedback,
    user_id: str = Depends(get_current_user)
):
    """
    Submit user feedback on an assistant response.
    
    Requires: Authorization: Bearer <token>
    """
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
        "version": "3.0.0",
        "features": ["authentication", "database", "sessions"]
    }


@app.get("/metrics")
async def metrics(user_id: str = Depends(get_optional_user)):
    """
    Get system metrics.
    If authenticated, includes user-specific stats.
    """
    try:
        base_metrics = {
            "total_feedback": len(feedback_store),
            "avg_rating": sum(f["rating"] for f in feedback_store) / len(feedback_store) if feedback_store else 0
        }
        
        if user_id:
            sessions = get_user_sessions(user_id)
            base_metrics["user_sessions"] = len(sessions)
        
        return base_metrics
    except Exception as e:
        logger.error("Metrics error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
