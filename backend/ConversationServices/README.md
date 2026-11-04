# ConversationServices

## Overview
ConversationServices is a FastAPI microservice for chat conversations, messages, and document associations. It authenticates requests with AuthServices access tokens and stores data in PostgreSQL.

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

Only the conversation owner can manage its associations. Linking requires current document access and returns the same `404` for missing and inaccessible resources. Repeated links succeed without creating duplicates. Listing hides documents the owner can no longer access. The owner can still remove an existing association after access is revoked.

Document access follows ownership, tenant administration, group membership, assignment and superadmin rules, including legacy document metadata. Cancelled and expired assignments do not grant access to conversation links.

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
The conversation API requires an AuthServices access token in the `Authorization: Bearer <token>` header. The service verifies the signature with the configured RSA public key and requires `token_type: access`, a future integer `exp` and a positive integer `user_id`. It uses that ID for conversation ownership, message ownership and user-specific document access. Health checks are public.

Existing rows owned by the numeric AuthServices ID retain the same owner. Rows recorded under a legacy username or placeholder require an explicit ownership review before reassignment.

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

From the repository root, follow the [local setup](../../README.md) and start the service with PostgreSQL and AuthServices:

```sh
docker compose -f docker/docker-compose.yml config --quiet
docker compose -f docker/docker-compose.yml up -d --build --wait conversation-service
curl http://localhost:8008/api/v1/health
curl http://localhost:8008/api/v1/health/db
```

Compose passes only the service settings and mounts the public verification key read-only. The local frontend origins are `http://localhost:3000` and `http://127.0.0.1:3000`. Override them with `CONVERSATION_CORS_ORIGINS` as a JSON array in the root Compose environment if needed.

For standalone development, run from this directory. Install `requirements.txt`, point `DATABASE_URL` at a PostgreSQL database with the repository schema, and set `AUTH_JWT_PUBLIC_KEY_PATH` to the public key issued by AuthServices. Set `CORS_ORIGINS` as a JSON array to override the defaults. Uvicorn reads settings from the process environment or the service-local `.env`.

```sh
python -m uvicorn app.main:app --reload --port 8008
```

Run the JWT, ownership and document-link tests against the local Compose database. The tests use an ephemeral RSA key and create and clean up synthetic records.

```sh
docker compose -f docker/docker-compose.yml cp backend/ConversationServices/requirements-test.txt conversation-service:/app/requirements-test.txt
docker compose -f docker/docker-compose.yml cp backend/ConversationServices/tests/test_conversations.py conversation-service:/app/test_conversations.py
docker compose -f docker/docker-compose.yml exec -T conversation-service python -m pip install -r requirements-test.txt
docker compose -f docker/docker-compose.yml exec -T conversation-service python -m pytest -q test_conversations.py
```

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
