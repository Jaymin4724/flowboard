# CLAUDE.md

This file provides guidance to AI assistants when working with this codebase.

## Development Commands

**Run the Application:**

```bash
# Start FastAPI server (dev with auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
fastapi dev app/main.py

# Start Celery worker
celery -A app.worker.celery_app.celery_app worker --loglevel=info
celery -A app.worker.celery_app.celery_app worker --pool=solo --loglevel=info  (Windows)

# Start Celery beat (periodic tasks)
celery -A app.worker.celery_app.celery_app beat --loglevel=info

# Start Flower (Celery monitoring UI)
celery -A app.worker.celery_app.celery_app flower --port=5555
```

**Database:**

```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

**Test:**

```bash
pytest                    # All tests
pytest --cov=app          # With coverage
pytest -v                 # Verbose
pytest tests/test_users.py::TestUser::test_login_success  # Single test
```

**Docker:**

```bash
docker compose up -d                    # Start all services
docker compose down                     # Stop
docker compose up -d --build            # Rebuild and start
```

**Package Management (uv):**

```bash
uv sync                    # Install dependencies
uv sync --frozen           # Install from lock (CI/Docker)
```

## Full Source Map

```
project-root/
├── app/
│   ├── main.py                         # FastAPI app entry — title="FlowBoard"
│   ├── api/v1/
│   │   ├── api.py                      # Combines all routers into api_router
│   │   ├── dependencies.py             # DI: get_db, get_redis, get_current_user, AdminDep
│   │   ├── routes/
│   │   │   ├── items.py                # /items — CRUD with pagination, due-date filtering
│   │   │   ├── users.py                # /users — register(OTP), verify-otp, login, refresh, profile-photo
│   │   │   └── admin.py                # /admin — manage users/items, promote, restore
│   │   └── schemas/
│   │       ├── item.py                 # ItemCreateSchema, ItemUpdateSchema, ItemOutSchema
│   │       ├── user.py                 # UserCreateSchema, UserOutSchema, UserInDBSchema
│   │       ├── response.py             # ResponseSchema[T] — standard {success, message, data}
│   │       └── pagination.py           # PaginationSchema — page, size
│   ├── core/
│   │   ├── config.py                   # Settings(pydantic-settings) — reads .env
│   │   ├── logger.py                   # File logging with log_func decorator
│   │   └── redis.py                    # Shared async Redis client
│   ├── db/
│   │   ├── database.py                 # Async engine + session factory
│   │   └── models/
│   │       ├── base.py                 # Base(DeclarativeBase) — id, created_at, last_updated_at
│   │       ├── user.py                 # UserModel — email, username, hashed_password, is_admin, etc.
│   │       └── item.py                 # ItemModel — title, desc, status, remind_me_at, FK→owner
│   ├── repositories/
│   │   ├── users_repo.py              # UserRepository — get_by_email, get_by_id, create, update, etc.
│   │   ├── item_repo.py               # ItemRepository — CRUD, get_by_title, get_pending_reminders
│   │   └── admin_repo.py              # AdminRepository — bulk queries across all users/items
│   ├── service/
│   │   ├── auth_service.py            # JWT encode/decode, password hashing, OTP generation
│   │   ├── email_service.py           # Send OTP & reminder emails via SMTP
│   │   └── s3_service.py              # Upload/download/delete profile photos on S3 + presigned URLs
│   ├── middleware/
│   │   ├── logging_middleware.py       # Request/response logging to app/logs/
│   │   └── rate_limitting_middleware.py # Sliding-window rate limiter via Redis
│   ├── worker/
│   │   ├── celery_app.py              # Celery app config (beat schedule, autodiscovery)
│   │   └── tasks.py                   # execute_reminder_email, dispatch_reminders_batch, deactivate_completed_items
│   ├── utils/
│   │   └── mask_sensitive_data.py     # Redacts passwords, tokens, etc. from logs
│   └── templates/email/               # (reserved for email templates)
├── tests/
│   ├── conftest.py                    # Async fixtures: db, client (with Fakeredis, mock email)
│   ├── test_main.py                   # Health-check endpoint
│   ├── test_users.py                  # Register, verify-otp, login, refresh, profile-photo flows
│   ├── test_items.py                  # Item CRUD + pagination + reminders
│   ├── test_admin.py                  # Admin user/item management
│   └── test_utils.py                  # Util-level unit tests
├── alembic/                           # Auto-generated migrations
│   └── versions/
├── .env                               # Local environment config (git-ignored)
├── .env.docker                        # Docker environment config
├── docker-compose.yml                 # postgres, redis, fastapi-app, celery-worker, celery-beat, flower
├── Dockerfile                         # Multi-stage uv-based build
├── pyproject.toml                     # Project metadata (name="flowboard")
├── pytest.ini                         # pytest config
├── pitch.txt                          # Project origin story
└── CLAUDE.md                          # (this file)
```

## API Endpoints

| Prefix     | Endpoint                     | Method | Auth  | Description                          |
| ---------- | ---------------------------- | ------ | ----- | ------------------------------------ |
| `/`      | `/`                        | GET    | No    | Health check                         |
| `/users` | `/register`                | POST   | No    | Initiate registration (sends OTP)    |
| `/users` | `/verify-otp`              | POST   | No    | Verify OTP to complete registration  |
| `/users` | `/login`                   | POST   | No    | Login → access + refresh tokens     |
| `/users` | `/refresh`                 | POST   | No    | Refresh access token                 |
| `/users` | `/profile-photo/{user_id}` | POST   | Yes   | Upload profile photo to S3           |
| `/users` | `/profile-photo/{user_id}` | GET    | Yes   | Get presigned S3 URL                 |
| `/items` | `/`                        | GET    | Yes   | List user's items (paginated)        |
| `/items` | `/`                        | POST   | Yes   | Create item                          |
| `/items` | `/{item_id}`               | PATCH  | Yes   | Update item (partial)                |
| `/items` | `/{item_id}`               | DELETE | Yes   | Delete item                          |
| `/items` | `/reminder/{item_id}`      | POST   | Yes   | Set reminder (schedules Celery task) |
| `/admin` | `/items`                   | GET    | Admin | List all items (paginated)           |
| `/admin` | `/users`                   | GET    | Admin | List all users (paginated)           |
| `/admin` | `/users/{user_id}`         | GET    | Admin | Get user details                     |
| `/admin` | `/items`                   | POST   | Admin | Create item for any user             |
| `/admin` | `/items/{item_id}`         | PATCH  | Admin | Update any item                      |
| `/admin` | `/users/{user_id}/promote` | PATCH  | Admin | Promote user to admin                |
| `/admin` | `/items/{item_id}`         | DELETE | Admin | Delete any item                      |
| `/admin` | `/users/{user_id}`         | DELETE | Admin | Deactivate user                      |

## Key Patterns & Conventions

1. **Async-first** — All DB/Redis/HTTP calls use `async/await`. Repository methods are async.
2. **Dependency Injection** — FastAPI `Depends()` via `app/api/v1/dependencies.py`. Type aliases (`DBDep`, `CurrentUserDep`, etc.) reduce boilerplate.
3. **Repository Pattern** — Data access lives in `app/repositories/`. Services call repositories. Routes call services/repos directly.
4. **Standard Response** — Every endpoint returns `ResponseSchema` `{success, message, data}` via `create_response()`.
5. **Logging** — Use `@log_func` decorator on route handlers. Sensitive data is auto-masked.
6. **JWT Auth** — Access tokens (short-lived) + refresh tokens (long-lived, blacklisted in Redis on logout).
7. **OTP Flow** — Registration sends OTP email; user must verify within 5 min (OTP stored in Redis).
8. **Celery Tasks** — Reminders are dispatched in batches (beat, every 60s) → individual ETA tasks → emails. Completed items auto-deactivate weekly.
9. **Rate Limiting** — Sliding-window counter in Redis per IP per endpoint.
10. **S3** — Profile photos uploaded directly through API; reads return presigned download URLs.
11. **Testing** — `conftest.py` overrides `get_db` (test DB with transactions), `get_redis` (Fakeredis), and `EmailService` (AsyncMock). Each test gets a fresh rolled-back session.
12. **Error Handling** — FastAPI `HTTPException` with standardized status codes.

## Environment Variables

**Required** in `.env` (or `.env.docker` for Docker):

- `DB_URL` — PostgreSQL async DSN
- `TEST_DB_URL` — Separate DB for tests
- `SECRET_ACCESS_KEY` / `SECRET_REFRESH_KEY` — JWT signing secrets (256-bit base64)
- `ALGORITHM` — JWT algorithm (default `HS256`)
- `REDIS_HOST` / `REDIS_PORT` / `REDIS_URL`
- `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_FROM` / `MAIL_PORT` / `MAIL_SERVER` — SMTP
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` / `AWS_S3_BUCKET` — S3
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30)
- `REFRESH_TOKEN_EXPIRE_DAYS` (default 7)
- `TESTING` — set `true` to bypass email in tests
- `EMAIL_SERVICE_ACTIVE` — set `false` to skip email sending

## AI Assistant Notes

- **FastAPI version**: ^0.132.0 (uses `Annotated` + `Depends` pattern)
- **Python**: >=3.10 (uses `type | None` union syntax)
- **SQLAlchemy**: 2.0+ async (uses `Mapped`, `mapped_column`, `selectinload`, not legacy `Query` API)
- **No HTML frontend** — this is a pure JSON API (no Jinja2 templates, no static files)
- **No `.env.example`** — copy `.env` directly
- **Celery on Windows** requires `--pool=solo` flag
- **Migration naming convention**: descriptive snake_case strings
