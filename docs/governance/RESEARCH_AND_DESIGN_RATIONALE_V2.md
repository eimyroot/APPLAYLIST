---
id: APPLAYLIST-RESEARCH-002
title: Výzkumný a návrhový základ Produktové, rozhodovací a realizační ústavy V2
status: VERIFIED_RESEARCH_SYNTHESIS
version: 1.0.0
owner: Eimy
created: 2026-07-26
updated: 2026-07-26
related:
  - PRODUCT_DECISION_EXECUTION_CONSTITUTION_V2.md
---

# VÝZKUMNÝ A NÁVRHOVÝ ZÁKLAD V2

## 1. Výzkumná otázka

Jak vytvořit governance systém, který současně maximalizuje:

- produktovou čistotu,
- jednoduchost,
- rychlost toku,
- automatizaci,
- spolehlivost,
- bezpečnost,
- měřitelnost,
- vratnost,
- úplnou auditovatelnost,

aniž by produkoval falešné `10/10` výsledky nebo procesní byrokracii?

## 2. Hlavní závěr

Silný systém nesmí používat jednu univerzální metodiku ani jedno průměrné skóre.

V2 proto kombinuje:

1. **pevné invarianty** — pravdivost, 7Q, security, evidence;
2. **kontextově přiměřený proces** — clear/complicated/complex/chaotic;
3. **proporcionální governance** — T0 až T3;
4. **krátkou operativní kartu** — nízká kognitivní zátěž;
5. **plnou referenční ústavu** — výjimky a high-risk případy;
6. **strojově validovaný gate** — zákaz nedoloženého `10/10`;
7. **evidence graph** — problém až outcome, nikoli jen Git.

## 3. Přijaté principy podle zdrojů

### Jobs-to-be-Done

