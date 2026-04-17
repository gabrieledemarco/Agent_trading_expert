# Audit dashboard statiche + piano di dynamicizzazione

Data audit: **2026-04-17**.
Ambito: tutte le pagine HTML in `dashboards/`.

## Executive summary

Le dashboard sono oggi principalmente una **demo statica**: la quasi totalità di metriche, tabelle, log, badge e serie chart è hardcoded in HTML/JS locale. Questo crea:

1. **Rischio decisionale** (numeri incoerenti tra pagine).
2. **Bassa affidabilità UX** (utenti vedono dati non allineati al backend).
3. **Debito tecnico** (duplicazioni massive di layout e logica sidebar/topbar).

Priorità immediata: introdurre un **data contract unico** (API + schema) e migrare progressivamente le viste a rendering dinamico.

---

## 1) Findings trasversali (bug, inconsistenze, hardcoded)

### 1.1 Hardcoded diffusi (bloccante)

- Badge navigazione fissi (`Research 6`, `Strategies 4`, `Agents 2`) ripetuti in quasi tutte le pagine.
- Metriche portfolio hardcoded (equity, DD, Sharpe, P&L, exposure).
- Tabelle posizioni/trade log statiche.
- Array chart locali con dati deterministici o casuali (`Math.random`) anziché feed reale.
- Messaggi chat predefiniti con numeri statici.

**Impatto:** dashboard scollegate dal backend reale.

### 1.2 Inconsistenze numeriche tra pagine (alta)

- **Capitale/equity incoerente**: pagine con base 41k vs altre con 10k.
- **Soglia Max Drawdown incoerente**: 5%, 10%, 15% in contesti che sembrano riferirsi allo stesso perimetro.
- **Rischio/allocazioni non allineate** tra overview, risk, strategy e chat.

**Impatto:** perdita di fiducia utente e rischio di interpretazioni errate.

### 1.3 Inconsistenze temporali e semantiche (media)

- Date e testi “today/oggi/now” hardcoded.
- In chat compare: “Prossimo ciclo ricerca arXiv: giovedì 17 aprile 08:00” ma il 17 aprile 2026 è venerdì.
- Copy misto IT/EN non governato (es. label inglesi in pagine italiane).

### 1.4 Architettura frontend fragile (media)

- Ogni pagina replica sidebar/topbar/status e pezzi CSS: alto rischio drift.
- Uso esteso di `onclick` inline.
- Assenza di livello shared per formattazione numeri/date/percentuali.

### 1.5 Sicurezza/manutenibilità (media)

- Presente qualche attenzione XSS in alcune pagine, ma non uniforme.
- Presenza di punti con `innerHTML` per rendering dinamico (non immediatamente vulnerabile coi dati attuali, ma pericoloso se i dati diventano esterni senza sanificazione).

---

## 2) Audit per pagina

## `dashboards/index.html` (Overview)
- Hardcoded estesi su ticker, alert, allocazioni, table strategy e KPI.
- Incoerenza potenziale: “Max DD soglia 5%” nell’alert vs “limit: 10%” nella sezione KPI portfolio.
- Nessun fetch backend: i numeri non possono riflettere stato reale.

## `dashboards/dashboard_live.html`
- P&L/mark price simulati con `Math.random`.
- Log eventi e stato feed non collegati a websocket/stream reale.
- Possibile percezione falsa di live trading.

## `dashboards/dashboard_performance.html`
- Trade log statico con date e righe fisse.
- Metriche modello statiche; nessuna sincronizzazione con backtest o monitor reali.
- Tabs/periodi chart pilotano dati locali.

## `dashboards/dashboard_backtest.html`
- Risultati walk-forward e Monte Carlo precomputati staticamente.
- Uso di `innerHTML` per costruire celle walk-forward (da rifattorizzare con DOM API sicure se i dati diventano esterni).

## `dashboards/dashboard_risk.html`
- Limiti, usage e gauge statici.
- Rischio non derivato da engine risk backend.
- Coerenza numerica non garantita con altre pagine.

## `dashboards/dashboard_research.html`
- Dataset PAPERS hardcoded (metadati, metriche, stato).
- Azione “Run Research” simulata localmente.

## `dashboards/dashboard_agents.html`
- Stato agenti hardcoded nell’oggetto `AGENTS`.
- Azioni run/stop senza risultato effettivo lato backend (comportamento simulato).

## `dashboards/dashboard_with_chat.html`
- Risposte predefinite statiche (performance, risk, papers, agents).
- Dati in chat divergono facilmente dal resto della UI.
- Incongruenza temporale nel testo “giovedì 17 aprile”.

