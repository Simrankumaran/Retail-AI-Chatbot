"""MongoDB operations for chat sessions and messages."""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "retail_chatbot")

_mongo_client: Optional[MongoClient] = None
_db = None


def get_mongo_client() -> MongoClient:
    """Get or create MongoDB client."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)
    return _mongo_client


def get_db():
    """Get database instance."""
    global _db
    if _db is None:
        client = get_mongo_client()
        _db = client[MONGO_DB_NAME]
    return _db


def init_mongo_collections():
    """Initialize MongoDB collections and indexes."""
    db = get_db()
    
    # Create sessions collection with indexes
    sessions = db.sessions
    sessions.create_index("session_id", unique=True)
    sessions.create_index("user_id")
    sessions.create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)])
    
    # Create messages collection with indexes
    messages = db.messages
    messages.create_index([("session_id", ASCENDING), ("timestamp", ASCENDING)])
    messages.create_index("session_id")
    
    # Create users collection
    users = db.users
    users.create_index("user_id", unique=True)
    users.create_index("username", unique=True, sparse=True)
    
    print("MongoDB collections and indexes initialized")


def create_session(session_id: str, user_id: str, metadata: Optional[Dict] = None) -> bool:
    """Create a new chat session in MongoDB."""
    db = get_db()
    sessions = db.sessions
    
    now = datetime.utcnow()
    session_doc = {
        "session_id": session_id,
        "user_id": user_id,
        "created_at": now,
        "updated_at": now,
        "metadata": metadata or {},
        "message_count": 0
    }
    
    try:
        sessions.insert_one(session_doc)
        return True
    except DuplicateKeyError:
        # Session already exists
        return False


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session details from MongoDB."""
    db = get_db()
    sessions = db.sessions
    
    session = sessions.find_one({"session_id": session_id})
    if not session:
        return None
    
    # Convert ObjectId to string and datetime to ISO format
    session["_id"] = str(session["_id"])
    session["created_at"] = session["created_at"].isoformat()
    session["updated_at"] = session["updated_at"].isoformat()
    
    return session


def add_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict] = None
) -> str:
    """Add a message to a session in MongoDB. Returns message ID."""
    db = get_db()
    messages = db.messages
    sessions = db.sessions
    
    now = datetime.utcnow()
    message_doc = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": now,
        "metadata": metadata or {}
    }
    
    # Insert message
    result = messages.insert_one(message_doc)
    
    # Update session timestamp and message count
    sessions.update_one(
        {"session_id": session_id},
        {
            "$set": {"updated_at": now},
            "$inc": {"message_count": 1}
        }
    )
    
    return str(result.inserted_id)


def get_session_messages(session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get all messages for a session from MongoDB."""
    db = get_db()
    messages = db.messages
    
    cursor = messages.find({"session_id": session_id}).sort("timestamp", ASCENDING).limit(limit)
    
    result = []
    for msg in cursor:
        result.append({
            "id": str(msg["_id"]),
            "session_id": msg["session_id"],
            "role": msg["role"],
            "content": msg["content"],
            "timestamp": msg["timestamp"].isoformat(),
            "metadata": msg.get("metadata", {})
        })
    
    return result


def get_user_sessions(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get all sessions for a user from MongoDB."""
    db = get_db()
    sessions = db.sessions
    
    cursor = sessions.find({"user_id": user_id}).sort("updated_at", DESCENDING).limit(limit)
    
    result = []
    for session in cursor:
        result.append({
            "session_id": session["session_id"],
            "created_at": session["created_at"].isoformat(),
            "updated_at": session["updated_at"].isoformat(),
            "message_count": session.get("message_count", 0),
            "metadata": session.get("metadata", {})
        })
    
    return result


def delete_session(session_id: str) -> bool:
    """Delete a session and all its messages."""
    db = get_db()
    sessions = db.sessions
    messages = db.messages
    
    # Delete all messages
    messages.delete_many({"session_id": session_id})
    
    # Delete session
    result = sessions.delete_one({"session_id": session_id})
    
    return result.deleted_count > 0


def create_or_get_user(user_id: str, username: str = None, email: str = None) -> Dict[str, Any]:
    """Create user if doesn't exist, or update last login in MongoDB."""
    db = get_db()
    users = db.users
    
    now = datetime.utcnow()
    
    # Try to find existing user
    user = users.find_one({"user_id": user_id})
    
    if user:
        # Update last login
        users.update_one(
            {"user_id": user_id},
            {"$set": {"last_login": now}}
        )
        return {
            "user_id": user["user_id"],
            "username": user.get("username"),
            "email": user.get("email")
        }
    else:
        # Create new user
        user_doc = {
            "user_id": user_id,
            "username": username or f"user_{user_id}",
            "email": email,
            "created_at": now,
            "last_login": now,
            "is_active": True
        }
        
        try:
            users.insert_one(user_doc)
            return {
                "user_id": user_id,
                "username": username or f"user_{user_id}",
                "email": email
            }
        except DuplicateKeyError:
            # Race condition - user was created between find and insert
            user = users.find_one({"user_id": user_id})
            return {
                "user_id": user["user_id"],
                "username": user.get("username"),
                "email": user.get("email")
            }


def get_user_stats(user_id: str) -> Dict[str, Any]:
    """Get statistics for a user."""
    db = get_db()
    sessions = db.sessions
    messages = db.messages
    
    # Count sessions
    session_count = sessions.count_documents({"user_id": user_id})
    
    # Count total messages
    session_ids = [s["session_id"] for s in sessions.find({"user_id": user_id}, {"session_id": 1})]
    message_count = messages.count_documents({"session_id": {"$in": session_ids}})
    
    return {
        "user_id": user_id,
        "total_sessions": session_count,
        "total_messages": message_count
    }


def search_messages(user_id: str, query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search messages by content for a specific user."""
    db = get_db()
    sessions = db.sessions
    messages = db.messages
    
    # Get user's session IDs
    session_ids = [s["session_id"] for s in sessions.find({"user_id": user_id}, {"session_id": 1})]
    
    # Search messages
    cursor = messages.find({
        "session_id": {"$in": session_ids},
        "content": {"$regex": query, "$options": "i"}
    }).sort("timestamp", DESCENDING).limit(limit)
    
    result = []
    for msg in cursor:
        result.append({
            "id": str(msg["_id"]),
            "session_id": msg["session_id"],
            "role": msg["role"],
            "content": msg["content"],
            "timestamp": msg["timestamp"].isoformat()
        })
    
    return result


# Cleanup function
def close_mongo_connection():
    """Close MongoDB connection."""
    global _mongo_client, _db
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _db = None
