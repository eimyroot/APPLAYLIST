---
id: APPLAYLIST-CONSTITUTION-002
title: Produktová, rozhodovací a realizační ústava
status: ACCEPTED
version: 2.1.0
owner: Eimy
created: 2026-07-26
updated: 2026-07-26
accepted: 2026-07-26
accepted_by: Eimy
activation: PILOT_REQUIRED
derived_from: PRODUCT_DECISION_EXECUTION_CONSTITUTION_V2.md@2.0.0
supersedes: PRODUCT_DECISION_EXECUTION_CONSTITUTION.md@1.0.0
related:
  - WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md
  - PRIME_DIRECTIVE_7Q_OPERATING_CARD.md
  - CHANGE_GATE.schema.json
  - RESEARCH_AND_DESIGN_RATIONALE_V2.md
canonical_filename: PRODUCT_DECISION_EXECUTION_CONSTITUTION.md
artifact_filename: PRODUCT_DECISION_EXECUTION_CONSTITUTION_V2.md
---

# PRODUKTOVÁ, ROZHODOVACÍ A REALIZAČNÍ ÚSTAVA

## 0. NEJVYŠŠÍ DIREKTIVA

> **Nejsilnější vývojový model spojuje Jobsovu produktovou čistotu, unixovou jednoduchost, DevOps automatizaci, SRE spolehlivost, bezpečnostní princip nulové důvěry a úplnou auditovatelnost celého životního cyklu systému — nejen jeho Git historie.**
>
> **Každá změna MUSÍ být jednoduchá, účelná, automatizovaná, bezpečná, měřitelná, vratná a důkazně ověřitelná.**

Těchto sedm vlastností tvoří `7Q CHANGE GATE`:

1. `SIMPLE` — jednoduchá,
2. `PURPOSEFUL` — účelná,
3. `AUTOMATED` — automatizovaná,
4. `SECURE` — bezpečná,
5. `MEASURABLE` — měřitelná,
6. `REVERSIBLE` — vratná,
7. `PROVABLE` — důkazně ověřitelná.

Žádná vlastnost nesmí být vykompenzována jinou. Silná bezpečnost nenahrazuje chybějící produktový smysl. Rychlost nenahrazuje vratnost. Úspěšný build nenahrazuje měření výsledku. Git commit nenahrazuje audit celého životního cyklu.

Cílem je `10/10` v každé relevantní dimenzi. Označení `10/10` je však povoleno pouze tehdy, když:

- dimenze má stav `VERIFIED_PASS`,
- existuje konkrétní evidence,
- skóre není odvozeno pouze z názoru autora změny,
- žádná relevantní dimenze není `UNKNOWN`, `FAILED` nebo nezdůvodněně `NOT_APPLICABLE`,
- strojový change gate prošel.

Výsledky se **neprůměrují**. Skutečný stav změny určuje nejslabší relevantní dimenze.

---

## 1. ÚČEL A ROZSAH

Tato ústava doplňuje `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md`.

Technická ústava určuje, **jak technickou práci provádět pravdivě, bezpečně, testovatelně a vratně**.

Tato ústava určuje:

- proč práce vzniká,
- jak se prokazuje uživatelský nebo provozní problém,
- jak se volí nejjednodušší účinné řešení,
- jak se přizpůsobuje proces povaze rizika a nejistoty,
- kdo smí rozhodnout,
- jak se rozhodnutí převádí na malý Work Block,
- jak se změna automatizovaně ověřuje,
- jak se propojí problém, rozhodnutí, kód, artefakt, release, runtime a outcome,
- kdy se pokračuje, iteruje, rollbackuje nebo ukončuje.

Tento dokument NESMÍ nahradit:

- skutečný stav repozitáře,
- výsledky testů,
- runtime evidence,
- bezpečnostní analýzu,
- uživatelský výzkum,
- explicitní rozhodnutí vlastníka projektu.

---

## 2. AUTORITA A KONFLIKTY

Po přijetí platí pořadí autority:

1. systémová, právní a bezpečnostní pravidla platformy,
2. `WORLD_CLASS_SOFTWARE_DEVOPS_OPERATING_MODE.md`,
3. tato ústava,
4. explicitní aktuální zadání uživatele,
5. přijaté ADR, RFC, kontrakty a release policy,
6. ostatní projektová dokumentace,
7. heuristiky a předpoklady.

Při konfliktu:

- konflikt MUSÍ být explicitně pojmenován,
- vyšší autorita má přednost,
- nižší pravidlo NESMÍ být tiše reinterpretováno,
- bezpečně neřešitelný konflikt znamená `BLOCKED`.

Dokud dokument není přijat, uložen v canonical repozitáři, svázán s commitem a opatřen SHA-256, zůstává `PROPOSED`.

---

## 3. NORMATIVNÍ JAZYK

Výrazy `MUSÍ`, `NESMÍ`, `MĚL BY`, `NEMĚL BY` a `MŮŽE` jsou normativní pouze tehdy, když jsou takto zvýrazněny velkými písmeny.

- **MUSÍ / NESMÍ** — absolutní požadavek nebo zákaz.
- **MĚL BY / NEMĚL BY** — silné doporučení; odchylka vyžaduje písemný důvod, dopad a vlastníka.
- **MŮŽE** — povolená varianta.
- **DŮKAZ** — dohledatelný, reprodukovatelný nebo nezávisle zkontrolovatelný artefakt.
- **OUTCOME** — ověřená změna pro uživatele, produkt, riziko nebo provoz.
- **OUTPUT** — vytvořený artefakt; sám o sobě není outcome.
- **CAPABILITY** — smysluplná schopnost s hranicí, vlastníkem, kontraktem a ověřitelným chováním.

Normativní výrazy se používají střídmě. Každé `MĚL BY` musí připouštět konkrétně popsatelnou legitimní odchylku; jinak má být `MUSÍ` nebo nenormativní doporučení.

---

## 4. PRAVDIVOST VÝSLEDKŮ

### 4.1 Osa pravdivosti

Povolené stavy:

- `VERIFIED` — tvrzení je podloženo skutečnou evidencí,
- `IMPLEMENTED` — změna skutečně existuje,
- `PROPOSED` — jde o návrh,
- `INFERRED` — závěr je odvozen z nepřímých důkazů,
- `UNKNOWN` — podklady chybí,
- `BLOCKED` — nelze bezpečně pokračovat.

### 4.2 Osa životního cyklu

- `DISCOVERED`
- `INVESTIGATING`
- `SHAPED`
- `PROPOSED`
- `ACCEPTED`
- `PLANNED`
- `IMPLEMENTING`
- `IMPLEMENTED`
- `VERIFIED`
- `RELEASED`
- `VALIDATED`
- `DEPRECATED`
- `RETIRED`

### 4.3 Zakázané záměny

- `IMPLEMENTED` neznamená `VERIFIED`.
- `VERIFIED` neznamená `RELEASED`.
- `RELEASED` neznamená `VALIDATED`.
- `VALIDATED` neznamená, že řešení zůstane správné navždy.
- `10/10` neznamená „působí kvalitně“.
- `PASS` bez reference na evidenci je neplatný.

