# PRD — Agent Trading Expert (Current Baseline)

## 1. Obiettivo

Costruire una piattaforma multi-agent per:

1. ricerca paper quant/ML
2. trasformazione in specifiche implementabili
3. validazione tecnica/statistica
4. paper trading monitorato

## 2. Architettura target attuale

- **Versionamento**: GitHub
- **Runtime**: Render Web Service
- **Database**: Neon PostgreSQL
- **API**: FastAPI
- **Computation layer**: `execution_engine/`

## 3. Agenti e responsabilità

| Agente | Responsabilità |
|---|---|
| ResearchAgent | Scansione arXiv e creazione summary markdown |
| SpecAgent | Generazione specifiche YAML e action plan |
| MLEngineerAgent | Generazione codice modello e feature pipeline |
| ValidationAgent | Verifica qualità, coerenza e robustezza |
| TradingExecutorAgent | Selezione strategia e paper trading |
| MonitoringAgent | Alerting e reporting KPI |
| ChatAgent | Q&A operativo su modelli e risultati |
| StrategyAgent / ImprovementAgent | Supporto orchestrazione e iterazione migliorativa |

## 4. Flusso di lavoro (as-is)

```text
Research -> Spec -> ML Engineer -> Validation -> Trading -> Monitoring
```

Layer API:

- `api/main.py` (operativo + dashboard)
- `api/chat_api.py` (chat/dashboard data)
- `execution_engine/app.py` (health, execute, strategie, summary)

## 5. Vincoli principali

- `DATABASE_URL` obbligatoria e compatibile PostgreSQL (`postgres://` o `postgresql://`)
- modalità di default: paper trading
- niente credenziali hardcoded nei file

## 6. Deliverable documentali

- `docs/ARCHITECTURE_MAP.md` → endpoint map + workflow agenti
- `DEPLOYMENT_NEON.md` → runbook deploy Render + Neon
- `data/storage/MIGRATION_GUIDE.md` → migrazione dati verso Neon

## 7. Non-obiettivi

- gestione real-money trading
- orchestrazione distribuita completa con queue obbligatoria
- multi-tenant authentication avanzata
