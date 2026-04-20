"""Enhanced API with proper request/response models and session support."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import time

from app.agent_v2 import get_agent
from app.models import AgentRequest, AgentResponse, UserFeedback
from app.utils.db import init_db_schema

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Retail AI Chatbot API")
    init_db_schema()
    logger.info("Database schema initialized")
    yield
    logger.info("Shutting down Retail AI Chatbot API")


app = FastAPI(
    title="Retail AI Chatbot API",
    description="AI-powered retail assistant with multi-user support",
    version="2.0.0",
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
agent = get_agent()

# In-memory feedback storage (move to DB later)
feedback_store = []


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()
    response = await call_next(request)
    duration = (time.time() - start_time) * 1000
    logger.info(
        "%s %s - Status: %d - Duration: %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration
    )
    return response


@app.post("/chat", response_model=AgentResponse)
async def chat(request: AgentRequest):
    """
    Process a chat query from a user.
    
    - **query**: User's question or request
    - **user_id**: 4-digit user identifier
    - **session_id**: Optional session ID for conversation continuity
    - **include_history**: Whether to include conversation history (default: true)
    """
    try:
        logger.info("Chat request from user %s: %s", request.user_id, request.query[:50])
        response = agent.run(request)
        return response
    except Exception as e:
        logger.error("Chat endpoint error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.post("/feedback")
async def submit_feedback(feedback: UserFeedback):
    """
    Submit user feedback on an assistant response.
    
    - **session_id**: Session identifier
    - **message_index**: Index of the message being rated
    - **rating**: Rating from 1-5 stars
    - **feedback_text**: Optional feedback comments
    """
    try:
        feedback_store.append(feedback.dict())
        logger.info(
            "Feedback received - session: %s, rating: %d",
            feedback.session_id,
            feedback.rating
        )
        return {"status": "success", "message": "Feedback recorded"}
    except Exception as e:
        logger.error("Feedback endpoint error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error recording feedback: {str(e)}")


@app.get("/session/{session_id}/history")
async def get_session_history(session_id: str):
    """Get conversation history for a session."""
    try:
        history = agent.get_session_history(session_id)
        return {
            "session_id": session_id,
            "message_count": len(history),
            "messages": [msg.dict() for msg in history]
        }
    except Exception as e:
        logger.error("Session history error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving history: {str(e)}")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "retail-ai-chatbot",
        "version": "2.0.0"
    }


@app.get("/metrics")
async def metrics():
    """Get basic metrics (placeholder for now)."""
    return {
        "total_sessions": len(agent.sessions),
        "total_feedback": len(feedback_store),
        "avg_rating": sum(f["rating"] for f in feedback_store) / len(feedback_store) if feedback_store else 0
    }
