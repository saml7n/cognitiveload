# FinServ Ledger API (Demo App)

A small FastAPI application for tracking financial ledger entries. Used as a target for the Issue Intelligence PoC.

## Setup

Using `uv`:
```bash
uv sync --project demo_app
```

## Run

```bash
uv run --project demo_app uvicorn demo_app.main:app --reload
```

## Test

```bash
uv run --project demo_app pytest demo_app/tests
```

## API Endpoints

- `GET /entries`: List all entries.
- `GET /summary`: Get financial summary.
- `POST /entries`: Create a new entry.
