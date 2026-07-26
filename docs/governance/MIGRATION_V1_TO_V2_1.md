# MIGRATION — PRODUCT GOVERNANCE V1 → V2.1

## Nahrazení

Canonical soubor `PRODUCT_DECISION_EXECUTION_CONSTITUTION.md` přechází na verzi `2.1.0`.

V1 se nemaže z historických artefaktů ani Git historie. V2.0.0 zůstává zdrojovým návrhovým artefaktem; V2.1.0 opravuje adopční lifecycle a odstraňuje runtime závislost validátoru na třetí straně.

## Změny V2.1

- explicitně odděleno `ACCEPTED` od provozního `VERIFIED`,
- přidán stav `PILOT_ACTIVE`,
- definovány tři povinné pilotní WB,
- change-gate validátor používá pouze Python standard library,
- validátor rozlišuje pravdivé `PARTIALLY_VERIFIED` od kontradiktorního maxima,
- canonical authority index je explicitní.

## Kompatibilita

- schéma zůstává `schema_version=1.0.0`,
- existující poctivé 7Q dokumenty zůstávají kompatibilní,
- skripty závislé na původním `jsonschema` importu musí používat nový canonical validátor.

## Rollback

Použij `git revert <adoption-commit>`. Neprováděj force push ani přepis historie.