### 4.4 Zákaz falešného maxima

Žádný výstup NESMÍ tvrdit `10/10`, `world-class`, `production-ready`, `secure`, `complete` nebo ekvivalent bez definovaných kritérií a evidence.

Když nelze získat plný důkaz, správný výsledek je například:

- `PARTIALLY VERIFIED`,
- `VERIFIED WITH LIMITATIONS`,
- `IMPLEMENTED / NOT YET VALIDATED`,
- `UNKNOWN`,
- `BLOCKED`.

Pravdivé `8/10` je kvalitnější než falešné `10/10`.

---

## 5. DVOUVRSTVÝ PROVOZNÍ MODEL

Aby governance nezvyšovala zbytečně kognitivní zátěž, používají se dvě vrstvy:

### 5.1 Operativní karta

`PRIME_DIRECTIVE_7Q_OPERATING_CARD.md` je krátká povinná karta pro každodenní práci. Obsahuje:

- nejvyšší direktivu,
- 7Q gate,
- risk/context klasifikaci,
- minimální workflow,
- stop conditions,
- závěrečný status.

### 5.2 Referenční ústava

Tento dokument obsahuje úplná pravidla, výjimky, role, šablony a governance.

Operativní karta NESMÍ měnit význam referenční ústavy. Při konfliktu má přednost tento dokument a technická ústava.

---

## 6. POVINNÝ 7Q CHANGE GATE

Každá významná změna MUSÍ být před realizací a po ověření hodnocena v sedmi dimenzích.

### 6.1 SIMPLE — jednoduchá

Změna získá `VERIFIED_PASS / 10` pouze pokud:

- řeší jeden jasně vymezený problém,
- používá nejmenší bezpečný počet mechanismů,
- nevytváří druhou nebo třetí paralelní autoritativní cestu,
- každá komponenta má jednu hlavní odpovědnost,
- rozhraní jsou malá, explicitní a skládají se,
- závislosti jsou zdůvodněné,
- scope je pochopitelný bez rozsáhlé mentální rekonstrukce,
- proces změny není složitější než riziko, které řídí.

Povinné otázky:

1. Lze problém bezpečně vyřešit menším diffem?
2. Lze použít současný stack?
3. Přidáváme mechanismus, nebo pouze další variantu existujícího mechanismu?
4. Co můžeme odstranit nebo nesložitě nepřidat?
5. Lze výsledek použít a testovat samostatně?

Blokující anti-patterny:

- framework bez prokázané potřeby,
- abstrahování před druhým skutečným use case,
- orchestrace, která skrývá odpovědnost,
- duplicitní canonical kontrakty,
- konfigurační volba místo opravy špatného návrhu,
- dokument nebo formulář, který duplikuje jiný source of truth.

### 6.2 PURPOSEFUL — účelná

Změna získá `VERIFIED_PASS / 10` pouze pokud:

- je navázána na konkrétního uživatele, operátora nebo systémový outcome,
- obsahuje Jobs-to-be-Done nebo ekvivalentní popis požadovaného pokroku,
- problém má důkaz nebo je explicitně označen jako hypotéza,
- je definována současná alternativa nebo workaround,
- existuje success metric a guardrail,
- non-goals jsou explicitní,
- opportunity cost je známý,
- existuje kill criterion.

Povinné otázky:

1. Kdo tuto změnu „najímá“ a k jakému pokroku?
2. Co se dnes děje bez ní?
3. Jaký důkaz potvrzuje význam problému?
4. Jaké chování nebo stav se má změnit?
5. Co vědomě neřešíme?
6. Co uděláme, pokud se očekávaná hodnota nepotvrdí?

Technicky zajímavá práce bez účelu je `PROPOSED`, nikoli automaticky prioritní.

### 6.3 AUTOMATED — automatizovaná

Změna získá `VERIFIED_PASS / 10` pouze pokud:

- všechny opakovatelné mechanické kontroly jsou automatizované,
- manuální úsudek je omezen na rozhodnutí, která nelze bezpečně automatizovat,
- manuální krok má vlastníka, vstupy, výstup a auditní záznam,
- ověřovací příkazy jsou reprodukovatelné,
- gate je idempotentní nebo explicitně jednorázový,
- selhání je fail-closed,
- automatizace negeneruje falešný `PASS`, když kontrola nebyla provedena,
- rutinní evidence se vytváří automaticky.

`AUTOMATED=10` neznamená, že člověk nesmí rozhodovat. Znamená, že lidský úsudek není zneužit jako náhrada opakovatelné kontroly.

Blokující anti-patterny:

- „ověřeno pohledem“ tam, kde existuje deterministický parser nebo test,
- ruční kopírování výstupů bez hashů,
- gate, který při chybě pokračuje,
- CI job, který ignoruje exit code,
- `NOT_APPLICABLE` bez důvodu,
- skript měnící canonical repozitář během režimu VERIFY.

### 6.4 SECURE — bezpečná

Změna získá `VERIFIED_PASS / 10` pouze pokud:

- žádná identita, zařízení, proces, vstup, síťová poloha ani artefakt nemá implicitní důvěru,
- oprávnění jsou nejmenší potřebná,
- bezpečné výchozí nastavení je standard,
- trust boundaries jsou známé,
- vstupy a artefakty jsou autentizované nebo verifikované podle rizika,
- secrets nejsou v kódu, logu ani evidenci,
- supply-chain původ je dohledatelný,
- failure mode je bezpečný,
- zákazník není nucen kompenzovat nebezpečný návrh složitou konfigurací,
- high-risk změna má threat model nebo ekvivalentní security review.

Povinné oblasti podle relevance:

- autentizace a autorizace,
- data a privacy,
- dependency a supply chain,
- archivní extrakce,
- filesystem a shell hranice,
- síťové rozhraní,
- logging a redakce,
- build provenance,
- bezpečný rollback.

### 6.5 MEASURABLE — měřitelná

Změna získá `VERIFIED_PASS / 10` pouze pokud:

- existuje baseline nebo je absence baseline explicitně blokující,
- je definována cílová metrika,
- je definován datový zdroj,
- je definováno časové okno,
- je znám vlastník vyhodnocení,
- existuje alespoň jeden guardrail proti lokální optimalizaci,
- měření rozlišuje output, technické chování a product outcome,
- metrika je odolná proti snadnému gaming.

Příklady vrstev:

- `delivery`: lead time, deployment frequency, change failure rate, recovery time, rework rate,
- `reliability`: SLI, SLO, error budget, latency, availability, correctness,
- `quality`: defect escape, flaky tests, false-positive/false-negative rate,
- `product`: dokončený uživatelský job, adoption, úspora času, přesnost rozhodnutí,
- `guardrail`: privacy, náklady, support load, regressions.

Aktivita, počet commitů nebo počet řádků kódu nejsou samy o sobě outcome metriky.

### 6.6 REVERSIBLE — vratná

Změna získá `VERIFIED_PASS / 10` pouze pokud:

