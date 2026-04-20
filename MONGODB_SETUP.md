# MongoDB Setup for Chat Storage

## Why MongoDB for Chat?

✅ **Better for chat data** - Document-based storage perfectly fits conversation structure  
✅ **Scalable** - Handles millions of messages easily  
✅ **Fast queries** - Indexed searches on user, session, timestamps  
✅ **Flexible** - Easy to add metadata without schema changes  
✅ **Production-ready** - MongoDB Atlas for cloud deployment  

---

## Quick Start

### Option 1: Local MongoDB (Development)

#### Install MongoDB Community Edition

**Windows:**
```powershell
# Download from: https://www.mongodb.com/try/download/community
# Or use Chocolatey:
choco install mongodb

# Start MongoDB
mongod --dbpath="C:\data\db"
```

**Linux/Mac:**
```bash
# Ubuntu
sudo apt-get install mongodb

# Mac
brew install mongodb-community

# Start MongoDB
mongod --dbpath=/data/db
```

#### Verify MongoDB is Running
```bash
# Open MongoDB shell
mongosh

# Should connect to mongodb://127.0.0.1:27017
```

---

### Option 2: MongoDB Atlas (Cloud - Free Tier)

1. Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register)
2. Create free cluster (512MB free)
3. Create database user
4. Whitelist your IP (or use 0.0.0.0/0 for development)
5. Get connection string:
   ```
   mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
   ```

Update `.env`:
```env
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=retail_chatbot
```

---

## Install pymongo

```bash
# Activate your virtualenv
.\.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate      # Linux/Mac

# Install pymongo
pip install pymongo==4.10.1
```

---

## MongoDB Collections Structure

### `sessions` Collection
```json
{
  "_id": ObjectId("..."),
  "session_id": "session_2001_abc123",
  "user_id": "2001",
  "created_at": ISODate("2026-03-15T10:00:00Z"),
  "updated_at": ISODate("2026-03-15T10:30:00Z"),
  "message_count": 10,
  "metadata": {
    "device": "web",
    "ip": "192.168.1.1"
  }
}
```

### `messages` Collection
```json
{
  "_id": ObjectId("..."),
  "session_id": "session_2001_abc123",
  "role": "user",  // or "assistant"
  "content": "Show me my orders",
  "timestamp": ISODate("2026-03-15T10:00:00Z"),
  "metadata": {
    "tools_used": ["MyOrdersTool"]
  }
}
```

### `users` Collection
```json
{
  "_id": ObjectId("..."),
  "user_id": "2001",
  "username": "user_2001",
  "email": "user@example.com",
  "created_at": ISODate("2026-03-15T08:00:00Z"),
  "last_login": ISODate("2026-03-15T10:00:00Z"),
  "is_active": true
}
```

---

## Run API with MongoDB

```bash
# Start MongoDB (if local)
mongod --dbpath="C:\data\db"

# In another terminal, start API
uvicorn app.api_mongo:app --reload --port 8000
```

---

## API Endpoints (MongoDB Version)

### Chat (Demo Mode)
```bash
curl -X POST "http://localhost:8000/chat/demo?query=Show%20laptops&user_id=2001"
```

### Chat (Authenticated)
```bash
# 1. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "2001"}'

# Response: {"access_token": "abc123...", ...}

# 2. Chat
curl -X POST "http://localhost:8000/chat?query=Show%20my%20orders" \
  -H "Authorization: Bearer abc123..."
```

### Get Sessions
```bash
curl http://localhost:8000/sessions \
  -H "Authorization: Bearer abc123..."
```

### Get Messages in Session
```bash
curl http://localhost:8000/sessions/session_2001_abc123/messages \
  -H "Authorization: Bearer abc123..."
```

### Search Messages
```bash
curl "http://localhost:8000/sessions/search?q=laptop" \
  -H "Authorization: Bearer abc123..."
```

### Delete Session
```bash
curl -X DELETE http://localhost:8000/sessions/session_2001_abc123 \
  -H "Authorization: Bearer abc123..."
```

### Get User Stats
```bash
curl http://localhost:8000/stats \
  -H "Authorization: Bearer abc123..."
```

---

## MongoDB Queries (Manual)

Connect to MongoDB shell:
```bash
mongosh

use retail_chatbot
```

### View all sessions for a user
```javascript
db.sessions.find({user_id: "2001"}).sort({updated_at: -1})
```

### View all messages in a session
```javascript
db.messages.find({session_id: "session_2001_abc123"}).sort({timestamp: 1})
```

### Count total messages
```javascript
db.messages.countDocuments()
```

### Search messages by content
```javascript
db.messages.find({content: /laptop/i}).limit(10)
```

### Get user statistics
```javascript
db.sessions.aggregate([
  {$match: {user_id: "2001"}},
  {$group: {
    _id: "$user_id",
    total_sessions: {$sum: 1},
    total_messages: {$sum: "$message_count"}
  }}
])
```

### Delete old sessions (older than 30 days)
```javascript
const thirtyDaysAgo = new Date(Date.now() - 30*24*60*60*1000);
db.sessions.deleteMany({updated_at: {$lt: thirtyDaysAgo}})
```

---

## Advantages vs SQLite for Chat

| Feature | SQLite chats | MongoDB chats |
|---------|-------------|---------------|
| **Scalability** | Limited | Millions of messages |
| **Schema** | Fixed | Flexible |
| **Metadata** | Hard to add | Easy JSON fields |
| **Search** | Basic | Full-text search |
| **Cloud** | Manual backup | Built-in (Atlas) |
| **Replication** | None | Auto replication |
| **Concurrent writes** | Limited | Excellent |

**Recommendation:** 
- SQLite for: orders, products, users (transactional data)
- MongoDB for: chats, logs, events (document data)

---

## Production Considerations

### Indexes (created automatically by `init_mongo_collections()`)
```python
sessions.create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)])
messages.create_index([("session_id", ASCENDING), ("timestamp", ASCENDING)])
```

### Backup Strategy
```bash
# Backup
mongodump --uri="mongodb://localhost:27017" --db=retail_chatbot --out=/backup

# Restore
mongorestore --uri="mongodb://localhost:27017" /backup
```

### Monitor Performance
```javascript
// In mongosh
db.sessions.stats()
db.messages.stats()
db.currentOp()  // See running queries
```

---

## Migration from SQLite to MongoDB

If you have existing chat data in SQLite:

```python
# migration_script.py
from app.utils.session_db import get_all_sessions  # SQLite
from app.utils.session_mongo import create_session, add_message  # MongoDB

sqlite_sessions = get_all_sessions()
for session in sqlite_sessions:
    create_session(session['session_id'], session['user_id'])
    for msg in get_sqlite_messages(session['session_id']):
        add_message(
            session['session_id'],
            msg['role'],
            msg['content'],
            msg['metadata']
        )
```

---

## Troubleshooting

### Connection Error
```
pymongo.errors.ServerSelectionTimeoutError
```
**Fix:** Check if MongoDB is running (`mongod`)

### Authentication Failed
```
pymongo.errors.OperationFailure: Authentication failed
```
**Fix:** Check MONGO_URI username/password in `.env`

### Database Not Found
**Normal!** MongoDB creates databases on first write automatically.

---

## Next Steps

1. ✅ Install MongoDB or use Atlas
2. ✅ Install pymongo: `pip install pymongo`
3. ✅ Update `.env` with MONGO_URI
4. ✅ Run API: `uvicorn app.api_mongo:app --reload`
5. ✅ Test: `curl http://localhost:8000/health`

**Your chat data is now in MongoDB!** 🎉