Zdroj: [Christensen Institute — Jobs to Be Done Theory](https://www.christenseninstitute.org/theory/jobs-to-be-done/)

Přijato:

- produkt se posuzuje podle pokroku člověka v konkrétních okolnostech;
- demografie ani seznam funkcí nestačí;
- Product Brief musí popsat aktéra, okolnosti, pokrok a současnou alternativu.

### Amazon Working Backwards

Zdroj: [AWS Prescriptive Guidance — Start with why](https://docs.aws.amazon.com/prescriptive-guidance/latest/strategy-product-development/start-with-why.html)

Přijato:

- začít zákaznickou cestou, hodnotou a očekávaným outcome;
- PR/FAQ nebo ekvivalent jako nástroj zpřesnění scope a komunikace;
- roadmap odvozovat od hodnoty, nikoli od technického seznamu.

### Apple design principles

Zdroj: [Apple Human Interface Guidelines — Design principles](https://developer.apple.com/design/human-interface-guidelines/design-principles)

Přijato:

- vytvářet něco smysluplného;
- rozhodování zakládat na hlubokém pochopení člověka;
- design používat jako nástroj vyvažování konkurenčních priorit, nikoli jako dekoraci.

### Unix

Zdroj: [Nokia Bell Labs archive — Creating a programming philosophy from pipes and a tool box](https://www.nokia.com/bell-labs/unix-history/philosophy.html)

Přijato:

- jedna hlavní odpovědnost;
- malé části, které spolupracují;
- nástroje a automatizace místo opakované ruční práce;
- jednoduché skládání a stabilní rozhraní.

Zpřesnění pro moderní systémy:

- „text stream“ není dogma; povolené jsou strukturované kontrakty;
- jednoduchost neznamená ignorování security, typů nebo transakcí.

### Shape Up

Zdroje:

- [Set Boundaries](https://basecamp.com/shapeup/1.2-chapter-03)
- [Write the Pitch](https://basecamp.com/shapeup/1.5-chapter-06)

Přijato:

- appetite místo falešně přesného odhadu;
- shaping před realizací;
- jasné boundaries a rabbit holes;
- hodnotný řez přizpůsobit investici, ne nekonečně zvětšovat rozpočet.

Nepřijato jako univerzální pravidlo:

- pevný šestitýdenní cyklus pro každý typ práce.

### Linear Method

Zdroje:

- [Principles & Practices](https://linear.app/method/introduction)
- [Scope projects down](https://linear.app/method/scope-projects)
- [Generate momentum](https://linear.app/method/building-with-momentum)

Přijato:

- purpose-built proces;
- simple first, then powerful;
- odstraňovat busywork;
- krátké projekty a rychlé feedback loops;
- rozhodnout a pokračovat, pokud je rozhodnutí vratné;
- udržovat zvládnutelný backlog.

### GitLab Product Development Flow

Zdroj: [GitLab Handbook — Product Development Flow](https://handbook.gitlab.com/handbook/product-development/how-we-work/product-development-flow/)

Přijato:

- oddělení validation track a build track;
- fáze definované outcome, nikoli pouze aktivitou;
- možnost zkrátit nebo přeskočit fázi při vysoké confidence;
- single source of truth pro stav práce;
- launch následovaný měřením a iterací.

Odmítnuto:

- mechanicky lineární interpretace procesu;
- rozsáhlé label/status ceremony bez přidané hodnoty pro malý projekt.

### Cynefin

Zdroje:

- [The Cynefin Framework](https://thecynefin.co/about-cynefin-framework/)
- [Decision support tool](https://thecynefin.co/effective-decision-making-support-tool/)

Přijato:

- jiný rozhodovací režim pro clear, complicated, complex a chaotic situace;
- safe-to-fail probes v komplexní doméně;
- containment first v chaosu;
- zákaz vynucovat standardní řešení na komplexní problém.

### ADR

Zdroj: [Michael Nygard — Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)

Přijato:

- malé modulární záznamy;
- kontext, rozhodnutí a důsledky;
- dokumentace má sloužit týmu a být udržovatelná;
- obří statické dokumenty nejsou náhradou živých rozhodnutí.

### C4 model

Zdroj: [C4 model official site](https://c4model.com/)

Přijato:

- hierarchické úrovně system/context/container/component/code;
- konzistentní abstrakce;
- zákaz míchat úrovně a neoznačovat vztahy.

### Team Topologies

Zdroje:

- [Team Topologies](https://teamtopologies.com/)
- [Core team types](https://teamtopologies.com/key-concepts-content/what-are-the-core-team-types-in-team-topologies)

Přijato:

- flow hodnoty jako organizační cíl;
- kognitivní zátěž jako architektonické omezení;
- jasné ownership boundaries;
- platforma jako produkt s self-service rozhraním;
- týmové interakce mají být explicitní.

Pro jednočlenný projekt se princip aplikuje jako oddělení „rolí/klobouků“, capability boundaries a omezení paralelní práce.

### DORA

Zdroj: [DORA software delivery performance metrics](https://dora.dev/guides/dora-metrics/)

Přijato:

- měřit throughput a stability společně;
- používat delivery metriky k učení systému, ne k hodnocení jednotlivců;
- sledovat trend a rework, ne pouze frekvenci změn.

### Google SRE a Well-Architected reliability

Zdroje:

- [Google SRE resources](https://sre.google/resources/)
- [Set realistic targets for reliability](https://cloud.google.com/architecture/framework/reliability/choose-slos)
- [Operational excellence](https://docs.cloud.google.com/architecture/framework/operational-excellence)

Přijato:

- user-centric SLI/SLO;
- error budget;
- 100% reliability není automatický cíl;
- automation redukuje toil;
- observability, incident response a learning;
- reliability se vyvažuje s hodnotou a náklady.

### NIST Zero Trust

Zdroj: [NIST SP 800-207 — Zero Trust Architecture](https://www.nist.gov/publications/zero-trust-architecture)

Přijato:

- žádná implicitní důvěra podle fyzické nebo síťové polohy;
- zaměření na resources, identity a jednotlivé sessions;
- lokální proces, soubor nebo síť nejsou automaticky důvěryhodné.

### NIST SSDF

Zdroj: [NIST SP 800-218 — Secure Software Development Framework](https://csrc.nist.gov/pubs/sp/800/218/final)

Přijato:

- security musí být integrována do SDLC;
- organizace, ochrana software, secure production a vulnerability response;
- společný jazyk pro producenty a konzumenty software.

### CISA Secure by Design

Zdroj: [Applying Secure by Design Thinking](https://www.cisa.gov/news-events/news/applying-secure-design-thinking-events-news)

Přijato:

- ownership customer security outcomes;
- radical transparency and accountability;
- secure by default;
- security je produktová a leadership odpovědnost;
- zákaz přenášet základní bezpečnostní práci na uživatele.

### NIST AI RMF

Zdroj: [NIST AI RMF 1.0](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10)

Přijato:

- AI risk management v celém životním cyklu;
- trustworthiness, měření a governance;
- use-case-specific a adaptivní aplikace;
- human agency, transparency, uncertainty a monitoring.

### SLSA / OpenSSF

Zdroje:

- [SLSA specification v1.2](https://slsa.dev/spec/v1.2/)
- [SLSA provenance](https://slsa.dev/spec/v1.2/provenance)

Přijato:

- provenance jako verifikovatelná informace, kde, kdy a jak artefakt vznikl;
- source a build provenance;
- postupné úrovně supply-chain assurance;
- provenance není automatický důkaz bezpečnosti.

### OpenTelemetry

Zdroj: [Context propagation](https://opentelemetry.io/docs/concepts/context-propagation/)

Přijato:

- korelace traces, metrics a logs;
- causal flow přes procesní a síťové hranice;
- runtime audit musí používat context/correlation IDs podle architektury.

### RFC 2119 a RFC 8174

Zdroje:

- [RFC 2119](https://www.rfc-editor.org/info/rfc2119/)
- [RFC 8174](https://www.rfc-editor.org/info/rfc8174/)

Přijato:

- jednoznačný normativní jazyk;
- speciální význam pouze pro uppercase keywords;
- normativní termíny používat střídmě.

## 4. Zásadní konstrukční změny proti V1

### 4.1 Exact Prime Directive

V1 obsahovala principy rozptýleně. V2 je staví jako první normativní axiom.

### 4.2 7Q bez průměrování

V1 připouštěla podpůrná čísla, ale neměla tvrdý model „nejnižší dimenze rozhoduje“.

V2 zakazuje kompenzaci slabiny jinou silnou stránkou.

### 4.3 Strojový gate

V2 má JSON Schema a validátor. `10/10` je technicky odmítnuto, pokud chybí evidence nebo je některá dimenze unknown/failed.

### 4.4 Dvouvrstvá governance

V1 měla přes 1 400 řádků a byla příliš těžká pro každodenní použití.

V2 přidává krátkou operativní kartu. Plná ústava zůstává referencí pro high-risk a neobvyklé situace.

### 4.5 Proporcionální proces

V2 kombinuje context domain a risk tier. T0 oprava nemá stejnou ceremony jako T3 migrace.

### 4.6 Audit loop breaker

V2 zakazuje opakované široké audity bez změny source of truth a vyžaduje rozhodnutí nebo cílený další krok.

### 4.7 Evidence graph

V2 explicitně propojuje:

```text
problem → decision → WB → commit → test → artifact → release → runtime → outcome
```

### 4.8 Governance budget

Každý povinný procesní artefakt musí snižovat riziko, zlepšovat rozhodnutí, flow nebo auditovatelnost. Duplicity se odstraňují.

## 5. Co bylo záměrně odmítnuto

- univerzální rigidní proces pro všechny situace;
- průměrné „quality score“;
- `10/10` založené na sebehodnocení;
- Git jako jediný auditní systém;
- CI jako jediný quality gate;
- nekonečný backlog;
- několik paralelních aktivních Work Blocků;
- dokumentace pro dokumentaci;
- fixní časový cyklus pro incidenty a high-risk migrace;
- automatizace lidských rozhodnutí pouze proto, že je technicky možná;
- security kontrola až na konci;
- provenance zaměněná za inherentní důvěryhodnost.

## 6. Omezení výzkumu

- Výzkumné zdroje představují rozdílné organizace a kontexty; jejich postupy nejsou univerzální zákony.
- V2 je syntéza přizpůsobená malému local-first projektu APPLAYLIST.
- Praktická ergonomie a účinnost V2 nejsou dosud ověřeny v canonical repozitáři.
- Skutečné přijetí vyžaduje pilot na minimálně třech různých Work Blocích.

## 7. Pravdivý závěr

V2 je silnější návrh než V1 v:

- explicitní jednoduchosti,
- anti-bureaucracy mechanismech,
- context-aware rozhodování,
- strojové kontrole tvrzení `10/10`,
- runtime a outcome auditovatelnosti.

Není však oprávněné tvrdit, že je objektivně `10/10`, dokud neprojde praktickou adopcí a měřením.
