<!-- prettier-ignore -->
<div align="center">

# Customer Support Agent

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-Frontend-61dafb?style=flat-square&logo=react&logoColor=111)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169e1?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=flat-square&logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-pytest-blue?style=flat-square)

A customer support agent built around a custom Python agent harness: tool routing, parameter collection, session state, response validation, and streaming updates are implemented directly in this repo instead of using an agent framework.

</div>

## What We Built

- Custom agent harness for routing support requests to backend tools
- OpenAI-compatible LLM provider layer
- Tool registry for customer lookup, order status, refunds, order updates, and ticket creation
- Parameter extraction and follow-up handling for missing user details
- Session state for multi-turn support flows
- Response validation before tool-based answers are streamed back
- React chat console with backend health checks and live progress events
- Docker Compose setup for running the frontend and backend together

## Backend Architecture

The backend is organized as a small FastAPI API around a custom agent harness. The API layer stays thin: it accepts chat requests, streams progress events, and delegates the actual support-agent work to the LLM service, planner, tool registry, session store, validators, and telemetry layer.

```mermaid
flowchart TD
    Client[Frontend chat UI] --> API[FastAPI API layer]
    API --> Session[In-memory session store]
    API --> LLM[LLM service]
    LLM --> Provider[OpenAI-compatible provider]
    LLM --> Guardrails[User and assistant guardrails]
    LLM --> Schemas[Customer support tool schemas]
    API --> Planner[Tool turn planner]
    Planner --> Extractor[Parameter extraction]
    Planner --> Params[Required parameter validation]
    Planner --> FollowUp[Follow-up prompt builder]
    Planner --> Registry[Tool registry]
    Registry --> CustomerTool[Customer tool]
    Registry --> OrderTool[Order tools]
    Registry --> RefundTool[Refund tool]
    Registry --> TicketTool[Ticket tool]
    CustomerTool --> DB[(PostgreSQL)]
    OrderTool --> DB
    RefundTool --> DB
    TicketTool --> DB
    API --> Validator[Tool response validator]
    API --> Telemetry[OpenTelemetry and Datadog events]
```

### Backend Layers

| Layer | Main files | Responsibility |
| --- | --- | --- |
| API edge | `backend/app/main.py` | Defines health checks, session creation, non-streaming chat, and SSE streaming chat endpoints. It also runs the full chat pipeline. |
| LLM service | `backend/app/llm/service.py`, `backend/app/llm/providers/` | Applies guardrails, builds messages with the system prompt and tool schemas, and calls any OpenAI-compatible chat completions provider. |
| Agent harness | `backend/app/llm/tool_orchestrator.py` | Converts an LLM turn into one of three deterministic actions: no tool, ask a follow-up question, or execute a backend tool. |
| Parameter layer | `backend/app/llm/parameter_extraction.py`, `backend/app/llm/tool_params.py` | Combines LLM tool-call arguments, keyword detection, regex extraction, active session context, aliases, and Pydantic validation before any tool runs. |
| Tool layer | `backend/app/llm/tool_registry.py`, `backend/app/tools/` | Maps tool names to Python functions for customer lookup, order status, order update, refund decisioning, and ticket creation. |
| Data layer | `database/connection.py`, `database/models.py` | Uses SQLAlchemy models and a pooled PostgreSQL engine with Neon-friendly defaults such as `sslmode=require`. |
| Session layer | `backend/app/session_store.py` | Keeps short-lived multi-turn state: collected parameters, active tool, missing fields, and recent conversation turns. |
| Validation layer | `backend/app/llm/response_validation.py` | Checks customer-facing tool responses against verified tool results and falls back only on high-severity unsupported claims. |
| Observability | `backend/app/telemetry/`, `backend/app/datadog_observability/` | Emits structured agent events, trace context, span events, and optional Datadog LLM observability annotations. |
| Test harness | `backend/tests/` | Covers orchestration, parameter extraction, tool params, tool registry, tool behavior, sessions, validation, telemetry, and live-LLM boundaries. |

### Chat Turn Lifecycle

