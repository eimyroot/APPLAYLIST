---
id: APPLAYLIST-GOVERNANCE-DECISION-2026-07-26
title: Adopt dual-constitution product engineering governance V2.1
status: ACCEPTED
owner: Eimy
created: 2026-07-26
updated: 2026-07-26
related:
  - WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md
  - PRODUCT_DECISION_EXECUTION_CONSTITUTION.md
  - PRIME_DIRECTIVE_7Q_OPERATING_CARD.md
---

# ROZHODNUTÍ O PŘIJETÍ GOVERNANCE V2.1

## Kontext

APPLAYLIST potřebuje současně chránit technickou pravdivost a řídit produktový smysl, rozhodovací disciplínu, realizaci, release a outcome validaci. Samotná Git historie ani samotná technická pravidla nepokrývají celý životní cyklus rozhodnutí.

## Rozhodnutí

Projekt přijímá dvouvrstvý governance model:

1. `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md` zůstává nejvyšší technickou ústavou.
2. `PRODUCT_DECISION_EXECUTION_CONSTITUTION.md` ji doplňuje o produktovou, rozhodovací a realizační vrstvu.
3. `PRIME_DIRECTIVE_7Q_OPERATING_CARD.md` je krátký každodenní vstup.
4. 7Q change gate je strojově kontrolovatelný a nesmí připustit falešné `10/10`.

## Oddělení přijetí a ověření

- Přijetí vlastníkem: `ACCEPTED`.
- Implementace v canonical repozitáři: prokázána adopčním commitem.
- Provozní ověření: `PARTIALLY_VERIFIED`, dokud neproběhnou tři pilotní WB.
- Plná aktivace: až po samostatném pilot review rozhodnutí.

## Trade-off

Governance přidává malou počáteční režii. Přijímá se pouze proto, že krátká operativní karta, risk-tier fast paths a automatizovaný gate mají snížit rework, auditní smyčky a falešná tvrzení.

## Rollback

Adopční commit lze bezpečně revertovat jedním logickým `git revert`. Technická ústava se při rollbacku nesmí měnit na jiný obsah; lze pouze odstranit nově tracked kopii, pokud zůstane dostupný ověřený external bootstrap.

## Následné rozhodnutí

Po třech pilotech musí vzniknout `KEEP / ITERATE / ROLLBACK / SUPERSEDE` review.
