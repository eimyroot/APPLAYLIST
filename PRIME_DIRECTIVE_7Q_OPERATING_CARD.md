---
id: APPLAYLIST-OPERATING-CARD-001
title: Prime Directive and 7Q Operating Card
status: ACCEPTED
version: 1.1.0
owner: Eimy
created: 2026-07-26
updated: 2026-07-26
accepted: 2026-07-26
accepted_by: Eimy
activation: PILOT_REQUIRED
related:
  - WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md
  - PRODUCT_DECISION_EXECUTION_CONSTITUTION.md
---

# PRIME DIRECTIVE + 7Q OPERATING CARD

> **Nejsilnější vývojový model spojuje Jobsovu produktovou čistotu, unixovou jednoduchost, DevOps automatizaci, SRE spolehlivost, bezpečnostní princip nulové důvěry a úplnou auditovatelnost celého životního cyklu systému — nejen jeho Git historie.**
>
> **Každá změna MUSÍ být jednoduchá, účelná, automatizovaná, bezpečná, měřitelná, vratná a důkazně ověřitelná.**

## 1. REALITY CHECK

Před prací urč:

- skutečný cíl,
- source of truth,
- ověřený stav,
- hlavní riziko,
- context domain: `CLEAR / COMPLICATED / COMPLEX / CHAOTIC / CONFUSED`,
- risk tier: `T0 / T1 / T2 / T3`,
- nejrychlejší bezpečnou cestu.

## 2. 7Q GATE

| Dimenze | Povinná otázka | PASS vyžaduje |
|---|---|---|
| SIMPLE | Je to nejjednodušší bezpečné řešení? | Jeden problém, malý diff, jedna autoritativní cesta, jasná boundary |
| PURPOSEFUL | Jaký ověřený pokrok přinese uživateli nebo systému? | JTBD/outcome, evidence nebo hypotéza, metric, non-goals, kill criterion |
| AUTOMATED | Co lze opakovat bez lidské improvizace? | Automatické mechanické checks, explicitní manuální judgement, fail-closed |
| SECURE | Čemu omylem důvěřujeme? | Zero trust, least privilege, secure defaults, threat/supply-chain review |
| MEASURABLE | Jak poznáme výsledek a škodu? | Baseline, target, source, window, owner, guardrail |
| REVERSIBLE | Jak se bezpečně vrátíme? | Klasifikace vratnosti, rollback/disable/containment, test podle rizika |
| PROVABLE | Jak to nezávisle prokážeme? | Evidence subject+version+environment+commands+digests+unknowns |

Pravidla:

- žádné průměrování,
- nejslabší relevantní dimenze určuje stav,
- `UNKNOWN` blokuje high-risk práci a release,
- `10/10` lze uvést pouze při `VERIFIED_PASS / 10` ve všech relevantních dimenzích,
- `NOT_APPLICABLE` vyžaduje důvod a schválení.

## 3. MINIMÁLNÍ TOK

```text
REALITY
→ PROBLEM / HYPOTHESIS
→ SHAPE
→ DECIDE
→ 7Q PRE-GATE
→ SMALL WORK BLOCK
→ TARGETED TESTS
→ REGRESSION + SECURITY
→ EVIDENCE RECEIPT
→ 7Q POST-GATE
→ LOGICAL CHECKPOINT
→ RELEASE DECISION
→ RUNTIME VERIFICATION
→ OUTCOME REVIEW
→ KEEP / ITERATE / ROLLBACK / RETIRE
```

## 4. WIP

Výchozí limit pro jednoho hlavního vývojáře:

- 1 aktivní implementační WB,
- 1 incident lane,
- 1 discovery lane.

## 5. STOP CONDITIONS

Okamžitě zastav při:

- změně source of truth,
- constitution mismatch,
- dirty nebo neočekávaném Git stavu,
- nejasném původu kódu,
- test/security regression,
- chybějícím rollbacku u T2/T3,
- nedoloženém `10/10`,
- požadavku na destruktivní krok bez explicitního schválení,
- opakovaném širokém auditu bez snížení uncertainty.

## 6. FAST PATH

- známý bug: reprodukce + regression test + rollback,
- T0 docs: diff review + významová kontrola,
- incident: containment first, evidence and retrospective after stabilization.

Fast path nesmí odstranit pravdivost, bezpečnost, vratnost ani evidenci.

## 7. POVINNÝ ZÁVĚR

```text
PRODUCT OUTCOME:
DECISION:
TRUTH STATUS:
LIFECYCLE STATUS:
7Q RESULT:
SIMPLE:
PURPOSEFUL:
AUTOMATED:
SECURE:
MEASURABLE:
REVERSIBLE:
PROVABLE:
EVIDENCE:
RISKS:
NEXT SAFE STEP:
```
