# Customer Support Agent

Full-stack customer support assistant with a React frontend, FastAPI backend, PostgreSQL database, LLM tool calling, and Docker Compose setup.

## What It Does

- Chats with users about support requests
- Looks up customer account information
- Checks order status
- Evaluates refund requests
- Checks whether an order can be updated
- Creates support tickets
- Streams backend progress to the frontend while the assistant works

## Tech Stack

- Frontend: React, Vite, Nginx
- Backend: FastAPI, Python
- Database: PostgreSQL, SQLAlchemy
- LLM: OpenAI-compatible chat completions API
- Containers: Docker, Docker Compose

## Project Structure

```text
.
|-- backend/              # FastAPI app, LLM orchestration, tools, tests
|-- database/             # SQLAlchemy models, DB connection, seed scripts
|-- frontend/             # React app and frontend Docker config
|-- docker-compose.yml
|-- .env.example
`-- README.md
```

## Setup

Create a `.env` file:

```bash
cp .env.example .env
```

Update the values:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB_NAME?sslmode=require

LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-llm-api-key
LLM_MODEL=gpt-4.1-mini
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=1000

VITE_API_BASE_URL=http://localhost:8000
```

Create and seed the database once:

```bash
python database/create_tables.py
python database/seed_dummy_data.py
```

## Run With Docker

Start both frontend and backend:

```bash
docker compose up --build
```

Open:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
API docs: http://localhost:8000/docs
```

Stop the app:

```bash
docker compose down
```

## Run Locally Without Docker

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

On macOS/Linux, use:

```bash
source .venv/bin/activate
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## API

Health:

```http
GET /health
GET /health/db
GET /health/llm
```

Create session:

```http
POST /sessions
```

Chat:

```http
POST /llm/chat
```

Request:

```json
{
  "session_id": "optional-session-id",
  "message": "I want a refund",
  "history": []
}
```

Streaming chat:

```http
POST /llm/chat/stream
```

The streaming endpoint returns Server-Sent Events:

```text
event: status
data: {"stage":"planning"}

event: content
data: {"delta":"Your "}

event: done
data: {"session_id":"...","content":"...","model":"...","tool_calls":[]}
```

## Tests

Run backend tests:

```bash
cd backend
python -m pytest -m "not live"
```

Run frontend build:

```bash
cd frontend
npm install
npm run build
```

Check Docker Compose config:

```bash
docker compose config
```

## Troubleshooting

If Docker cannot connect to the daemon, start Docker Desktop and retry.

If the frontend cannot reach the backend, make sure `VITE_API_BASE_URL` points to `http://localhost:8000` and rebuild the frontend container.

If `/health/db` fails, check `DATABASE_URL`.

If `/health/llm` fails, check `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`.