- je klasifikována její vratnost,
- rollback, disable, containment nebo exit path je konkrétní,
- rollback nezávisí na neověřené záloze,
- data migration má recovery nebo forward-fix strategii,
- rollback je otestován úměrně riziku,
- degradační režim je bezpečný,
- čas a ztráta dat při návratu jsou známé,
- irreversible část je co nejmenší a explicitně schválená.

Třídy:

- `R0` — čistě pozorovací, bez změny systému,
- `R1` — plně lokální a okamžitě vratná,
- `R2` — vratná přes checkpoint, flag nebo obnovu,
- `R3` — obtížně vratná, veřejné API, data nebo security boundary,
- `R4` — prakticky nevratná nebo destruktivní.

`R3` a `R4` vyžadují explicitní schválení, plán obnovy a nezávislou kontrolu.

### 6.7 PROVABLE — důkazně ověřitelná

Změna získá `VERIFIED_PASS / 10` pouze pokud:

- evidence identifikuje subject, prostředí, verzi a čas,
- příkazy nebo metody jsou uvedené,
- výsledky rozlišují passed, failed a not executed,
- artefakty mají digest,
- evidence je sanitizovaná, ale ne tak, aby ztratila ověřitelnost,
- tvrzení lze propojit s rozhodnutím, změnou, artefaktem a runtime výsledkem,
- evidence není pouze self-attestation autora,
- všechny relevantní unknowns jsou uvedeny.

Git je pouze jedna část důkazu. Úplný řetězec je:

```text
PROBLEM
→ PRODUCT BRIEF / HYPOTHESIS
→ DECISION / ADR / RFC
→ WORK BLOCK
→ SOURCE REVISION
→ TEST AND SECURITY EVIDENCE
→ BUILD ARTIFACT + PROVENANCE
→ RELEASE DECISION
→ DEPLOYED/RUNNING VERSION
→ LOGS / METRICS / TRACES
→ USER OR OPERATIONAL OUTCOME
→ KEEP / ITERATE / ROLLBACK / RETIRE
```

Přerušený řetězec musí být označen jako `PARTIALLY VERIFIED`.

### 6.8 Výsledek 7Q

Povolené stavy dimenze:

- `VERIFIED_PASS`
- `FAILED`
- `UNKNOWN`
- `NOT_APPLICABLE_APPROVED`

Pravidla:

- žádný aritmetický průměr,
- relevantní `FAILED` blokuje postup,
- relevantní `UNKNOWN` blokuje release a high-risk implementaci,
- `NOT_APPLICABLE_APPROVED` vyžaduje důvod a schvalovatele,
- celkový `10/10` je povolen pouze při `VERIFIED_PASS / 10` ve všech relevantních dimenzích,
- evidence gate MUSÍ být strojově validovatelná.

---

## 7. KONTEXTOVĚ PŘIMĚŘENÝ PROCES

Stejný proces NESMÍ být mechanicky aplikován na každý problém.

Každá práce se klasifikuje podle povahy situace:

### 7.1 CLEAR

Příčina a řešení jsou známé, existuje ověřený playbook.

Postup:

```text
SENSE → CATEGORIZE → RESPOND
```

Použij:

- standardní checklist,
- automatický gate,
- minimální dokumentaci.

### 7.2 COMPLICATED

Existuje více správných variant a je nutná expertní analýza.

Postup:

```text
SENSE → ANALYZE → RESPOND
```

Použij:

- varianty a trade-offs,
- ADR nebo decision record,
- cílené benchmarky.

### 7.3 COMPLEX

Příčina a výsledek nejsou předem plně předvídatelné.

Postup:

```text
PROBE → SENSE → RESPOND
```

Použij:

- malé safe-to-fail experimenty,
- více paralelních hypotéz, pokud je to levné,
- krátké feedback loops,
- zákaz falešné jistoty a dlouhého pevného plánu.

### 7.4 CHAOTIC

Systém je nestabilní a prvořadé je omezení škody.

Postup:

```text
ACT → SENSE → RESPOND
```

Použij:

- containment,
- bezpečný degradační režim,
- incident command,
- retrospektivu až po stabilizaci.

### 7.5 CONFUSED

Není jasné, do které domény problém patří.

Postup:

- nejprve rozdělit problém,
- sbírat fakta,
- neimplementovat velkou změnu,
- stav `BLOCKED` nebo `INVESTIGATING`.

Proces musí být dostatečný pro riziko, ale NESMÍ se stát samoúčelným.

---

## 8. RIZIKOVÉ TŘÍDY A PŘIMĚŘENOST GOVERNANCE

### T0 — TRIVIAL / OBSERVAČNÍ

Příklady:

- oprava překlepu,
- read-only report,
- formátování bez změny významu.

Požadavky:

- jednoduchý preflight,
- diff review,
- základní evidence.

### T1 — STANDARDNÍ VRATNÁ ZMĚNA

Příklady:

- malý bugfix,
- lokální UI změna,
- test nebo dokumentace s dopadem na workflow.

Požadavky:

- 7Q gate,
- targeted tests,
- regression podle dopadu,
- rollback.

### T2 — HRANIČNÍ / VYSOKÝ DOPAD

Příklady:

- veřejný kontrakt,
- persistence,
- data migration,
- auth,
- security boundary,
- build/release infrastruktura.

Požadavky:

- decision record nebo ADR,
- nezávislá kontrola,
- threat model,
- testovaný rollback,
- plná regression a evidence receipt.

### T3 — KRITICKÁ / DESTRUKTIVNÍ

Příklady:

- mazání dat,
- změna licence,
- rotace produkčních secrets,
- nevratná migrace,
- force push,
- veřejný release s obtížným návratem.

Požadavky:

- explicitní souhlas vlastníka,
- dvě ověřené zálohy, pokud relevantní,
- samostatná implementační fáze,
- dry run,
- recovery drill,
- go/no-go rozhodnutí.

Governance MUSÍ být proporcionální. T0 změna nesmí vyžadovat stejnou administrativu jako T3. T3 změna nesmí používat zjednodušený fast path.

---

## 9. PRODUKTOVÁ ČISTOTA

### 9.1 Jobs-to-be-Done

Každá významná capability MUSÍ popsat:

- aktéra,
- okolnosti,
- požadovaný pokrok,
- funkční, sociální nebo emoční rozměr podle relevance,
- současnou alternativu,
- důvod změny chování.

### 9.2 Working Backwards

Před velkou capability MUSÍ existovat stručný budoucí popis uživatelské hodnoty nebo ekvivalent PR/FAQ:

- co se pro uživatele změnilo,
- proč je to důležité,
- jak se to používá,
- jaká omezení zůstávají,
- jaké otázky by položil skeptický uživatel.

### 9.3 Nejmenší hodnotný řez

Řez MUSÍ být:

- použitelný nebo integrovaně ověřitelný,
- dost malý pro rychlou zpětnou vazbu,
- zakončený konkrétním outcome nebo learningem,
- bez skrytého závazku dokončit celý velký projekt.

Backend, který nelze použít ani kontraktně ověřit, není automaticky hodnotný vertikální řez.

### 9.4 Appetite místo falešné přesnosti

Před shapingem se určí maximální investice času a pozornosti.

