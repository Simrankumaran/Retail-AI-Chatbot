"""Simple authentication and session management."""
from typing import Optional, Dict
from datetime import datetime, timedelta
import secrets
import hashlib
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.utils.session_db import create_or_get_user


# Simple in-memory token store (use Redis in production)
_active_tokens: Dict[str, Dict] = {}

security = HTTPBearer()


class LoginRequest(BaseModel):
    """Login request payload."""
    user_id: str
    # In production, add password, etc.


class LoginResponse(BaseModel):
    """Login response with token."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    expires_in: int = 3600


def generate_token(user_id: str) -> str:
    """Generate a secure token for user."""
    # Create token: hash(user_id + secret + timestamp)
    secret = secrets.token_urlsafe(32)
    token_data = f"{user_id}:{secret}:{datetime.utcnow().isoformat()}"
    token = hashlib.sha256(token_data.encode()).hexdigest()
    
    # Store token with expiry (1 hour)
    _active_tokens[token] = {
        "user_id": user_id,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=1)
    }
    
    return token


def validate_token(token: str) -> Optional[str]:
    """Validate token and return user_id if valid."""
    token_data = _active_tokens.get(token)
    
    if not token_data:
        return None
    
    # Check expiry
    if datetime.utcnow() > token_data["expires_at"]:
        del _active_tokens[token]
        return None
    
    return token_data["user_id"]


def login_user(user_id: str) -> LoginResponse:
    """Login user and return token."""
    # Create or get user in DB
    user = create_or_get_user(user_id)
    
    # Generate token
    token = generate_token(user_id)
    
    return LoginResponse(
        access_token=token,
        user_id=user_id,
        expires_in=3600
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Dependency to extract authenticated user from request.
    Use this in endpoints to automatically get user_id.
    
    Example:
        @app.get("/my-orders")
        async def my_orders(user_id: str = Depends(get_current_user)):
            # user_id is automatically extracted from token
    """
    token = credentials.credentials
    user_id = validate_token(token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_id


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[str]:
    """
    Optional authentication - returns user_id if authenticated, None otherwise.
    Use this for endpoints that work with or without auth.
    """
    if not credentials:
        return None
    
    return validate_token(credentials.credentials)


# For backward compatibility / demo mode
def get_default_user() -> str:
    """Return default user for demo/testing (your original approach)."""
    return "2001"
