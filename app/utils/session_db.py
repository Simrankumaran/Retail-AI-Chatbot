"""Database operations for chat sessions and messages."""
import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.utils.db import get_connection, get_cursor


def init_session_schema():
    """Create tables for sessions and messages if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)
    
    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
        )
    """)
    
    # Index for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_session 
        ON chat_messages(session_id, timestamp)
    """)
    
    # Users table (simple auth)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            email TEXT,
            created_at TEXT NOT NULL,
            last_login TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    conn.commit()


def create_session(session_id: str, user_id: str, metadata: Optional[Dict] = None) -> bool:
    """Create a new chat session."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        
        cursor.execute("""
            INSERT INTO chat_sessions (session_id, user_id, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, user_id, now, now, json.dumps(metadata or {})))
        
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Session already exists
        return False


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session details."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT session_id, user_id, created_at, updated_at, metadata
        FROM chat_sessions
        WHERE session_id = ?
    """, (session_id,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    return {
        "session_id": row[0],
        "user_id": row[1],
        "created_at": row[2],
        "updated_at": row[3],
        "metadata": json.loads(row[4]) if row[4] else {}
    }


def add_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict] = None
) -> int:
    """Add a message to a session. Returns message ID."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    cursor.execute("""
        INSERT INTO chat_messages (session_id, role, content, timestamp, metadata)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, role, content, now, json.dumps(metadata or {})))
    
    # Update session timestamp
    cursor.execute("""
        UPDATE chat_sessions
        SET updated_at = ?
        WHERE session_id = ?
    """, (now, session_id))
    
    conn.commit()
    return cursor.lastrowid


def get_session_messages(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get all messages for a session."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT id, role, content, timestamp, metadata
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY timestamp ASC
        LIMIT ?
    """, (session_id, limit))
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "id": row[0],
            "role": row[1],
            "content": row[2],
            "timestamp": row[3],
            "metadata": json.loads(row[4]) if row[4] else {}
        })
    
    return messages


def get_user_sessions(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get all sessions for a user."""
    cursor = get_cursor()
    cursor.execute("""
        SELECT session_id, created_at, updated_at,
               (SELECT COUNT(*) FROM chat_messages WHERE session_id = chat_sessions.session_id) as message_count
        FROM chat_sessions
        WHERE user_id = ?
        ORDER BY updated_at DESC
        LIMIT ?
    """, (user_id, limit))
    
    sessions = []
    for row in cursor.fetchall():
        sessions.append({
            "session_id": row[0],
            "created_at": row[1],
            "updated_at": row[2],
            "message_count": row[3]
        })
    
    return sessions


def create_or_get_user(user_id: str, username: str = None, email: str = None) -> Dict[str, Any]:
    """Create user if doesn't exist, or update last login."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    
    # Check if user exists
    cursor.execute("SELECT user_id, username, email FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row:
        # Update last login
        cursor.execute("""
            UPDATE users SET last_login = ? WHERE user_id = ?
        """, (now, user_id))
        conn.commit()
        return {"user_id": row[0], "username": row[1], "email": row[2]}
    else:
        # Create new user
        cursor.execute("""
            INSERT INTO users (user_id, username, email, created_at, last_login)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username or f"user_{user_id}", email, now, now))
        conn.commit()
        return {"user_id": user_id, "username": username or f"user_{user_id}", "email": email}
