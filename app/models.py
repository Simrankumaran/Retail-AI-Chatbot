"""Pydantic models for type safety and validation."""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Role of the message sender."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Represents a single chat message."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None


class ChatSession(BaseModel):
    """Represents a chat session."""
    session_id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    messages: List[ChatMessage] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class AgentRequest(BaseModel):
    """Request to the agent."""
    query: str = Field(..., min_length=1, max_length=1000)
    user_id: str = Field(..., pattern=r"^\d{4}$")  # 4-digit user ID
    session_id: Optional[str] = None
    include_history: bool = True


class AgentResponse(BaseModel):
    """Response from the agent."""
    response: str
    session_id: str
    user_id: str
    tools_used: List[str] = Field(default_factory=list)
    execution_time_ms: Optional[float] = None
    error: Optional[str] = None


class ToolCallResult(BaseModel):
    """Result from a tool call."""
    tool_name: str
    found: bool = True
    success: bool = True
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class UserFeedback(BaseModel):
    """User feedback on a response."""
    session_id: str
    message_index: int
    rating: int = Field(..., ge=1, le=5)  # 1-5 stars
    feedback_text: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