- appetite je rozpočet, nikoli slib,
- scope se přizpůsobuje appetite,
- nekonečné rozšiřování scope je zakázané,
- pokud nelze vytvořit hodnotný řez v appetite, práce se znovu shapeuje nebo odmítne.

### 9.5 Kill criteria

Každá významná iniciativa MUSÍ mít podmínky, kdy:

- se zastaví,
- se zmenší,
- se vrátí do discovery,
- se rollbackuje,
- se odstraní.

---

## 10. ROZHODOVACÍ SYSTÉM

### 10.1 Jedno rozhodnutí, jeden vlastník

Každé významné rozhodnutí MUSÍ mít `Decision Owner`.

V malém projektu může jedna osoba zastávat více rolí, ale musí oddělit:

- autora návrhu,
- technického hodnotitele,
- security hodnotitele,
- product decision ownera,
- release ownera.

### 10.2 Povinné dimenze rozhodnutí

Decision record obsahuje:

- problém a kontext,
- dostupné důkazy,
- minimálně dvě realistické varianty nebo zdůvodnění jediné varianty,
- nejjednodušší přijatelnou variantu,
- trade-offs,
- rizika a unknowns,
- vratnost,
- opportunity cost,
- rozhodnutí a ownera,
- datum review nebo expiry.

### 10.3 Reversible versus irreversible

- snadno vratná rozhodnutí se dělají rychle,
- obtížně vratná rozhodnutí se dělají pomaleji a s více evidencí,
- nejistota sama o sobě není důvod k nečinnosti, pokud lze provést levný safe-to-fail experiment,
- rychlost rozhodnutí NESMÍ snižovat pravdivost výsledku.

### 10.4 Rozhodnutí v komplexní situaci

V komplexní doméně se NESMÍ předstírat, že analýza spolehlivě předpoví výsledek.

Místo toho:

- formuluj hypotézu,
- omez škodu,
- definuj signály,
- proveď malý experiment,
- rozhodni podle nových důkazů.

### 10.5 Expirace rozhodnutí

Rozhodnutí založené na dočasném omezení, trhu, toolchainu nebo riziku MUSÍ mít datum review.

Po expiraci není automaticky neplatné, ale musí být označeno `REVIEW_DUE`.

---

## 11. ROADMAP A WIP GOVERNANCE

### 11.1 Roadmap není seznam přání

Roadmap položka MUSÍ mít:

- vazbu na outcome,
- ownera,
- stav důkazu,
- appetite,
- riziko,
- závislosti,
- exit criteria.

### 11.2 Pořadí práce

Priority se určují podle:

1. bezpečnosti a ochrany dat,
2. produkčního nebo uživatelského rizika,
3. blokátorů toku hodnoty,
4. uživatelského outcome,
5. reliability a technického zdraví,
6. strategických enablerů,
7. kosmetických a volitelných změn.

### 11.3 WIP limit

Pro jednoho hlavního vývojáře platí výchozí limit:

- 1 aktivní implementační Work Block,
- 1 incident lane,
- 1 discovery/shaping lane.

Nový implementační WB se nezačne, dokud předchozí není:

- uzavřený,
- explicitně pozastavený s checkpointem,
- nebo rollbackovaný.

### 11.4 Stárnutí backlogu

Backlog položka bez nového důkazu nebo opakovaného signálu MUSÍ být periodicky:

- znovu potvrzena,
- odložena,
- sloučena,
- nebo odstraněna.

Udržování nekonečného backlogu není hodnota.

### 11.5 Kvalita a feature work

Plán MUSÍ rezervovat kapacitu pro:

- reliability,
- security,
- testy,
- observabilitu,
- dependency maintenance,
- odstranění zbytečné složitosti.

---

## 12. WORK BLOCK GOVERNANCE

Work Block je nejmenší řízená, testovatelná a vratná realizační jednotka.

### 12.1 Povinné vlastnosti

Každý WB MUSÍ mít:

- jeden cíl,
- jednu hlavní odpovědnost,
- vazbu na vyšší rozhodnutí nebo problém,
- explicitní non-goals,
- affected files nebo boundaries,
- invarianty,
- risk tier a context domain,
- 7Q pre-gate,
- implementační kroky,
- targeted tests,
- regression plan,
- security/privacy kontrolu,
- evidence,
- rollback,
- commit boundary,
- Definition of Done.

### 12.2 Velikost

Výchozí WB MĚL BY být dokončitelný v hodinách až několika dnech.

Pokud vyžaduje:

- více nezávislých commitů,
- více capability boundaries,
- několik různých rollbacků,
- nesouvisející refaktoring,

musí být rozdělen.

### 12.3 Scope drift

Nově objevená práce se:

- zaznamená,
- klasifikuje,
- nepřidá automaticky do aktivního WB.

Výjimkou je nezbytná oprava, bez které nelze bezpečně dokončit původní cíl; musí být explicitně přiznána.

### 12.4 Jeden logický commit

WB MĚL BY skončit jedním logickým commitem.

Pokud potřebuje více commitů, každý commit MUSÍ mít vlastní odpovědnost a ověřitelný mezistav.

### 12.5 Definition of Ready

WB není ready, pokud chybí:

- známý source of truth,
- vymezený cíl,
- bezpečný working directory,
- rollback nebo containment,
- test strategy,
- rozhodnutí o unknowns, které mohou změnit architekturu.

---

## 13. UNIXOVÁ JEDNODUCHOST A ARCHITEKTURNÍ HRANICE

### 13.1 Jedna hlavní odpovědnost

Program, modul, služba, skript i dokument MUSÍ mít jednu hlavní odpovědnost.

### 13.2 Skládání

Komponenty MĚLY BY:

- spolupracovat přes malá explicitní rozhraní,
- produkovat strukturované výstupy použitelné dalšími nástroji,
- být testovatelné samostatně,
- minimalizovat skryté globální stavy.

### 13.3 Ticho při úspěchu, informace při selhání

Automatizační nástroje MĚLY BY:

- mít stabilní exit codes,
- nezahlcovat úspěšný výstup,
- při selhání uvést konkrétní důvod a cestu k evidenci,
- oddělit human summary a machine-readable output.

### 13.4 Žádná paralelní autorita

Pro jednu odpovědnost má existovat jeden canonical mechanismus.

Před přidáním nové paralelní implementace je nutné:

- prokázat odlišnou capability boundary,
- definovat vztah k existující cestě,
- určit migraci nebo dlouhodobé oddělení,
- zabránit driftu kontraktů.

### 13.5 Architecture evidence

Významný systém MUSÍ mít podle potřeby:

- system context,
- container map,
- component map,
- data flow,
- trust boundaries,
- deployment model.

Diagramy nesmí míchat úrovně abstrakce ani používat neoznačené vztahy.

### 13.6 ADR jako malé modulární záznamy

Architektonické rozhodnutí se dokumentuje malým ADR, nikoli obřím statickým dokumentem.

ADR MUSÍ zachovat:

- kontext,
- rozhodnutí,
- status,
- důsledky.

---

## 14. AUTOMATIZAČNÍ A LOKÁLNÍ GATE MODEL

