# Agent Trading Expert

![Architecture](https://img.shields.io/badge/Architecture-V2-blue)
![Stack](https://img.shields.io/badge/Stack-FastAPI%20%7C%20Neon%20%7C%20Render-green)

Piattaforma multi-agent per ricerca quantitativa, validazione strategica e paper trading.

## Stack ufficiale

- **Versionamento**: GitHub
- **Deploy**: Render Web Service
- **Database**: Neon PostgreSQL (`DATABASE_URL` obbligatoria)
- **Backend/API**: FastAPI

## Documentazione principale

- Architettura target: `docs/ARCHITECTURE_V2.md`
- Deploy baseline: `DEPLOYMENT_NEON.md`
- Migrazione dati legacy: `data/storage/MIGRATION_GUIDE.md`
- Migrazione architetturale V1→V2: `docs/MIGRATION_GUIDE_V1_V2.md`

## Accuratezza vs Validazione (principio)

- **MLEngineer**: valuta l'accuratezza ML del modello (MSE/MAE/R²/directional accuracy) durante training.
- **ValidationAgent**: valida la strategia completa (performance netta, risk, robustness L1-L5) dopo backtest.

Questa separazione evita di confondere qualità predittiva del modello con qualità operativa della strategia.

## Avvio locale

```bash
pip install -r requirements.txt
cp .env.example .env
# imposta DATABASE_URL con connessione Neon valida
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Test

```bash
pytest tests/ -v
```

## Nota operativa

`DataStorageManager` è in modalità **PostgreSQL-only**: senza `DATABASE_URL` valida l'applicazione fallisce in avvio.