## `dashboards/dashboard_documentation.html`
- Contenuti documentali statici con valori/metadati non versionati dinamicamente.
- Nessun binding con file reali in `models/validated` o `specs`.

## `dashboards/strategy.html`
- Config e metriche per strategia hardcoded in JS/DOM.
- Risk parameters non centralizzati (possibile mismatch con risk dashboard).

---

## 3) Piano di risoluzione (roadmap operativa)

## Fase 0 — Baseline & contratti dati (1-2 giorni)

1. Definire **schema JSON unico** per:
   - portfolio snapshot,
   - strategy snapshot,
   - risk snapshot,
   - agent status,
   - research papers,
   - trades/open positions.
2. Versionare schema (`v1`) e aggiungere validazione lato backend.
3. Definire owner per ogni metrica (source-of-truth).

**Deliverable:** `docs/dashboard_data_contract_v1.md` + esempi payload.

## Fase 1 — Dynamicizzazione KPI globali (2-3 giorni)

1. Estrarre sidebar/topbar in componente shared (template o JS include).
2. Sostituire badge e KPI globali con fetch da endpoint unico `/api/dashboard/summary`.
3. Centralizzare helper:
   - `formatCurrency`,
   - `formatPercent`,
   - `formatDateTime`,
   - color mapping by threshold.

**Acceptance criteria:** nessun numero hardcoded nei widget top-level.

## Fase 2 — Live/Performance/Risk (3-5 giorni)

1. `dashboard_live.html`
   - rimuovere `Math.random`,
   - introdurre polling/websocket per prezzi e P&L.
2. `dashboard_performance.html`
   - trade log e metriche da API (`/api/trades`, `/api/performance`).
3. `dashboard_risk.html`
   - gauge e limiti da `/api/risk/current`.

**Acceptance criteria:** coerenza numerica cross-page entro tolleranza (es. P&L totale identico su overview/performance/live).

## Fase 3 — Research/Agents/Chat/Strategy (3-5 giorni)

1. `dashboard_research.html` collegata a datastore research reale.
2. `dashboard_agents.html` collegata a stato/queue agenti reali.
3. `dashboard_with_chat.html`
   - prompt + retrieval su endpoint reali,
   - eliminazione risposte statiche embeddate.
4. `strategy.html` con selezione strategy da `/api/strategies` e dettaglio dinamico.

**Acceptance criteria:** nessun testo numerico statico in JS business-critical.

## Fase 4 — Hardening & qualità (2-3 giorni)

1. Rimozione `onclick` inline → event listeners centralizzati.
2. Sanitizzazione output (no `innerHTML` per dati esterni).
3. Test automatici:
   - smoke UI,
   - contract tests API,
   - cross-page consistency tests.
4. Introduzione monitor “data freshness” (timestamp reale ultimo update per ogni widget).

---

## 4) Backlog tecnico prioritizzato

### P0 (subito)
- Creare endpoint aggregato summary e sostituire badge/KPI statici.
- Allineare definizioni rischio globali (es. max DD portfolio vs strategy).
- Eliminare contenuti temporali hardcoded (“oggi/now/giovedì 17 aprile”).

### P1
- Migrare live monitor a feed reale.
- Migrare performance + risk a source-of-truth backend.
- Introdurre shared layout component.

### P2
- Migrare chat a retrieval dinamico.
- Migliorare i18n (solo IT o EN coerente con preferenze utente).
- Migliorare accessibilità e gestione errori API.

---

## 5) KPI di successo del refactor

- **Hardcoded critical metrics:** da >90% a <5%.
- **Cross-page metric mismatch:** 0 mismatch sulle metriche core (equity, daily pnl, max DD, active strategies).
- **Data freshness:** >95% widget con timestamp update < 60s (quando feed disponibile).
- **MTTR frontend inconsistency bug:** riduzione >50%.

---

## 6) Rischi di implementazione e mitigazioni

- **Rischio:** API non pronte o incomplete.
  - **Mitigazione:** adapter layer frontend + fallback null-state espliciti.
- **Rischio:** regressioni visive durante modularizzazione layout.
  - **Mitigazione:** visual snapshot test delle dashboard principali.
- **Rischio:** dati parziali provocano NaN/empty widget.
  - **Mitigazione:** formatter robusti e placeholder standard (`—`, `N/A`).

---

## 7) Proposta concreta di prossimi step (settimana 1)

1. Giorno 1: definizione schema e endpoint summary.
2. Giorno 2: migrazione `index.html` + sidebar badge dinamici.
3. Giorno 3: migrazione `dashboard_performance.html` e `dashboard_risk.html` KPI.
4. Giorno 4: migrazione `dashboard_live.html` da simulazione a feed.
5. Giorno 5: test coerenza cross-page + fix finali.