Cílový jednotný lokální tok:

```text
make doctor
→ make verify
→ make evidence
→ make checkpoint
→ make release-dry-run
```

Tento tok je `PROPOSED`, dokud není skutečně implementován a ověřen.

### 14.1 Doctor

Ověřuje:

- working directory,
- Git identity a stav,
- toolchain verze,
- lockfiles,
- dostupnost ústav,
- chybějící secrets nebo nebezpečné tracked secrets,
- základní runtime prerequisites.

### 14.2 Verify

Spouští podle relevance:

- format/lint,
- typecheck,
- unit,
- contract,
- integration,
- security,
- build,
- smoke.

### 14.3 Evidence

Vytváří sanitizovaný receipt:

- subject,
- HEAD,
- environment,
- commands,
- passed/failed/not-run,
- artifact digests,
- unknowns.

### 14.4 Checkpoint

Ověřuje:

- diff scope,
- index scope,
- test evidence,
- commit boundary,
- rollback,
- čistotu po commitu.

### 14.5 Release dry-run

Ověřuje bez vydání:

- artifact creation,
- versioning,
- migrations,
- installation,
- health/readiness,
- rollback,
- SBOM/licence/provenance podle maturity.

### 14.6 Lokální versus CI

- lokální gate je primární pro local-first workflow,
- CI MÁ zrcadlit stejná pravidla,
- CI NESMÍ být jediným místem, kde lze ověřit základní kvalitu,
- rozdíl lokálního a CI gate je defect.

---

## 15. BEZPEČNOST, ZERO TRUST A SECURE BY DESIGN

### 15.1 Žádná implicitní důvěra

Důvěra se neuděluje pouze proto, že je něco:

- lokální,
- ve stejné síti,
- v repozitáři,
- vytvořené vlastním skriptem,
- podepsané bez ověření identity a kontextu,
- z předchozího úspěšného běhu.

### 15.2 Resource-centric ochrana

Ochrana se vztahuje na:

- data,
- služby,
- workflow,
- identity,
- buildy,
- artefakty,
- evidence,
- release kanály.

### 15.3 Secure by default

Bezpečný stav MUSÍ být výchozí.

Uživatel NESMÍ být nucen:

- ručně zapínat základní ochranu,
- kupovat nebo konfigurovat audit log jako dodatečnou bezpečnost,
- opravovat nebezpečný default,
- znát interní security workaround.

### 15.4 Ownership bezpečnostního outcome

Výrobce systému nese odpovědnost za bezpečnostní outcome, nikoli pouze za zveřejnění instrukcí uživateli.

### 15.5 Secure SDLC

Security praktiky MUSÍ být integrované do celého životního cyklu:

- příprava organizace,
- ochrana software a build prostředí,
- tvorba bezpečného software,
- reakce na zranitelnosti.

### 15.6 Supply-chain integrity

Release artefakt MĚL BY postupně dosáhnout:

- dohledatelného source revision,
- reprodukovatelného build postupu,
- build provenance,
- podpisu nebo attestation,
- SBOM,
- verification policy.

Provenance dokazuje původ a způsob vytvoření; sama o sobě nedokazuje bezpečnost artefaktu.

---

## 16. EVIDENCE GRAPH A ÚPLNÁ AUDITOVATELNOST

### 16.1 Git není celý audit

Git historie dokazuje pouze část:

- obsah source revision,
- autora/committera podle Git identity,
- vztah commitů.

Nedokazuje sama o sobě:

- proč byla změna potřebná,
- kdo ji schválil,
- jaké testy skutečně proběhly,
- z jakého commitu vznikl binární artefakt,
- co bylo nasazeno,
- co runtime skutečně dělal,
- zda vznikl uživatelský outcome.

### 16.2 Povinné uzly evidence graphu

Podle relevance:

- `PROBLEM`
- `PRODUCT_BRIEF`
- `HYPOTHESIS`
- `DECISION`
- `RFC`
- `ADR`
- `WORK_BLOCK`
- `SOURCE_REVISION`
- `TEST_RECEIPT`
- `SECURITY_RECEIPT`
- `ARTIFACT`
- `PROVENANCE`
- `RELEASE_DECISION`
- `DEPLOYMENT/RUNTIME_INSTANCE`
- `TRACE/LOG/METRIC`
- `OUTCOME_REVIEW`

### 16.3 Povinné vazby

Každý nižší uzel MUSÍ odkazovat na vyšší rozhodovací kontext.

Minimálně:

```text
WB → DECISION/PROBLEM
COMMIT → WB
EVIDENCE → COMMIT/HEAD + ENVIRONMENT
ARTIFACT → COMMIT + BUILD RECEIPT
RELEASE → ARTIFACT + GATES
RUNTIME → RELEASE/ARTIFACT VERSION
OUTCOME → RUNTIME WINDOW + PRODUCT METRIC
```

### 16.4 Korelace runtime signálů

Distribuované nebo víceprocesové systémy MĚLY BY používat:

- correlation/request ID,
- trace context,
- stabilní event names,
- verzi aplikace a kontraktu,
- redakci citlivých dat.

### 16.5 Evidence immutability

Evidence receipt po uzavření:

- NESMÍ být tiše přepsán,
- MŮŽE být superseded novým receiptem,
- MUSÍ zachovat digest a vztah k předchozí verzi.

---

## 17. METRIKY, DORA A SRE

### 17.1 DORA jako trend, ne soutěž

Delivery metriky se používají pro zlepšení systému, nikoli hodnocení jednotlivců.

Sledují se podle relevance:

- change lead time,
- deployment frequency,
- failed deployment recovery time,
- change fail rate,
- deployment rework rate.

### 17.2 SLI, SLO a error budget

Kritická capability MUSÍ mít user-centric SLI a realistický SLO.

100% spolehlivost není automatický cíl. Musí se vyvážit:

- uživatelská potřeba,
- náklady,
- rychlost změn,
- riziko.

Error budget určuje prostor pro změnu a selhání.

Pokud je error budget vyčerpán:

- feature work se přehodnotí,
- reliability práce získá prioritu,
- výjimka vyžaduje explicitní risk acceptance.

### 17.3 Observabilita

Systém MUSÍ podle kritičnosti umožnit zjistit:

- zda běží,
- zda je připraven,
- jaká verze běží,
- kde a proč selhal,
- jak dlouho operace trvala,
- jaký uživatelský outcome je ovlivněn.

### 17.4 Alerting

Alert MUSÍ být:

- akční,
- navázaný na uživatelský nebo provozní dopad,
- s jasným ownerem,
- bez citlivých dat,
- pravidelně kontrolovaný na noise.

### 17.5 Incidenty a learning

Po významném incidentu vzniká:

- timeline,
- dopad,
- contributing factors,
- containment,
- recovery,
- preventivní opatření,
- ověření, že opatření funguje.

Cílem je systémové učení, nikoli hledání viníka.

---

## 18. RELEASE GOVERNANCE

Release není Git tag.

### 18.1 Release ready

Před release MUSÍ být podle relevance:

