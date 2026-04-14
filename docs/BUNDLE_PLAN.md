# BUNDLE PLAN

## Bundle 0
Repo bootstrap

## Bundle 1
Core contracts, config hardening, security skeleton, scripts

## Bundle 2
Data layer foundation:
- records
- repositories
- sqlite connection helper
- local schema init
- migration bootstrap rules

## Bundle 3
Jobs & workers foundation:
- job manager
- in-memory queue
- jobs API
- worker base scaffold

## Bundle 4
Analysis engine foundation:
- librosa-backed analyzer
- bpm / chroma / centroid / zcr feature extraction
- naive key + camelot mapping
- analysis persistence through repository
- analysis worker scaffold

## Bundle 5
Composer foundation:
- bpm flow
- harmonic compatibility
- energy curve targeting
- transition scoring

## Bundle 6
Export layer:
- M3U export
- manifest
- warnings
- audit
- artifact directories

## Bundle 7
External intelligence:
- external signal stub
- fusion layer
- composer scoring enrichment

## Bundle 8
Embeddings + vibe AI:
- feature-derived embedding vectors
- cosine similarity search
- embedding worker scaffold
