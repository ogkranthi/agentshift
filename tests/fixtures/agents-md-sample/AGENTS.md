# FastAPI Inventory Service

A production inventory management API built with FastAPI and PostgreSQL.

## Architecture

This is a FastAPI + PostgreSQL application using SQLAlchemy as the ORM.

- Main entry point: `src/main.py`
- API routes: `src/routes/`
- Database models: `src/models/`
- Business logic: `src/services/`
- Migrations: `alembic/versions/`

The app follows a layered architecture: routes → services → models.

## Commands

- Run server: `uvicorn src.main:app --reload --port 8000`
- Test: `pytest tests/ -v`
- Lint: `ruff check src/`
- Format: `ruff format src/`
- Migrate: `alembic upgrade head`

## Code Style

- Use type hints on all function signatures
- Prefer dataclasses over plain dicts for structured data
- Keep functions under 50 lines
- Use `logging` module, never `print()`
- All API endpoints must have docstrings

## Do NOT

- Modify migration files directly — use `alembic revision --autogenerate`
- Import anything from `src.legacy` — that package is deprecated
- Use `print()` for logging — use the `logging` module instead
- Commit `.env` files or hardcoded secrets
- Skip type hints on public functions

## Testing

- Unit tests go in `tests/unit/`
- Integration tests go in `tests/integration/`
- Use `pytest-asyncio` for async test functions

```bash
pytest tests/unit/ -v
pytest tests/integration/ -v --slow
```

## Deployment

The app deploys via Docker Compose. See `docker-compose.yml` for the full stack.