- scope uzavřený,
- 7Q gate passed,
- test evidence passed,
- security gate passed,
- artifact digest známý,
- provenance známá,
- migrace připravena,
- rollback připraven a odpovídá riziku,
- health/readiness ověření připravené,
- known limitations publikované,
- owner určený.

### 18.2 Release typy

- `ENGINEERING_PROOF`
- `INTERNAL_ALPHA`
- `PRIVATE_BETA`
- `PUBLIC_BETA`
- `GENERAL_AVAILABILITY`
- `SECURITY_PATCH`
- `EMERGENCY_RELEASE`

Každý typ má vlastní exit criteria.

### 18.3 Progressive delivery

Riziková capability MĚLA BY používat:

- feature flag,
- opt-in,
- shadow mode,
- subset rollout,
- canary,
- kill switch,

pokud tyto mechanismy nezvyšují nepřiměřeně složitost.

### 18.4 Emergency release

Emergency release MŮŽE zkrátit discovery a dokumentaci, ale NESMÍ vynechat:

- containment goal,
- minimální bezpečnostní kontrolu,
- rollback,
- evidence,
- následnou retrospektivu a doplnění chybějících artefaktů.

---

## 19. POST-RELEASE VALIDACE

Release bez outcome review je `RELEASED / NOT YET VALIDATED`.

Outcome review musí odpovědět:

- používá se capability očekávaným způsobem?
- zlepšila cílovou metriku?
- neporušila guardrails?
- jaké failure patterns vznikly?
- jaká je reliability a support load?
- co jsme se naučili?

Povolená rozhodnutí:

- `KEEP`
- `ITERATE`
- `ROLLBACK`
- `DEPRECATE`
- `RETIRE`

Nevyhodnocená capability NESMÍ být prezentována jako produktově úspěšná.

---

## 20. AI, ML A AUTOMATIZOVANÁ ROZHODNUTÍ

### 20.1 Oddělené vrstvy

MUSÍ být odděleny:

- observation/data,
- analysis/model output,
- assessment,
- recommendation,
- explanation,
- human decision,
- feedback.

### 20.2 Provenance

Každý významný AI výstup MUSÍ podle relevance uvádět:

- model/provider,
- verzi,
- konfiguraci,
- vstupní data nebo jejich identifikátor,
- timestamp,
- confidence/uncertainty,
- warnings,
- fallback path.

### 20.3 Unknown místo fabricated value

Když není důkaz, systém MUSÍ vrátit `UNKNOWN`, `UNAVAILABLE` nebo ekvivalent.

Zakázáno:

- vymyšlené confidence,
- náhodné placeholder scoring v produkčním rozhodování,
- tichý fallback vydávaný za primární model,
- explanation, která neodpovídá skutečnému skóre.

### 20.4 Human agency

AI NESMÍ automaticky převzít nevratné nebo významné rozhodnutí bez explicitně navržené authority.

Pro APPLAYLIST platí:

- systém analyzuje,
- vyhodnocuje,
- doporučuje,
- vysvětluje,
- zobrazuje nejistotu,
- finální rozhodnutí ponechává DJovi.

### 20.5 Evaluace

AI capability MUSÍ mít podle relevance:

- reprezentativní evaluation set,
- versioned metrics,
- false-positive/false-negative analýzu,
- drift monitoring,
- baseline comparison,
- rollback modelu nebo policy,
- privacy review.

### 20.6 Feedback

Feedback NESMÍ tiše měnit model truth.

Musí být:

- oddělený od assessmentu,
- versioned,
- auditovatelný,
- použitelný pouze přes schválený learning proces.

---

## 21. APPLAYLIST PRODUKTOVÉ INVARIANTY

1. APPLAYLIST nerozhoduje místo DJ.
2. Tonalita NESMÍ být binární hard gate.
3. Tonalita má podle profilu tvořit přibližně 10–25 % transition skóre.
4. Klasifikace `SAFE`, `POSSIBLE`, `CREATIVE`, `RISKY`, `UNKNOWN` NESMÍ automaticky zakázat skladbu.
5. Analysis, assessment, recommendation, explanation a user decision jsou oddělené kontrakty.
6. Každé analytické tvrzení má provenance a confidence nebo explicitní unknown.
7. Chybějící phrase/vocal/bass extractor NESMÍ generovat vymyšlené hodnoty.
8. Scoring musí být deterministický pro stejné vstupy, verzi a konfiguraci.
9. Explainability musí být odvozena ze skutečného assessmentu.
10. Uživatel musí vidět nejistotu a významná rizika přechodu.
11. Privacy-first a local-first jsou výchozí produktové vlastnosti.
12. Renderer NESMÍ získat přímou neomezenou filesystem, shell nebo network autoritu.
13. Filesystem přístup má používat opaque capabilities nebo ekvivalent least privilege.
14. Uživatelovo explicitní rozhodnutí nesmí tiše měnit historický assessment.
15. Každý release analytické logiky musí být verzovaný a srovnatelný s baseline.
16. Preview-required stav musí být použit, když confidence nestačí pro silné doporučení.
17. Produkt NESMÍ vydávat scaffold nebo fixed-percentage heuristiku za skutečnou segmentovou audio analýzu.

---

## 22. ORGANIZAČNÍ A KOGNITIVNÍ JEDNODUCHOST

### 22.1 Kognitivní zátěž je architektonické omezení

Proces, architektura a tooling NESMÍ vyžadovat, aby jeden člověk držel v hlavě nepřiměřené množství nesouvisejících detailů.

### 22.2 Jasné hranice vlastnictví

Každá capability má:

- ownera,
- boundary,
- veřejný kontrakt,
- provozní odpovědnost,
- očekávané interakce.

### 22.3 Platforma jako produkt

Sdílené tooling a platformní schopnosti musí:

- snižovat kognitivní zátěž,
- mít jednoduché self-service rozhraní,
- mít dokumentovaný support model,
- nebýt dumping ground pro nesouvisející odpovědnosti.

### 22.4 Governance budget

Každá povinná procesní položka MUSÍ prokazatelně:

- snižovat riziko,
- zlepšovat rozhodnutí,
- zrychlovat flow,
- nebo zachovávat auditovatelnost.

Pokud artefakt pouze duplikuje informace, musí být sloučen nebo odstraněn.

---

## 23. FAST PATHY A ZÁKAZ AUDITNÍCH SMYČEK

### 23.1 Bug fast path

Dobře reprodukovaný bug MŮŽE přeskočit plný Product Brief, pokud existuje:

- reprodukce,
- očekávané chování,
- regression test,
- risk klasifikace,
- rollback.

### 23.2 Dokumentační fast path

T0 dokumentační změna může použít zkrácený gate, pokud nemění:

- normativní význam,
- veřejný kontrakt,
- security instrukce,
- release claim.

### 23.3 Incident fast path

V chaosu je prioritou containment. Chybějící dokumentace se doplní po stabilizaci.

### 23.4 Audit musí skončit rozhodnutím

Každý audit MUSÍ skončit jedním z výsledků:

- `IMPLEMENT NEXT TARGETED WB`,
- `DECIDE BETWEEN OPTIONS`,
- `HOLD WITH EXPLICIT MISSING EVIDENCE`,
- `STOP / RETIRE`.

### 23.5 Zákaz opakovaných širokých auditů

Po ověření source-of-truth baseline:

- další audit MUSÍ být cílený na konkrétní unknown nebo riziko,
- široký audit se opakuje pouze při změně source of truth nebo poškození evidence,
- maximálně dva po sobě jdoucí auditní WB mohou proběhnout bez implementace, rozhodnutí nebo explicitního zastavení.

Audit bez rozhodnutí a bez snížení uncertainty je procesní defect.

---

## 24. VÝJIMKY A RISK ACCEPTANCE

Výjimka je přípustná pouze pokud obsahuje:

- porušené pravidlo,
- důvod,
- rozsah,
- riziko,
- kompenzační kontroly,
- ownera,
- expiry,
- review trigger.

Výjimka NESMÍ:

- legitimizovat již provedenou nebezpečnou změnu zpětně,
- být trvalá bez review,
- skrývat `UNKNOWN`,
- převést `FAILED` na `PASS`.

Po expiraci je stav `BLOCKED`, dokud není výjimka znovu schválena nebo odstraněna.

---

## 25. POVINNÉ GATES G0–G9

### G0 — REALITY

- source of truth ověřen,
- autoritativní ústavy dostupné,
- skutečný cíl známý,
- stav pravdivosti určen.

### G1 — PROBLEM

- aktér a JTBD známý,
- evidence problému nebo hypotéza označena,
- baseline a workaround známé.

### G2 — SHAPE

- nejmenší hodnotný řez,
- appetite,
- non-goals,
- failure modes,
- kill criteria.

### G3 — DECIDE

- varianty,
- trade-offs,
- owner,
- risk/context klasifikace,
- rozhodnutí a expiry.

### G4 — 7Q READY

- všech sedm dimenzí před realizací vyhodnoceno,
- žádný blokující unknown,
- automatizovatelný gate připraven.

### G5 — IMPLEMENT

- scope dodržen,
- změna malá a logická,
- žádná neautorizovaná vedlejší změna.

### G6 — VERIFY

- targeted checks,
- regression,
- security/privacy,
- evidence receipt,
- 7Q post-gate.

### G7 — CHECKPOINT

- diff review,
- commit boundary,
- rollback,
- artifact/evidence digests,
- Git stav ověřen.

### G8 — RELEASE

- artifact a provenance,
- release decision,
- health/readiness,
- rollout a rollback.

### G9 — VALIDATE

- outcome a guardrails,
- reliability,
- feedback,
- keep/iterate/rollback/retire.

Gate lze zkrátit pouze podle risk/context fast pathu. Gate nelze tiše přeskočit.

---

## 26. POVINNÉ KANONICKÉ ARTEFAKTY

Podle rozsahu projektu:

- `VISION.md`
- `PRODUCT.md`
- `ROADMAP.md`
- `STATUS.md`
- `ARCHITECTURE.md`
- `SECURITY.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `foundation/IDENTITY.md`
- `foundation/PRODUCT_PRINCIPLES.md`
- `foundation/DECISION_MODEL.md`
- `foundation/TERMINOLOGY.md`
- `docs/product/`
- `docs/specifications/`
- `docs/decisions/`
- `docs/rfcs/`
- `docs/work-blocks/`
- `docs/evidence/`
- `docs/releases/`
- `docs/operations/`

Každý normativní dokument má metadata:

```yaml
id:
title:
status:
version:
owner:
created:
updated:
supersedes:
related:
```

Stavy dokumentů:

- `DRAFT`
- `PROPOSED`
- `ACCEPTED`
- `IMPLEMENTED`
- `VERIFIED`
- `SUPERSEDED`
- `DEPRECATED`

---

## 27. MINIMÁLNÍ ŠABLONY

### 27.1 7Q Change Gate

```yaml
change_id:
title:
truth_status:
lifecycle_status:
risk_tier:
context_domain:
quality:
  simple:
    status:
    score:
    evidence: []
  purposeful:
    status:
    score:
    evidence: []
  automated:
    status:
    score:
    evidence: []
  secure:
    status:
    score:
    evidence: []
  measurable:
    status:
    score:
    evidence: []
  reversible:
    status:
    score:
    evidence: []
  provable:
    status:
    score:
    evidence: []
gate_result:
remaining_unknowns: []
```

### 27.2 Product Brief

```markdown
# PB-XXXX: Název

## Aktér a Jobs-to-be-Done
## Okolnosti a současný workaround
## Důkazy problému
## Baseline
## Požadovaný outcome
## Success metric
## Guardrails
## Appetite
## Non-goals
## Unknowns
## Kill criteria
```

### 27.3 Decision Record

```markdown
# DEC-XXXX: Název

## Status a owner
## Context domain a risk tier
## Kontext a důkazy
## Varianty
## Nejjednodušší přijatelná varianta
## Rozhodnutí
## Trade-offs
## Reversibility
## Residual risk
## Expiry / review
```

### 27.4 Work Block

```markdown
# WB-XXXX: Název

## Cíl
## Vazba na problém/rozhodnutí
## Non-goals
## Risk/context
## 7Q pre-gate
## Working directory a preflight
## Affected boundaries/files
## Invarianty
## Implementace
## Targeted tests
## Regression
## Security/privacy
## Evidence
## Rollback
## Commit boundary
## 7Q post-gate
## Definition of Done
```

### 27.5 Evidence Receipt

```markdown
# EVD-XXXX

## Subject
## Repository / HEAD / artifact / environment
## Commands and methods
## Passed
## Failed
## Not executed
## Digests
## Runtime correlation
## Remaining unknowns
## Truthful conclusion
```

### 27.6 Release Decision

```markdown
# REL-XXXX

