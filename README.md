# APPLAYLIST

APPLAYLIST je nový hlavní produkt: **AI-powered DJ playlist operating system**.

## Repo role
- `APPLAYLIST` = nový produkční základ
- `Applaylist-old` = donor logiky / reference / osnova

## Bundle 0
Tento bundle vytváří:
- production skeleton repa
- base FastAPI app
- health endpoint
- central config
- structured logging
- docs bootstrap
- local docker compose bootstrap

## Spuštění lokálně
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Health check
- `GET /health`

## Architektonický princip
```text
API -> Services -> Repositories -> DB
               -> Queue -> Workers
```

## Co Bundle 0 ještě neobsahuje
- jobs
- DB implementaci
- analyzer/composer/validator/export logiku
- external connectors
- AI embeddings
