FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock .
RUN uv sync --frozen --no-install-project
COPY . .
RUN uv sync --frozen
CMD ["/app/.venv/bin/fastapi", "run", "app/main.py", "--host", "0.0.0.0"]