```mermaid
sequenceDiagram
    participant UI as Frontend
    participant API as FastAPI
    participant Store as Session Store
    participant LLM as LLM Service
    participant Planner as Tool Planner
    participant Tools as Tool Registry
    participant DB as PostgreSQL
    participant Validator as Response Validator

    UI->>API: POST /llm/chat or /llm/chat/stream
    API->>Store: Get or create session
    API->>LLM: Send user message, history, system prompt, tool schemas
    LLM-->>API: Assistant content and optional tool calls
    API->>Planner: Plan the turn from tool calls, text, and session context
    Planner-->>API: no_tool, ask_follow_up, or execute_tool

    alt Missing required parameters
        API->>Store: Save active tool and collected params
        API-->>UI: Focused follow-up question
    else Tool ready
        API->>Store: Save collected params and clear active tool
        API->>Tools: Execute validated tool params
        Tools->>DB: Query or mutate support data
        DB-->>Tools: Verified result
        Tools-->>API: Tool result
        API->>LLM: Generate response from verified result only
        API->>Validator: Validate response against tool result
        Validator-->>API: Allowed, warning, or fallback content
        API->>Store: Store conversation turn
        API-->>UI: Final answer
    else No backend tool needed
        API->>Store: Store conversation turn
        API-->>UI: Direct answer
    end
```

### Custom Agent Harness

The core backend effort is the custom harness in `backend/app/llm/`. Instead of handing control to a third-party agent framework, the app makes each step explicit:

1. The model receives customer-support tool schemas from `tool_schemas.py`.
2. The first LLM call can return normal text, tool calls, or both.
3. `plan_tool_turn()` merges LLM tool-call arguments, regex extraction, keyword intent detection, and previous session context.
4. `get_missing_tool_params()` checks the selected tool's required schema fields before execution.
5. If information is missing, `build_follow_up_prompt()` asks one focused question and `session_store.py` remembers the active tool.
6. If the tool is ready, `build_tool_params()` creates a strict Pydantic model from the tool schema and validates/coerces parameters.
7. `execute_tool_plan()` calls the registry, not the model, so database reads and writes happen through controlled Python functions.
8. The backend asks the LLM to turn the verified tool result into a customer-facing answer.
9. `validate_tool_response()` checks that final answer against the verified result before the response is returned or streamed.

This makes the agent flow inspectable and testable: intent detection, parameter collection, tool execution, response generation, and response validation can each be tested independently.

### Streaming And Progress Events

`POST /llm/chat/stream` runs the same pipeline as `POST /llm/chat`, but wraps it with Server-Sent Events. The stream reports stages such as `loading_session`, `calling_llm`, `planning`, `collecting_missing_information`, `executing_tool`, `generating_tool_response`, `validating_response`, and `storing_conversation` before sending the final content chunks.

That means the frontend can show real progress without owning backend logic, and both streaming and non-streaming requests share the same source of truth.

### Backend Tools

| Tool name | File | What it does |
| --- | --- | --- |
| `customerInformation` | `backend/app/tools/customers.py` | Looks up a customer by email and returns customer id, email, name, and creation timestamp. |
| `OrderStatus` | `backend/app/tools/orders.py` | Finds a customer by email and returns their orders ordered by newest first. |
| `updateOrder` | `backend/app/tools/orders.py` | Verifies customer and order ownership, recalculates the amount, and updates only when the amount is unchanged. |
| `Refund` | `backend/app/tools/refunds.py` | Verifies customer and order ownership, auto-approves refunds under `$10.00`, and routes larger refunds to human approval. |
| `openTicket` | `backend/app/tools/tickets.py` | Creates an open support ticket for a known customer and returns the new ticket id. |

### Data Model

```mermaid
erDiagram
    CUSTOMER ||--o{ CUSTOMER_ORDER : places
    CUSTOMER ||--o{ TICKET : opens

    CUSTOMER {
        int id
        string email
        string name
        datetime created_at
    }

    CUSTOMER_ORDER {
        int id
        int customer_id
        string status
        decimal total_amount
        datetime created_at
    }

    TICKET {
        int id
        int customer_id
        text issue
        string status
        datetime created_at
        datetime closed_at
    }
```

### Reliability And Safety Boundaries

- The system prompt tells the model to use tools before making customer-specific claims.
- Guardrails run before and after provider calls in `LLMService`.
- Tool parameters are validated with generated Pydantic models based on the same schemas sent to the model.
- The session store preserves multi-turn context for missing details, then clears the active tool after execution.
- Tool-generated responses are validated against verified backend results to reduce hallucinated IDs, statuses, refunds, or actions.
- Telemetry records the session state, selected tool source, plan, tool execution, validation, and final storage event for each turn.

## Tech Stack

- Frontend: React, Vite, Nginx
- Backend: FastAPI, Python
- Database: PostgreSQL, SQLAlchemy
- LLM: OpenAI-compatible chat completions API
- Containers: Docker, Docker Compose

No agent framework is used for the core workflow orchestration. The planning, tool execution, session handling, and validation flow are implemented in the backend code.

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
