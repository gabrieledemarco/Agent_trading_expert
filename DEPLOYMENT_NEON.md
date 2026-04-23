# Deploy ufficiale — Render + Neon PostgreSQL

## Architettura

- **Render Web Service**: ospita API FastAPI e dashboard statiche
- **Neon PostgreSQL**: storage persistente
- **GitHub**: source of truth del codice

## Prerequisiti

1. Repository connesso a Render
2. Database Neon creato
3. Connection string Neon con `sslmode=require`

## Variabili ambiente minime

In Render (Environment):

- `DATABASE_URL=postgresql://...`
- `PYTHONUNBUFFERED=1`
- `LOG_LEVEL=INFO`

## Start command consigliato

```bash
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

## Smoke test post-deploy

```bash
curl https://<your-render-service>/health
curl https://<your-render-service>/dashboard/summary
curl https://<your-render-service>/strategies
```

## Endpoint disponibili dopo deploy

### API principale (`api/main.py`)

- `GET /`
- `GET /health`
- `POST /research`
- `GET /models`
- `POST /trade/execute`
- `GET /performance`
- `GET /dashboard/summary`
- `GET /dashboard/agent-activity`
- `GET /dashboard/strategy/{strategy_name}`
- `GET /strategies`

### API chat (`api/chat_api.py`)

- `GET /api/chat/data`
- `POST /api/chat/message`

### Execution Engine (`execution_engine/app.py`)

- `GET /health`
- `POST /execute`
- `GET /strategies`
- `GET /dashboard/summary`

## Note operative

- Il sistema è configurato per **paper trading**.
- Se `DATABASE_URL` manca o è invalida, `DataStorageManager` interrompe l'avvio con errore esplicito.
