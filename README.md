# Agent Trading Expert

Piattaforma multi-agent per ricerca quantitativa, generazione specifiche, validazione e paper trading.

## Stack ufficiale (attuale)

- **Versionamento**: GitHub
- **Deploy**: Render Web Service
- **Database**: Neon PostgreSQL (`DATABASE_URL` obbligatoria)
- **Backend API**: FastAPI

## Agenti presenti

1. **ResearchAgent** (`agents/research/`) — ricerca e sintesi paper arXiv
2. **SpecAgent** (`agents/spec/`) — converte i risultati ricerca in specifiche YAML
3. **MLEngineerAgent** (`agents/ml_engineer/`) — genera codice modello e pipeline feature
4. **ValidationAgent** (`agents/validation/`) — quality check, robustezza, profilo rischio/rendimento
5. **TradingExecutorAgent** (`agents/trading/`) — selezione strategia, segnali, paper trading
6. **MonitoringAgent** (`agents/monitoring/`) — monitoraggio KPI e alert
7. **ChatAgent** (`agents/chat/`) — interfaccia conversazionale informativa
8. **StrategyAgent / ImprovementAgent** (`agents/strategy/`, `agents/improvement/`) — supporto pipeline orchestrata

## Mappa endpoint + workflow

Per la mappatura completa e aggiornata:

- `docs/ARCHITECTURE_MAP.md`

Il documento contiene:

- endpoint HTTP (`api/main.py`, `api/chat_api.py`, `execution_engine/app.py`)
- flusso operativo tra agenti
- ingressi/uscite per ogni componente
- dipendenze dati e storage

## Avvio locale

```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql://<user>:<password>@<host>/<db>?sslmode=require"
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Deploy Render + Neon

Vedi:

- `DEPLOYMENT_NEON.md`
- `data/storage/MIGRATION_GUIDE.md`

## Test

```bash
pytest tests/ -v
```

## Nota operativa

`DataStorageManager` è configurato in modalità **PostgreSQL-only**: senza `DATABASE_URL` valida l'applicazione fallisce in avvio.
