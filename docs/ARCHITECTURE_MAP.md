# Mappa Architetturale — Endpoint + Workflow Agenti

## 1. Panoramica componenti

- `api/main.py` → API operativa principale + endpoint dashboard
- `api/chat_api.py` → endpoint chat e aggregazione dati sintetici
- `execution_engine/app.py` → layer di calcolo numerico (execution)
- `data/storage/data_manager.py` → persistenza PostgreSQL (Neon) centralizzata
- `agents/*` → logica per ricerca, spec, ML, validazione, trading, monitoring

---

## 2. Endpoint map

## 2.1 API principale (`api/main.py`)

| Metodo | Endpoint | Scopo | Dipendenze principali |
|---|---|---|---|
| GET | `/` | metadata API | FastAPI |
| GET | `/health` | health check | FastAPI |
| POST | `/research` | avvia ricerca arXiv | `ResearchAgent` |
| GET | `/models` | lista modelli in `models/versions` | filesystem |
| POST | `/trade/execute` | esegue trade manuale | `TradingExecutorAgent` |
| GET | `/performance` | summary performance | `TradingExecutorAgent` |
| GET | `/dashboard/summary` | KPI dashboard | `DataStorageManager` |
| GET | `/dashboard/agent-activity` | attività agenti | `DataStorageManager` |
| GET | `/dashboard/strategy/{strategy_name}` | KPI strategia | `DataStorageManager` |
| GET | `/strategies` | stato strategie validate | `models/validated/*_validation.json` |

## 2.2 API chat (`api/chat_api.py`)

| Metodo | Endpoint | Scopo |
|---|---|---|
| GET | `/api/chat/data` | aggregati su modelli/report |
| POST | `/api/chat/message` | risposta rule-based per chat |

## 2.3 Execution Engine (`execution_engine/app.py`)

| Metodo | Endpoint | Scopo |
|---|---|---|
| GET | `/health` | health execution engine |
| POST | `/execute` | esecuzione richiesta strategia (stub deterministico) |
| GET | `/strategies` | lista strategie validate |
| GET | `/dashboard/summary` | summary dashboard via storage manager |

---

## 3. Workflow agenti (as-is)

## 3.1 Pipeline primaria

```text
ResearchAgent
  -> produce markdown in data/research_findings/
SpecAgent
  -> legge markdown, produce YAML in specs/
MLEngineerAgent
  -> legge YAML, genera codice/modelli
ValidationAgent
  -> verifica coerenza + robustezza, produce *_validation.json e *_documentation.md in models/validated/
TradingExecutorAgent
  -> carica strategie APPROVED, genera segnali ed esegue paper trading, scrive trading_logs/
MonitoringAgent
  -> legge trading_logs/ e modelli validati, produce alert/report
```

## 3.2 Workflow API-driven

```text
Client -> api/main.py
       -> endpoint invoca agente specifico
       -> agente legge/scrive storage/files
       -> risposta JSON al client
```

---

## 4. Storage e consistenza dati

- Fonte dati persistente: **Neon PostgreSQL** via `DataStorageManager`.
- Tabelle core: `research`, `specs`, `models`, `validation`, `trades`, `performance`, `agent_logs`.
- Artefatti file-based restano presenti per pipeline agenti:
  - `data/research_findings/*.md`
  - `specs/*.yaml`, `specs/*_action_plan.md`
  - `models/validated/*_validation.json`, `*_documentation.md`
  - `trading_logs/*.jsonl`

---

## 5. Flusso consigliato in produzione (Render + Neon)

1. Trigger ricerca/spec/validazione (manuale o scheduler esterno)
2. Persistenza metriche e attività agenti su Neon
3. Trading in paper mode
4. Monitoring continuo KPI + alert
5. Dashboard/API su Render come punto unico di consultazione

---

## 6. Checklist coerenza documentale

- README allineato allo stack GitHub + Render + Neon
- PRD allineato alla baseline attuale
- Guida deploy unica: `DEPLOYMENT_NEON.md`
- Guida migrazione unica: `data/storage/MIGRATION_GUIDE.md`
