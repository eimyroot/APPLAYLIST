# APPLAYLIST

APPLAYLIST je backend a vývojový základ pro DJ/audio intelligence: analýzu tracků, tvorbu playlistů, strukturu setů, export a budoucí API produkt.

## Aktuální stav

- Kanonický repozitář: `nulleimy/APPLAYLIST`
- Aktuální checkpoint: Bundle 23
- Podporovaný Python: `>=3.11,<3.13`
- Produkční stav: **není ještě release-ready**
- Legacy analyzér zůstává aktivní; provider vrstva a benchmark jsou zatím experimentální základ

## Architektura

```text
API -> Services -> Repositories -> DB
               -> Queue -> Workers

Audio input -> Provider -> Normalize/Validate -> AnalysisRecord -> Repository
```

Hranice komponent:

- `api/` — HTTP rozhraní, middleware a transportní validace
- `core/` — doménové kontrakty, provider registry a čistá logika
- `services/` — aplikační orchestrace
- `data/` — modely, repository a persistence
- `workers/` — asynchronní zpracování
- `tests/` — unit, integrační a regresní testy
- `docs/` — architektura, rollout a provozní dokumentace

## Lokální vývoj

```bash
cd /cesta/k/APPLAYLIST
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
cp .env.example .env
.venv/bin/python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

## Ověření

```bash
cd /cesta/k/APPLAYLIST
.venv/bin/python -m compileall -q api core services data workers
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
```

Nepoužívej globální Python ani Python 3.14. Do repozitáře nepatří `.env`, `.venv`, databáze, cache, lokální zálohy ani iCloud duplikáty typu `* 2.py`.

## Release brány

Release je povolen pouze při splnění všech podmínek:

1. CI projde na Pythonu 3.11 a 3.12.
2. Import API nevyžaduje nepovinný audio backend.
3. Provider výstup je normalizovaný a validovaný před uložením.
4. Neexistuje falešný úspěch ani skrytý fallback.
5. API kontrakty zůstávají zpětně kompatibilní nebo mají migrační plán.
6. Rollback provider režimu je ověřený feature flagem.

## Další implementační pořadí

1. Production baseline a CI gate.
2. Provider hardening bez importu optional závislostí při bootu.
3. Routed analysis service za fail-closed feature flagem.
4. Integrace do jobs, observability a persistence compatibility testy.
5. API metadata/availability bez změny stávající response shape.
6. Staging porovnání výstupů a teprve poté rozhodnutí o default provideru.
