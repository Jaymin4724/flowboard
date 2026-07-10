# FlowBoard: Scalable Task Management Platform

A production-style async backend API for task management with authentication, background job processing, file storage, and containerized deployment.

## Quick Start

```bash
# 1. Clone and enter the project directory
cd flowboard

# 2. Configure environment
cp .env.example .env   # or configure .env directly

# 3. Install dependencies
uv sync

# 4. Apply database migrations
alembic upgrade head

# 5. Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

### Running the Streamlit frontend (optional)

```bash
# 1. Install the frontend's extra dependencies
uv sync --extra frontend

# 2. Configure the frontend (defaults to http://localhost:8000)
cp frontend/.env.example frontend/.env

# 3. Start it, with the API already running
streamlit run frontend/app.py
```

The UI will be available at `http://localhost:8501`. It's a separate process from the API — it talks to it purely over HTTP.

### Running with Docker

```bash
docker compose up -d
```

This launches: PostgreSQL, Redis, FastAPI app (port 8000), Celery worker, Celery beat, and Flower (port 5555).

## Features

- **User Authentication** — Register with email OTP verification, login with JWT access/refresh tokens
- **Item Management** — Create, update, delete, and list tasks with status workflow (pending → running → completed → deactivated)
- **Smart Reminders** — Set per-item reminders dispatched via Celery beat + ETA tasks; once the reminder email fires, `remind_me_at`/`reminded`/`dispatched` all clear back to their unset state; completed items are auto-deactivated weekly
- **Profile Photos** — Upload/download via AWS S3 with presigned URLs
- **Admin Panel** — Manage all users and items, promote admins, deactivate users
- **Rate Limiting** — Sliding-window per-IP rate limiter via Redis
- **Comprehensive Logging** — Auto-logged request/response with sensitive data masking
- **Pagination** — All list endpoints support `page` and `size` query params
- **Containerized** — Full Docker Compose stack (app, worker, beat, flower, postgres, redis)
- **Streamlit Frontend** — Optional multipage UI (`frontend/`) covering auth, items/reminders, and the admin panel. Session state lives in memory for the browser tab only — refreshing the page logs you out by design; there's no cross-reload persistence.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Framework** | FastAPI (async) |
| **Database** | PostgreSQL + SQLAlchemy 2.0 (async) + Alembic |
| **Cache / Queue** | Redis (Celery broker/backend, rate limiting, OTP storage, token blacklist) |
| **Background Jobs** | Celery (distributed task queue with beat scheduler) |
| **Auth** | JWT (access + refresh tokens), bcrypt (passwords), OTP via email |
| **Storage** | AWS S3 (profile photos with presigned URLs) |
| **Email** | SMTP via FastAPI-Mail |
| **Testing** | Pytest, httpx, Fakeredis, mock email |
| **Infra** | Docker, Docker Compose, uv (package manager) |
| **Frontend** | Streamlit (optional, separate process, `frontend/`) |

## About the Project

FlowBoard started as a simple task management CRUD app built while learning FastAPI. Over the course of development, it grew into a production-style backend that demonstrates real-world engineering patterns:

- Transitioning from synchronous CRUD to **async-first architecture** with proper connection pooling
- Implementing **JWT authentication** with OTP-based email verification and token refresh flows
- Building a **distributed reminder system** using Celery beat (batch dispatch every 60s) + Celery ETA tasks
- Integrating **AWS S3** for file storage with presigned URL access patterns
- Containerizing the full stack with **Docker Compose** (6 services)
- Writing **comprehensive tests** with mocked Redis, isolated DB transactions, and mock email

Every backend concept was applied directly to the same evolving codebase rather than building isolated demos, making FlowBoard a practical demonstration of how real software systems grow and become more maintainable over time.

## Architecture

```
Browser ──► Streamlit (8501, optional) ──┐
                                          ▼
API Client ─────────────────────►  FastAPI (port 8000)  ──►  PostgreSQL
                                          │
                                    ┌─────┴──────┐
                                    ▼            ▼
                                  Redis        AWS S3
                                    │
                              ┌─────┴──────┐
                              ▼            ▼
                          Celery Beat   Celery Worker
                              │              │
                              └──────────────┘
                                   (ETA tasks)
```

- **Arc 1 (Local)** — Configuration via `.env`, direct connections to local Postgres/Redis
- **Arc 2 (Docker)** — Configuration via `.env.docker`, all services run in containers on `app-network`

## Endpoints Overview

| Group | Endpoints | Auth |
|-------|-----------|------|
| **Users** | Register, Verify OTP, Login, Refresh, Upload/Get Profile Photo | Mixed (register/login are public) |
| **Items** | CRUD + Set Reminder | Bearer token |
| **Admin** | List items/users, Create/Update/Delete items, Promote/Deactivate users | Admin token |
| **Health** | `GET /` — server status | Public |

Full interactive documentation is available at `/docs` when the server is running.

## Project Structure

```
app/             # Application source
├── api/         # Routes + schemas + DI
├── core/        # Config, logging, redis client
├── db/          # SQLAlchemy models + session
├── repositories/# Data access layer
├── service/     # Auth, email, S3 integrations
├── middleware/   # Logging + rate limiting
├── worker/      # Celery tasks + config
└── utils/       # Sensitive data masking

frontend/        # Optional Streamlit UI (separate process, talks to app/ over HTTP)
├── api/         # httpx client + one module per backend route group
├── auth/        # st.session_state helpers (in-memory only, no persistence)
├── components/  # Shared widgets (forms, item cards, auth guards)
├── pages/       # One module per screen (login, register, items, profile, admin)
└── app.py       # Entrypoint — builds the nav based on auth/admin state
```

## License

MIT
