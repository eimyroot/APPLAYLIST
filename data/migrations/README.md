# Migrations

Bundle 2 zavádí repository vrstvu a explicitní schema bootstrap pro local SQLite mode.

## Locked rule
- žádné přímé DB zápisy mimo `data/repositories/*`
- analyzér ani service vrstvy nesmí dělat vlastní `sqlite3.connect(...)`
- budoucí migration layer bude navazovat na tento základ

## Current state
Tento bundle používá `ensure_schema()` pro local bootstrap.
To je přechodový krok před plnohodnotnou migration vrstvou.
