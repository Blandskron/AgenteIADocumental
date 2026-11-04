# ConversationServices

## Overview
ConversationServices is a FastAPI-based microservice responsible for managing chat conversations, messages, and their association with documents. It provides secure, authenticated RESTful endpoints for CRUD operations on conversations and messages, as well as linking documents to conversations. The service is designed for integration in a microservices architecture, supporting JWT authentication and PostgreSQL persistence.

## Features
- Create, list, update, and delete conversations
- Add, list, and manage messages within conversations
- Associate and disassociate documents with conversations
- JWT-based authentication (access token required)
- Health check endpoints
- CORS support for frontend integration

## API Endpoints

### Health
- `GET /api/v1/health` — Service health check
- `GET /api/v1/health/db` — Database connectivity check

### Conversations (Authenticated)
- `GET /api/v1/conversations` — List conversations (optionally include archived)
- `POST /api/v1/conversations` — Create a new conversation
- `GET /api/v1/conversations/{conversation_id}` — Get conversation details
- `PATCH /api/v1/conversations/{conversation_id}` — Update conversation (title, archived)
- `DELETE /api/v1/conversations/{conversation_id}` — Delete conversation

### Messages (Authenticated)
- `GET /api/v1/conversations/{conversation_id}/messages` — List messages in a conversation
- `POST /api/v1/conversations/{conversation_id}/messages` — Add a message to a conversation

### Documents (Authenticated)
- `GET /api/v1/conversations/{conversation_id}/documents` — List associated document IDs
- `POST /api/v1/conversations/{conversation_id}/documents/{document_id}` — Associate a document
- `DELETE /api/v1/conversations/{conversation_id}/documents/{document_id}` — Remove a document association

## Data Models

### Conversation
- `conversation_id`: str
- `owner_user_id`: str
- `title`: str
- `archived`: bool
- `metadata`: dict
- `created_at`: datetime
- `updated_at`: datetime

### Message
- `message_id`: str
- `conversation_id`: str
- `owner_user_id`: str
- `role`: "user" | "assistant" | "system"
- `content`: str
- `sources`: list
- `metadata`: dict
- `created_at`: datetime

### Document Association
- `conversation_id`: str
- `document_id`: str
- `owner_user_id`: str
- `created_at`: datetime

## Authentication
All endpoints (except health checks) require a valid JWT access token in the `Authorization: Bearer <token>` header. The token is validated using the configured RSA public key and must have `token_type: access`.

## Architecture
- **FastAPI** for API layer
- **SQLAlchemy** for ORM/database access
- **PostgreSQL** as the database
- **Pydantic** for request/response validation
- **Docker** for containerization
- **CORS** enabled for frontend integration

## Project Structure
- `app/main.py`: FastAPI app setup, middleware, error handling
- `app/interfaces/api/router.py`: API router and endpoint registration
- `app/interfaces/api/v1/routes/`: Endpoint implementations
- `app/application/use_cases/`: Business logic (use cases)
- `app/infrastructure/database/`: Models, repositories, DB connection
- `app/config/`: Settings, security, logging
- `app/shared/`: Shared error classes

## Running the Service
1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variables or edit config as needed
3. Run with Uvicorn: `uvicorn app.main:app --reload`
4. Or use Docker: `docker build -t conversation-services . && docker run ...`

## Example Requests

**Create Conversation**
```json
POST /api/v1/conversations
{
  "title": "Project Discussion",
  "metadata": {"project": "Alpha"}
}
```

**Add Message**
```json
POST /api/v1/conversations/{conversation_id}/messages
{
  "role": "user",
  "content": "Hello, team!",
  "sources": [],
  "metadata": {}
}
```

## License
This project is licensed under the terms of the repository's LICENSE file.
