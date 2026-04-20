# MongoDB Chat Storage - Complete Setup

## ✅ What's Been Created

### New Files for MongoDB:
1. **`app/utils/session_mongo.py`** - MongoDB operations (create session, add message, search, etc.)
2. **`app/agent_mongo.py`** - Agent with MongoDB persistence
3. **`app/api_mongo.py`** - Complete API with MongoDB chat storage
4. **`MONGODB_SETUP.md`** - Full MongoDB setup guide

### Updated Files:
- **`.env.example`** - Added MongoDB configuration
- **`requirements.txt`** - Added `pymongo==4.10.1`

---

## 🚀 Quick Start (3 Steps)

### Step 1: Install MongoDB

**Option A: Local (Development)**
```powershell
# Download from: https://www.mongodb.com/try/download/community
# Start MongoDB
mongod --dbpath="C:\data\db"
```

**Option B: Cloud (Production)**
- Free MongoDB Atlas: https://www.mongodb.com/cloud/atlas/register
- Get connection string, add to `.env`

### Step 2: Install Dependencies
```bash
.\.venv\Scripts\Activate.ps1
pip install pymongo==4.10.1
```

### Step 3: Run API
```bash
uvicorn app.api_mongo:app --reload --port 8000
```

✅ **Chat is now stored in MongoDB!**

---

## 📊 Architecture

### Hybrid Storage Model

```
┌─────────────────────────────────────┐
│     Your Retail AI Chatbot         │
├─────────────────────────────────────┤
│                                     │
│  SQLite (db/retail.db)             │
│  ├── Products                       │
│  ├── Orders                         │
│  └── User accounts                  │
│                                     │
│  MongoDB (retail_chatbot)           │
│  ├── Chat sessions                  │
│  ├── Chat messages                  │
│  └── Conversation history           │
│                                     │
└─────────────────────────────────────┘
```

**Why hybrid?**
- ✅ SQLite = Fast transactional data (orders, products)
- ✅ MongoDB = Flexible document data (conversations)

---

## 🎯 Usage Examples

### Demo Mode (No Auth)
```bash
curl -X POST "http://localhost:8000/chat/demo?query=Show%20laptops"
# Uses default user 2001, stores in MongoDB
```

### With Authentication
```bash
# 1. Login
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "2001"}' | jq -r '.access_token')

# 2. Chat (automatically saved to MongoDB)
curl -X POST "http://localhost:8000/chat?query=Show%20my%20orders" \
  -H "Authorization: Bearer $TOKEN"

# 3. View chat history
curl "http://localhost:8000/sessions" \
  -H "Authorization: Bearer $TOKEN"
```

### Search Your Chats
```bash
curl "http://localhost:8000/sessions/search?q=laptop" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📁 File Structure

```
app/
├── agent.py              # Original (hardcoded user 2001)
├── agent_v2.py          # Improved (sessions in memory)
├── agent_db.py          # With SQLite persistence
├── agent_mongo.py       # ✨ NEW: With MongoDB persistence
│
├── api.py               # Original API
├── api_v2.py           # Improved with sessions
├── api_auth.py         # With SQLite + auth
├── api_mongo.py        # ✨ NEW: With MongoDB + auth
│
├── models.py           # Pydantic models
├── auth.py             # Authentication
│
└── utils/
    ├── db.py                # SQLite (orders/products)
    ├── session_db.py        # SQLite sessions
    └── session_mongo.py     # ✨ NEW: MongoDB sessions
```

---

## 🔄 Migration Options

### Option 1: Direct Switch (Recommended)
```python
# In your main code, just import the MongoDB version:
from app.api_mongo import app  # instead of app.api

# Or update app/main.py:
from app.api_mongo import app
```

### Option 2: Run Both APIs
```bash
# SQLite API on port 8000
uvicorn app.api_auth:app --port 8000

# MongoDB API on port 8001
uvicorn app.api_mongo:app --port 8001
```

### Option 3: Gradual Migration
1. Keep existing API running
2. Switch to MongoDB for new sessions
3. Migrate old data with migration script

---

## 🎁 New Features with MongoDB

### 1. Full-Text Search
```bash
curl "http://localhost:8000/sessions/search?q=laptop"
# Searches all your messages for "laptop"
```

### 2. Advanced Stats
```bash
curl "http://localhost:8000/stats" \
  -H "Authorization: Bearer $TOKEN"

# Returns:
{
  "user_id": "2001",
  "total_sessions": 15,
  "total_messages": 87
}
```

### 3. Delete Sessions
```bash
curl -X DELETE "http://localhost:8000/sessions/session_123" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Flexible Metadata
```python
# Easily add custom fields without schema changes
add_message(
    session_id,
    "assistant",
    response,
    metadata={
        "tools_used": ["ProductSearch"],
        "confidence": 0.95,
        "model": "llama-3.3-70b",
        "custom_field": "anything"
    }
)
```

---

## ✅ Checklist

- [ ] MongoDB installed/Atlas configured
- [ ] `pymongo` installed: `pip install pymongo`
- [ ] `.env` updated with `MONGO_URI`
- [ ] API running: `uvicorn app.api_mongo:app --reload`
- [ ] Test: `curl http://localhost:8000/health`
- [ ] Try demo chat: `curl -X POST "localhost:8000/chat/demo?query=hello"`

---

## 🆘 Quick Help

**MongoDB not starting?**
```powershell
# Create data directory
New-Item -ItemType Directory -Path "C:\data\db" -Force

# Start MongoDB
mongod --dbpath="C:\data\db"
```

**Can't connect to MongoDB?**
- Check if MongoDB is running: `mongosh`
- Check `.env` has correct `MONGO_URI`
- Try: `MONGO_URI=mongodb://localhost:27017/`

**ImportError: No module named 'pymongo'?**
```bash
pip install pymongo==4.10.1
```

---

## 📚 Documentation

- Full MongoDB setup: [MONGODB_SETUP.md](MONGODB_SETUP.md)
- Authentication guide: [AUTH_EXPLAINED.md](AUTH_EXPLAINED.md)
- General improvements: [IMPROVEMENTS.md](IMPROVEMENTS.md)

---

## 🎉 Summary

**You asked for MongoDB chat storage - You got:**

1. ✅ **Complete MongoDB integration**
2. ✅ **Chat sessions in MongoDB**
3. ✅ **Chat messages in MongoDB**
4. ✅ **Search functionality**
5. ✅ **User statistics**
6. ✅ **Session management**
7. ✅ **Your original demo mode still works!**

**Hybrid architecture:**
- Products/Orders = SQLite (fast transactions)
- Chat/Conversations = MongoDB (flexible documents)

**Ready to use!** Just install MongoDB, run the API, and all your chats will be stored in MongoDB automatically! 🚀
