# WB-000G — PRODUCT GOVERNANCE V2.1 ADOPTION

## Cíl

Přijmout technickou a produktovou governance vrstvu jako jeden přesný, vratný a auditovatelný documentation/tooling commit.

## Non-goals

- žádná změna produktového kódu,
- žádná změna dependencies,
- žádná změna runtime konfigurace,
- žádný release,
- žádný push,
- žádné tvrzení o provozním `VERIFIED` před třemi piloty.

## Affected paths

Pouze dvě root ústavy, operativní karta, `docs/governance`, tento WB a `tools/governance`.

## Invarianty

- canonical branch a parent HEAD musí odpovídat preflightu,
- index musí být před stagingem prázdný,
- všechny nesouvisející worktree změny musí zůstat byte-identické,
- stage a commit smí obsahovat pouze governance allowlist,
- push je zakázán,
- technická ústava musí mít SHA-256 `ed44c6147049887d941b7497f1bce3b817f22b6ae00a5136a27365a2f688d918`.

## Targeted tests

- UTF-8 a Markdown fence kontrola,
- JSON parse schema a příkladů,
- Python compile,
- honest maximum → exit `0`,
- truthful partial → exit `3`,
- dishonest maximum → exit `1`,
- payload SHA manifest,
- exact staged path allowlist.

## Rollback

`git revert <adoption-commit>` po samostatném preflightu.

## Definition of Done

- governance commit existuje,
- commit parent je předem ověřený HEAD,
- commit obsahuje pouze allowlist,
- lokální bundle je vytvořen a ověřen,
- push nebyl proveden,
- lifecycle je `ACCEPTED / PILOT_ACTIVE / PARTIALLY_VERIFIED`.
