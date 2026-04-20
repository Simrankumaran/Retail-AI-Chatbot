# Authentication & Database Persistence - Explained

## Your Questions Answered ✅

### 1. **"Will chat be stored in DB?"**
**YES! Now it is.** ✅

**Before:**
```python
self.sessions: Dict[str, ChatSession] = {}  # ❌ In memory - lost on restart
```

**After:**
```python
# In session_db.py - stored in SQLite
CREATE TABLE chat_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    ...
)

CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    role TEXT,
    content TEXT,
    ...
)
```

**Every message is now saved to the database permanently!**

---

### 2. **"How will you know which user has logged in?"**
**Through authentication tokens!** 🔑

**Your Original Approach (makes sense for demo):**
```python
SYSTEM_PROMPT = "You are a helpful retail assistant for USER 2001..."
# Hardcoded - works for single user MVP
```

**Production Approach:**
```python
# 1. User logs in
POST /auth/login
{"user_id": "2001"}
→ Returns: {"access_token": "abc123..."}

# 2. User makes requests with token
POST /chat
Headers: Authorization: Bearer abc123...
Body: {"query": "Show my orders"}

# 3. API automatically extracts user_id from token
async def chat(user_id: str = Depends(get_current_user)):
    # user_id = "2001" (from token)
```

---

## How It Works - Complete Flow

### Step 1: User Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "2001"}'
```
**Response:**
```json
{
  "access_token": "abc123def456...",
  "token_type": "bearer",
  "user_id": "2001",
  "expires_in": 3600
}
```

### Step 2: User Chats (Authenticated)
```bash
curl -X POST http://localhost:8000/chat?query=Show%20my%20orders \
  -H "Authorization: Bearer abc123def456..."
```

**What happens:**
1. ✅ API validates token
2. ✅ Extracts user_id = "2001" from token
3. ✅ Creates/gets session from **database**
4. ✅ Loads conversation history from **database**
5. ✅ Runs agent for user 2001
6. ✅ Saves message to **database**
7. ✅ Returns response

**Response:**
```json
{
  "response": "Here are your recent orders...",
  "session_id": "session_123",
  "user_id": "2001",
  "tools_used": ["MyOrdersTool"],
  "execution_time_ms": 1250.5
}
```

### Step 3: View Session History
```bash
curl http://localhost:8000/sessions \
  -H "Authorization: Bearer abc123..."
```
**Returns all chat sessions from database!**

---

## Database Tables Created

### `users` - User accounts
```sql
user_id | username  | email          | created_at | last_login
2001    | user_2001 | user@email.com | 2026-03-15 | 2026-03-15
2002    | user_2002 | null           | 2026-03-14 | 2026-03-14
```

### `chat_sessions` - Conversation sessions
```sql
session_id    | user_id | created_at | updated_at
session_abc   | 2001    | 2026-03-15 | 2026-03-15
session_xyz   | 2002    | 2026-03-14 | 2026-03-15
```

### `chat_messages` - Every message saved
```sql
id | session_id  | role      | content              | timestamp
1  | session_abc | user      | Show my orders       | 2026-03-15 10:00
2  | session_abc | assistant | Here are your...     | 2026-03-15 10:01
3  | session_abc | user      | Cancel order ABC123  | 2026-03-15 10:05
4  | session_abc | assistant | Order cancelled...   | 2026-03-15 10:06
```

**✅ Everything persists!** Even if server restarts, all conversations are saved.

---

## Two Modes Available

### Mode 1: **Production Mode (with Auth)** 🔐
```python
# Requires login + token
@app.post("/chat")
async def chat(user_id: str = Depends(get_current_user)):
    # user_id automatically extracted from token
```

**Use this when:**
- You have real users
- You need security
- You want user isolation

### Mode 2: **Demo Mode (like your original)** 🎮
```python
# No auth required, can specify user_id or default to 2001
@app.post("/chat/demo")
async def chat_demo(user_id: str = None):
    user_id = user_id or "2001"  # Your original approach!
```

**Use this when:**
- Testing/development
- MVP without auth
- Maintaining your current behavior

---

## Migration Path

### Option A: Keep Your Original Behavior (Easiest)
```python
# Just use /chat/demo endpoint - works exactly like before!
POST /chat/demo
Body: {"query": "Show laptops"}
# Defaults to user 2001, no auth needed
```

### Option B: Add Authentication (Production Ready)
```python
# 1. User logs in once
POST /auth/login → get token

# 2. Use token for all requests
POST /chat with Bearer token → automatic user_id
```

---

## Files Created

1. **`app/utils/session_db.py`** - Database operations for sessions/messages
2. **`app/auth.py`** - Authentication & token management
3. **`app/agent_db.py`** - Agent with database persistence
4. **`app/api_auth.py`** - Complete API with both modes

---

## Quick Start

### Run the new API:
```bash
uvicorn app.api_auth:app --reload --port 8000
```

### Test Demo Mode (works like your original):
```bash
curl -X POST "http://localhost:8000/chat/demo?query=Show%20laptops"
# Uses user 2001 by default
```

### Test Auth Mode:
```bash
# 1. Login
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "2001"}' | jq -r '.access_token')

# 2. Chat
curl -X POST "http://localhost:8000/chat?query=Show%20my%20orders" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Summary

**Your concerns were 100% valid!**

1. ✅ **Chat IS stored in database** (SQLite tables)
2. ✅ **User authentication** via tokens (or demo mode with default user)
3. ✅ **Your original approach still works** via `/chat/demo`
4. ✅ **Production-ready auth** available when needed

You can **start with demo mode** (like your hardcoded 2001) and **upgrade to auth later**!
