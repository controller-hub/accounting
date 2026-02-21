# Payment Patrol

FastAPI service for deterministic accounts receivable analysis from NetSuite CSV exports.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run server

```bash
uvicorn src.server:app --reload --port 8000
```

## API

- `GET /health` → `{"status":"ok","version":"0.1.0"}`
- `POST /analyze` (multipart form)
  - `file` (CSV, required)
  - `entity` (`fleetio` or `auto_integrate`, required)
  - `run_date` (ISO date, optional)
  - `prior_snapshot_json` (optional)
  - `total_invoiced_amount` (optional)

## Tests

```bash
pytest -q
```

## Architecture

```text
n8n upload form/trigger
        |
        v
  FastAPI /analyze
        |
        v
 ingest -> metrics -> scoring -> reports -> slack blocks
        |
        v
     JSON output
```

Notion spec: https://example.com/notion-payment-patrol-spec
