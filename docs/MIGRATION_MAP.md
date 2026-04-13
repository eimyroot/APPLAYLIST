# MIGRATION MAP

## Source of truth
- `Applaylist-old` = donor/reference
- `APPLAYLIST` = clean product rebuild

## Planned extraction
- `Applaylist-old/agents/library_scanner`
  -> `services/analysis/scanner_service.py`
- `Applaylist-old/agents/track_analyzer`
  -> `services/analysis/analyzer_service.py`
- `Applaylist-old/agents/playlist_composer`
  -> `services/composition/composer_service.py`
- `Applaylist-old/agents/quality_validator`
  -> `services/validation/validator_service.py`
- `Applaylist-old/agents/playlist_exporter`
  -> `services/export/export_service.py`