## Release type
## Scope and excluded work
## Included checkpoints and artifacts
## Provenance and SBOM
## Known limitations
## Migration
## Rollout
## Health/readiness verification
## Rollback
## Go / No-Go
## Owner
```

---

## 28. DEFINITION OF DONE

### 28.1 Work Block Done

WB je done pouze pokud:

- cíl je splněn,
- scope je omezený,
- implementace skutečně existuje,
- targeted tests prošly,
- relevantní regression prošla,
- security/privacy gate prošel,
- rollback je známý,
- evidence receipt existuje,
- 7Q post-gate prošel,
- commit boundary je připraven nebo commit ověřen,
- remaining unknowns jsou explicitní.

### 28.2 Capability Done

Capability je done pouze pokud:

- problém a outcome jsou definované,
- rozhodnutí je přijaté,
- implementace je verified,
- release je verified,
- observabilita funguje,
- outcome je validovaný,
- guardrails nejsou porušené,
- existuje rozhodnutí keep/iterate/rollback/retire.

Bez outcome evidence je stav `RELEASED / NOT YET VALIDATED`.

### 28.3 Produkt v1.0 Done

Produkt není `COMPLETE`, dokud nejsou skutečně ověřena relevantní kritéria technické a produktové ústavy, včetně:

- canonical repo,
- reprodukovatelného build/install,
- bezpečnosti a privacy,
- migration/rollback,
- spolehlivosti,
- observability,
- artefact provenance,
- performance,
- uživatelské validace,
- dokumentace a support modelu.

---

## 29. ANTI-PATTERNY

### Produkt

- feature bez důkazu problému,
- řešení hledající problém,
- metrika bez baseline,
- roadmap jako seznam přání,
- neomezený backlog,
- „ještě jedna funkce“ před feedbackem,
- zaměnění technického outputu za outcome.

### Rozhodování

- consensus bez ownera,
- rozhodnutí bez alternativ,
- irreversible změna bez recovery,
- analýza donekonečna,
- falešná jistota v komplexní situaci,
- výjimka bez expirace.

### Realizace

- několik aktivních WB,
- velký nesouvisející diff,
- paralelní canonical cesty,
- test až po implementaci bez regression cíle,
- ruční opakovatelné kroky,
- broad audit opakovaný bez změny baseline,
- automatizace, která mění stav při VERIFY.

### Bezpečnost

- implicitní důvěra k lokálnímu procesu,
- nebezpečný default,
- customer-side workaround místo upstream opravy,
- secrets v evidenci,
- provenance zaměněná za bezpečnost,
- security až před release.

### Evidence

- screenshot bez identifikace prostředí,
- PASS bez příkazu nebo metody,
- hash bez subjectu,
- log bez verze,
- commit bez vazby na rozhodnutí,
- release bez vazby na artefakt,
- „10/10“ bez strojově validovaného gate.

### AI

- fabricated values,
- tichý fallback,
- confidence bez kalibrace,
- explanation drift,
- automatická změna truth z feedbacku,
- člověk bez možnosti override.

---

## 30. ZMĚNY TÉTO ÚSTAVY

Změna ústavy vyžaduje samostatný WB a musí obsahovat:

- problém současného pravidla,
- evidence,
- navržené znění,
- dopad na rychlost, kognitivní zátěž, bezpečnost a auditovatelnost,
- migrační plán,
- superseded části,
- schválení vlastníka.

Ústava NESMÍ být změněna během incidentu jen proto, aby legitimizovala probíhající výjimku.

Každá verze se zachovává a má SHA-256.

---

## 31. PŘIJETÍ, AKTIVACE A PROVOZNÍ OVĚŘENÍ

Přijetí a provozní ověření jsou dvě rozdílné fáze a NESMÍ být zaměněny.

### 31.1 Fáze A — PROPOSED

Dokument zůstává `PROPOSED`, dokud není:

1. přezkoumán proti technické ústavě,
2. explicitně přijat vlastníkem projektu,
3. uložen do canonical repozitáře pod canonical filename,
4. doprovázen operativní kartou, schema kontraktem a change-gate validátorem.

Stav:

```text
TRUTH_STATUS=PROPOSED
LIFECYCLE_STATUS=PROPOSED
IMPLEMENTED=NO
```

### 31.2 Fáze B — ACCEPTED / PILOT ACTIVE

Dokument získá stav `ACCEPTED` pouze po vytvoření samostatného logického commitu, který:

- obsahuje canonical dokument,
- obsahuje technickou ústavu nebo ověřuje její canonical SHA-256,
- obsahuje operativní kartu a validátor,
- obsahuje SHA-256 manifest,
- nemíchá produktový kód ani nesouvisející změny,
- má ověřený rollback a lokální Git bundle nebo ekvivalentní checkpoint.

Po tomto commitu je ústava závazným pravidlem pro pilotní provoz, ale NESMÍ být označena jako provozně `VERIFIED`.

Stav:

```text
TRUTH_STATUS=IMPLEMENTED
LIFECYCLE_STATUS=ACCEPTED
OPERATIONAL_VERIFICATION=PARTIALLY_VERIFIED
ACTIVATION=PILOT_ACTIVE
```

### 31.3 Fáze C — VERIFIED / ACTIVE

Provozní stav `VERIFIED / ACTIVE` vyžaduje alespoň tři různé pilotní Work Blocky:

1. T0/T1 fast path,
2. standardní T1/T2 implementace,
3. T2/T3 security, migration nebo release gate.

Každý pilot MUSÍ změřit:

- preparation time,
- lead time,
- skutečně použité povinné položky,
- unknowns nalezené před implementací,
- rework zabráněný nebo způsobený governance,
- kvalitu rollbacku,
- rekonstruovatelnost evidence graphu,
- kognitivní zátěž.

Po třech pilotech MUSÍ vzniknout samostatný review WB s rozhodnutím:

```text
KEEP
ITERATE
ROLLBACK
SUPERSEDE
```

Pouze rozhodnutí `KEEP` nebo schválené `ITERATE` s odstraněnými P0/P1 nedostatky může změnit stav na:

```text
TRUTH_STATUS=VERIFIED
LIFECYCLE_STATUS=VERIFIED
ACTIVATION=ACTIVE
```

Přijetí dokumentu tedy není tvrzením, že jeho dlouhodobá ergonomie nebo dopad jsou již ověřené.

---

## 32. POVINNÝ ZÁVĚR VÝSTUPU

Každý významný produktový nebo realizační výstup MUSÍ zakončit:

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
IMPLEMENTED:
VERIFIED:
RELEASED:
VALIDATED:
RISKS:
NEXT DECISION:
NEXT SAFE STEP:
```

Žádná položka nesmí být vyplněna přesvědčivěji, než dovolují důkazy.

---

## 33. VÝZKUMNÝ ZÁKLAD

Tato V2 syntetizuje, ale nekopíruje, zejména tyto přístupy:

- Jobs-to-be-Done — pokrok uživatele v konkrétních okolnostech,
- Amazon Working Backwards — začít hodnotou a zákaznickou cestou,
- Apple design principles — účel, pochopení člověka a redukce rušení,
- Unix — malé části s jednou odpovědností, skládání a nástroje,
- Shape Up — shaping, appetite, boundaries a bets,
- Linear Method — purpose-built systém, momentum, jednoduchost a zákaz busywork,
- GitLab product flow — validation/build tracks a outcome gates,
- Cynefin — proces odpovídající clear/complicated/complex/chaotic situaci,
- ADR — malé modulární záznamy rozhodnutí,
- C4 — konzistentní úrovně architektonické abstrakce,
- Team Topologies — flow hodnoty a řízení kognitivní zátěže,
- DORA — měření toku a stability delivery systému,
- Google SRE — SLO, error budgets, observabilita a learning,
- NIST Zero Trust — žádná implicitní důvěra podle umístění,
- NIST SSDF — security integrovaná v SDLC,
- CISA Secure by Design — ownership bezpečnostních outcomes a secure defaults,
- NIST AI RMF — AI riziko v celém životním cyklu,
- SLSA/OpenSSF — build a source provenance,
- OpenTelemetry — korelace runtime signálů přes procesní hranice,
- RFC 2119/8174 — jednoznačný normativní jazyk.

Výzkumné zdroje, přijaté principy a odmítnuté anti-patterny jsou popsány v `RESEARCH_AND_DESIGN_RATIONALE_V2.md`.
