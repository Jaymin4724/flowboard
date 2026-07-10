# The Story Behind FlowBoard

Before this project, my background was primarily MERN stack development. When I started learning Python and FastAPI, I began with a simple task-management app to learn the fundamentals — models, routes, a database, basic CRUD.

As I kept learning, the project kept growing with me. Rather than starting a new toy project for every new backend concept, I extended the same codebase — so FlowBoard grew, got refactored, and matured the same way a real production backend does, instead of existing as a pile of disconnected demos.

Over the course of building it, I implemented:

- **Authentication** — JWT access/refresh tokens, OTP email verification, and Redis-backed refresh-token blacklisting on rotation/logout
- **Asynchronous APIs** — a fully async request path built on SQLAlchemy 2.0 (async) with proper connection pooling
- **Background processing** — Celery with a beat scheduler for batched reminder dispatch plus per-item Celery ETA tasks
- **Caching & rate limiting** — Redis-backed OTP storage and token blacklist, plus a sliding-window per-IP rate limiter
- **Cloud storage** — AWS S3 integration for profile photos with presigned URL access
- **Containerization** — a full Docker Compose stack (API, Celery worker, Celery beat, Flower, Postgres, Redis)
- **Testing** — a 53-test suite (pytest + httpx + FakeRedis) with a success and a failure/permission case for every endpoint

More than any single technology, FlowBoard reflects a shift in how I build software: from assembling CRUD endpoints to designing modular, testable, production-style backend systems — and from learning concepts in isolation to applying each one to a single codebase that had to keep working as it grew.

## What's next

Two things are still on my list, deliberately left for last since they build on everything above rather than standing alone:

- **Load testing with Locust** — simulate concurrent users against the item and reminder endpoints to see how the rate limiter and Celery throughput actually hold up under load, not just in theory
- **AWS deployment** — move FlowBoard from local Docker Compose to a live, publicly reachable deployment

---

This project is part of my preparation for backend engineering interviews — a way to show not just that I've learned these concepts, but that I've built with them.
