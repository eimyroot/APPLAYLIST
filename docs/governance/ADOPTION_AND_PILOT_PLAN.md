# GOVERNANCE V2.1 — ADOPTION AND PILOT PLAN

## Přijetí

Adopční WB vytvoří samostatný governance commit a nesmí měnit produktový kód, dependencies, runtime konfiguraci ani veřejné API.

## Povinné piloty

1. **Pilot A — T0/T1 fast path:** malá dokumentační nebo známá bug oprava.
2. **Pilot B — T1/T2 standard:** malý vertikální produktový Work Block.
3. **Pilot C — T2/T3:** security, migrace, packaging nebo release gate.

## Povinná měření

- preparation time,
- lead time,
- počet skutečně použitých polí,
- unknowns nalezené před implementací,
- rework zabráněný nebo přidaný,
- rollback quality,
- evidence graph reconstruction,
- cognitive load.

## Exit decision

```text
KEEP
ITERATE
ROLLBACK
SUPERSEDE
```

Do review rozhodnutí je správný stav:

```text
OWNER_DECISION=ACCEPTED
IMPLEMENTED=YES_AFTER_COMMIT
OPERATIONAL_VERIFICATION=PARTIALLY_VERIFIED
ACTIVATION=PILOT_ACTIVE
```
