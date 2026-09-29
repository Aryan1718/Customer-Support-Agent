<!-- prettier-ignore -->
<div align="center">

# Customer Support Agent

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Frontend-61dafb?style=flat-square&logo=react&logoColor=111)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169e1?style=flat-square&logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-pytest-blue?style=flat-square)

An AI-powered customer support backend that handles ambiguous support requests with tool calling, short-lived conversation state, validation, and streaming status updates.

[Overview](#overview) | [Features](#features) | [Architecture](#architecture) | [Getting Started](#getting-started) | [API](#api) | [Testing](#testing)

</div>

## Overview

Customer Support Agent is a full-stack project for experimenting with a production-style customer support assistant. The backend is the main focus today: it can reason over customer support intents, collect missing information over multiple turns, call deterministic tools, validate final responses, and stream progress back to clients.

The assistant currently supports workflows around:

- Customer account lookup
- Order status lookup
- Refund evaluation
- Order update checks
- Support ticket creation

> [!NOTE]
> The frontend is currently a minimal Vite/React shell. The backend contains the core agent orchestration, session management, tool execution, validation, and streaming behavior.

## Features

- **OpenAI-compatible LLM layer**  
  Works with OpenAI-compatible providers through `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.

- **Tool-aware customer support workflows**  
  Tools are registered for customer lookup, order status, refunds, order updates, and ticket creation.

- **Ambiguous request handling**  
  The agent can detect missing parameters, keep an active tool in session state, and ask focused follow-up questions.

- **In-memory session management**  
  Short-lived browser/session-specific state with a 3-minute sliding TTL, lazy cleanup, collected params, conversation turns, active tool, and missing params.

- **Pydantic-backed validation**  
  Tool parameters, helper outputs, validator verdicts, and response models are validated with Pydantic.

- **Tool-result response validation**  
  Final customer-facing responses generated from tool results are checked by a validator LLM. High-severity contradictions fall back to safe grounded text.

- **Streaming API with progress events**  
  `POST /llm/chat/stream` returns Server-Sent Events for stages like planning, tool execution, validation, and final content chunks.

- **Focused test coverage**  
  Backend tests cover tools, session store, orchestration, response validation, streaming API behavior, guardrails, and LLM prompt/tool schemas.

## Architecture

```text
frontend/
  Vite + React app shell

backend/
  FastAPI API
  LLM provider abstraction
  Tool schemas and registry
  Tool parameter extraction and validation
  Conversation/session orchestration
  Tool-result response validation
  SSE streaming endpoint

database/
  SQLAlchemy models
  PostgreSQL connection helpers
  Table creation and seed scripts
  Semantic layer YAML files
```

High-level chat flow:

```text
Client request
  -> load/create session
  -> call LLM with recent session history
  -> plan tool turn
  -> collect missing params OR execute tool
  -> generate customer-facing tool result response
  -> validate final response
  -> store conversation turn
  -> return JSON or SSE stream
```

## Project Structure

```text
.
|-- backend/
|   |-- app/
|   |   |-- llm/              # LLM service, tools, orchestration, validation
|   |   |-- tools/            # Deterministic backend tool implementations
|   |   |-- main.py           # FastAPI routes
|   |   `-- session_store.py  # In-memory session manager
|   |-- tests/
|   |-- requirements.txt
|   `-- pytest.ini
|-- database/
|   |-- models.py
|   |-- connection.py
|   |-- create_tables.py
|   |-- seed_dummy_data.py
|   `-- semantic_layer/
|-- frontend/
|   `-- src/
|-- .env.example
`-- README.md
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ for the frontend shell
- PostgreSQL database URL, such as Neon
- An OpenAI-compatible LLM provider key

### 1. Clone and configure environment

```bash
git clone <your-repo-url>
cd Customer-Support-Agent
cp .env.example .env
```

Update `.env`:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB_NAME?sslmode=require
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-llm-api-key
LLM_MODEL=gpt-4.1-mini
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=1000
```

> [!TIP]
> `LLM_BASE_URL` can point to OpenAI, Groq, OpenRouter, Ollama, or any provider that supports the OpenAI-compatible chat completions API shape.

### 2. Install backend dependencies

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Create and seed the database

Run from the repository root:

```bash
python database/create_tables.py
python database/seed_dummy_data.py
```

The seed script inserts sample customers, orders, and tickets using the `example.test` email domain.

### 4. Start the backend

From `backend/`:

```bash
uvicorn app.main:app --reload
```

The API runs at:

```text
http://localhost:8000
```

Interactive docs:

```text
http://localhost:8000/docs
```

### 5. Start the frontend shell

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs at:

```text
http://localhost:5173
```

## API

### Health

```http
GET /health
GET /health/db
GET /health/llm
```

### Sessions

```http
POST /sessions
```

Creates a short-lived in-memory chat session.

Response:

```json
{
  "session_id": "generated-session-id",
  "expires_at": "2026-09-28T..."
}
```

### Chat

```http
POST /llm/chat
Content-Type: application/json
```

Request:

```json
{
  "session_id": "optional-session-id",
  "message": "I want a refund",
  "history": []
}
```

Response:

```json
{
  "session_id": "active-session-id",
  "content": "What email address is on the account? Also, what is the order ID?",
  "model": "gpt-4.1-mini",
  "tool_calls": []
}
```

### Streaming Chat

```http
POST /llm/chat/stream
Content-Type: application/json
Accept: text/event-stream
```

Returns Server-Sent Events:

```text
event: status
data: {"stage":"received"}

event: status
data: {"stage":"planning"}

event: status
data: {"stage":"executing_tool","detail":{"tool_name":"Refund"}}

event: content
data: {"delta":"Your "}

event: done
data: {"session_id":"...","content":"...","model":"...","tool_calls":[]}
```

> [!IMPORTANT]
> Tool-result responses are validated before content chunks are emitted. This prevents unsafe or contradictory tool-result text from being streamed to users before validation completes.

## Agent Behavior

The agent is designed around deterministic backend tools and validated LLM responses.

1. **Intent and parameter extraction**  
   The orchestration layer detects tool intent from LLM tool calls and lightweight text extraction.

2. **Missing information collection**  
   If required tool params are missing, the session stores `active_tool` and `last_missing_params`, then asks a targeted follow-up.

3. **Validated tool execution**  
   Tool params are built and validated with Pydantic before execution.

4. **Customer-facing response generation**  
   Tool output is passed back to the LLM to produce a natural response.

5. **Response validation**  
   A validator LLM returns strict JSON. High-severity contradictions use a safe fallback response; uncertain or malformed validator results fail open with logging.

## Testing

Run the non-live backend suite:

```bash
cd backend
python -m pytest -m "not live"
```

Run all tests, including live LLM connectivity tests:

```bash
python -m pytest
```

> [!NOTE]
> Live tests require valid LLM environment variables and network access.

## Current Status

Implemented:

- FastAPI backend
- PostgreSQL/SQLAlchemy models and seed data
- LLM service with OpenAI-compatible provider
- Tool schemas and deterministic tool implementations
- Tool parameter helpers with Pydantic validation
- In-memory session management with sliding TTL
- Ambiguous request orchestration
- Tool execution registry
- Response validation layer
- SSE streaming endpoint with status events
- Backend test suite

Not yet complete:

- Full frontend chat experience
- Persistent production session storage
- Auth/user accounts
- Deployment configuration
- External validator provider such as Jev

## Troubleshooting

### `DATABASE_URL is not set`

Create a `.env` file at the repository root and add `DATABASE_URL`.

### LLM health is unhealthy

Check:

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- Provider compatibility with OpenAI chat completions

### Live LLM test fails locally

The live test requires network access and real credentials. Use this for ordinary local validation:

```bash
python -m pytest -m "not live"
```

### Database connection issues with Neon

The connection helper automatically adds `sslmode=require` for PostgreSQL URLs, but the host/user/password/database must still be valid.
