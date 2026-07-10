# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
docker compose up -d                    # Start all services (runs migrations via the `migrate` service first)
docker compose down                     # Stop
docker compose up -d --build            # Rebuild and start
```

**Package Management (uv):**

```bash
uv sync                    # Install dependencies
uv sync --frozen           # Install from lock (CI/Docker)
```

## Architecture

- **Layering**: routes (`app/api/v1/routes/`) call repositories (`app/repositories/`) directly for data access, and services (`app/service/`) for cross-cutting concerns (auth, email, S3). There is no separate service layer between routes and repositories for CRUD — routes own the business logic (ownership checks, status transitions, etc.) and delegate persistence to repositories.
- **Three route groups**, each with its own repository: `users` (`UserRepository`), `items` (`ItemRepository`), `admin` (`AdminRepository`, which duplicates cross-user item/user queries rather than reusing the other two repos).
- **Auth**: `app/api/v1/dependencies.py` defines `CurrentUserDep` (decodes the bearer access token, loads the user, rejects inactive users with 403) and `AdminDep` (wraps `CurrentUserDep`, additionally requires `user.is_admin`). There is currently no API endpoint that sets `is_admin` — `UserUpdateSchema`/`UserUpdateMeSchema` deliberately exclude it, so promotion to admin must be done directly in the DB.
- **Standard response envelope**: every route returns `ResponseSchema` (`{success, message, data}`) via `create_response()` (`app/api/v1/schemas/response.py`).
- **Registration flow**: `/users/register` hashes the password, stores a pending-user blob + OTP in Redis (`pending_user:{email}`, 10 min TTL) and emails the OTP; `/users/verify-otp` validates the OTP and only then creates the row in Postgres. If `EMAIL_SERVICE_ACTIVE=false` and not `TESTING`, registration skips OTP entirely and creates an unverified user directly.
- **Token lifecycle**: access tokens are signed with `SECRET_ACCESS_KEY`, refresh tokens with `SECRET_REFRESH_KEY` (separate secrets, `app/service/auth_service.py`). `/users/refresh` rotates both tokens and blacklists the *old* refresh token in Redis (`blacklist:{token}`, TTL = remaining token lifetime) to prevent reuse. `/users/logout` blacklists a given refresh token (and optionally an access token) the same way.
- **Item lifecycle**: `ItemStatus` = `pending → running → completed → deactivated`. Setting `status=deactivated` via PATCH auto-sets `deactivation_type=manual`; any other status resets it to `none`. A weekly Celery beat task (`deactivate_completed_items`) bulk-flips `completed` items to `deactivated` with `deactivation_type=automatic`, using `SELECT ... FOR UPDATE SKIP LOCKED` to avoid contention.
- **Reminders**: `POST /items/remind/{item_id}` (body: `remind_at`) sets `remind_me_at` and resets `reminded`/`dispatched`. A beat task (`dispatch_reminders_batch`, every 60s) row-locks (`SKIP LOCKED`) and claims items due within the next 60s, marking `dispatched=True`, then schedules one `execute_reminder_email` Celery ETA task per item. That task sends the email and then clears the reminder entirely (`remind_me_at=None, reminded=False, dispatched=False`) — an item that's been reminded looks identical to one that never had a reminder set, rather than sitting in a stale "reminded" state with a past `remind_me_at`. Both worker tasks build their own SQLAlchemy engine/session per call (`make_session_factory()` in `app/worker/tasks.py`) since Celery workers run outside the FastAPI event loop.
- **Rate limiting**: `app/middleware/rate_limitting_middleware.py` is a sliding-window counter in Redis keyed by client IP (`rate_limit:{ip}`, 15 req/60s). It is a no-op whenever `settings.TESTING` is `True`.
- **Timestamps**: `app/db/models/base.py`'s `created_at`/`last_updated_at` are stored as naive UTC (`tzinfo` stripped before insert) — be careful comparing against timezone-aware datetimes elsewhere in the codebase (e.g. `remind_me_at`, which *is* timezone-aware).
- **Logging**: `@log_func` (`app/core/logger.py`) wraps route handlers to log entry/exit/errors to `app/logs/application_logs.txt`, auto-masking sensitive fields via `app/utils/mask_sensitive_data.py`. `logging_middleware.py` separately logs every request/response with a request ID and timing header.
- **Testing** (`tests/conftest.py`): overrides `get_db` with a per-test transactional session that's rolled back after each test, `get_redis` with a single shared in-process `FakeRedis` instance across the whole test session (flushed after each test), and `EmailService` with an `AsyncMock`. Tests run against `TEST_DB_URL` (a real Postgres DB, not sqlite).
- **Docker Compose services**: `postgres`, `redis`, a one-shot `migrate` service (runs `alembic upgrade head`, must complete before `fastapi-app` starts), `fastapi-app`, `celery-worker`, `celery-beat`, `flower`. All share `.env.docker` and an `app-network` bridge network.

## API Endpoints

| Prefix     | Endpoint                     | Method | Auth  | Description                          |
| ---------- | ----------------------------- | ------ | ----- | ------------------------------------- |
| `/`        | `/`                            | GET    | No    | Health check                          |
| `/users`   | `/register`                    | POST   | No    | Initiate registration (sends OTP)     |
| `/users`   | `/verify-otp`                  | POST   | No    | Verify OTP to complete registration   |
| `/users`   | `/login`                       | POST   | No    | Login → access + refresh tokens      |
| `/users`   | `/refresh`                     | POST   | No    | Rotate access + refresh tokens        |
| `/users`   | `/logout`                      | POST   | No*   | Blacklist refresh (+ access) token    |
| `/users`   | `/me`                          | GET    | Yes   | Get own profile                       |
| `/users`   | `/me`                          | PATCH  | Yes   | Update own username/email/password    |
| `/users`   | `/me`                          | DELETE | Yes   | Deactivate own account (soft delete)  |
| `/users`   | `/profile-photo/{user_id}`     | POST   | Yes   | Upload profile photo to S3            |
| `/users`   | `/profile-photo/{user_id}`     | GET    | Yes   | Get presigned S3 URL                  |
| `/items`   | `/`                             | GET    | Yes   | List own items (paginated)            |
| `/items`   | `/`                             | POST   | Yes   | Create item                           |
| `/items`   | `/{item_id}`                   | PATCH  | Yes   | Update item (partial, ownership-checked) |
| `/items`   | `/{item_id}`                   | DELETE | Yes   | Delete item (ownership-checked)       |
| `/items`   | `/remind/{item_id}`            | POST   | Yes   | Set reminder (schedules Celery task)  |
| `/admin`   | `/items`                       | GET    | Admin | List all items (paginated)            |
| `/admin`   | `/items/detailed`              | GET    | Admin | List all items with owner username/email |
| `/admin`   | `/users`                       | GET    | Admin | List all active users (paginated)     |
| `/admin`   | `/items`                       | POST   | Admin | Create item for admin's own user      |
| `/admin`   | `/items/{item_id}`             | PATCH  | Admin | Update any item                       |
| `/admin`   | `/items/{item_id}`             | DELETE | Admin | Delete any item                       |
| `/admin`   | `/users/{user_id}`             | PATCH  | Admin | Update any user (`is_active`, `is_verified`, `profile_photo_key`) |
| `/admin`   | `/users/{user_id}`             | DELETE | Admin | Deactivate user (soft delete)         |

\* `/logout` takes the token(s) as request params rather than reading the caller's bearer token, so it isn't gated by `CurrentUserDep`.

## Key Patterns & Conventions

1. **Async-first** — All DB/Redis/HTTP calls use `async/await`. Repository methods are async.
2. **Dependency Injection** — FastAPI `Depends()` via `app/api/v1/dependencies.py`. Type aliases (`DBDep`, `CurrentUserDep`, `AdminDep`, etc.) reduce boilerplate.
3. **Repository Pattern** — Data access lives in `app/repositories/`. Routes call repositories/services directly; there's no separate service layer for CRUD business logic.
4. **Standard Response** — Every endpoint returns `ResponseSchema` `{success, message, data}` via `create_response()`.
5. **Logging** — Use the `@log_func` decorator on route handlers. Sensitive data is auto-masked.
6. **JWT Auth** — Access tokens (short-lived) + refresh tokens (long-lived), signed with separate secrets; both are blacklisted in Redis on rotation/logout.
7. **OTP Flow** — Registration sends an OTP email; the user must verify within 10 min (pending user + OTP stored in Redis, not yet in Postgres).
8. **Celery Tasks** — Reminders are dispatched in batches (beat, every 60s) → individual ETA tasks → emails. Completed items auto-deactivate weekly (Saturday 22:30 UTC).
9. **Rate Limiting** — Sliding-window counter in Redis per IP, disabled when `TESTING=true`.
10. **S3** — Profile photos uploaded directly through the API; reads return presigned download URLs.
11. **Partial updates** — `ItemUpdateSchema`/`UserUpdateSchema`/`UserUpdateMeSchema` use `model_dump(exclude_unset=True)` so only explicitly-provided fields are changed.
12. **Error Handling** — FastAPI `HTTPException` with standardized status codes.

## Environment Variables

Copy `.env.example` to `.env` (or configure `.env.docker` for Docker) and fill in:

- `DB_URL` — PostgreSQL async DSN
- `TEST_DB_URL` — Separate DB for tests
- `SECRET_ACCESS_KEY` / `SECRET_REFRESH_KEY` — JWT signing secrets (256-bit base64)
- `ALGORITHM` — JWT algorithm (default `HS256`)
- `REDIS_HOST` / `REDIS_PORT` / `REDIS_URL`
- `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_FROM` / `MAIL_PORT` / `MAIL_SERVER` — SMTP
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` / `AWS_S3_BUCKET` — S3
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30)
- `REFRESH_TOKEN_EXPIRE_DAYS` (default 7)
- `TESTING` — set `true` to bypass rate limiting and force the OTP flow in tests
- `EMAIL_SERVICE_ACTIVE` — set `false` to skip OTP email and register users directly (unverified)

## AI Assistant Notes

- **FastAPI version**: ^0.132.0 (uses `Annotated` + `Depends` pattern)
- **Python**: >=3.10 (uses `type | None` union syntax)
- **SQLAlchemy**: 2.0+ async (uses `Mapped`, `mapped_column`, `selectinload`, not legacy `Query` API)
- **No HTML frontend** — this is a pure JSON API (no Jinja2 templates, no static files)
- **Celery on Windows** requires the `--pool=solo` flag
- **Migration naming convention**: descriptive snake_case strings
- **`is_admin`** exists on `UserModel` but is intentionally not exposed on any update schema — there's no API path to promote a user to admin.
