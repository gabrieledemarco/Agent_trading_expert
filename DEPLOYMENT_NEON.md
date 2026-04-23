# Deploy ufficiale — Render + Neon PostgreSQL

## Baseline

- Runtime: **Render Web Service**
- Database: **Neon PostgreSQL**
- Source of truth: **GitHub**

## Prerequisiti

1. Repository collegato a Render
2. Database Neon attivo
3. `DATABASE_URL` valida con `sslmode=require`

## Configurazione ambiente Render

Variabili minime:

- `DATABASE_URL=postgresql://...`
- `PYTHONUNBUFFERED=1`
- `LOG_LEVEL=INFO`

Start command:

```bash
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

Alternativa deploy-as-code:

- usare `render.yaml` in root repository.

## Migrazione architettura V2 (opzionale ma raccomandata)

Per introdurre schema `strategies/models_v2/backtest_reports/validations_v2` + trigger `pg_notify`:

```bash
psql "$DATABASE_URL" -f migrations/V2__architecture.sql
```

Dettagli:

- `docs/ARCHITECTURE_V2.md`
- `docs/MIGRATION_GUIDE_V1_V2.md`

## Smoke test post-deploy

```bash
curl https://<render-service>/health
curl https://<render-service>/dashboard/summary
curl https://<render-service>/strategies
```

## Nota

Il servizio usa `DataStorageManager` PostgreSQL-only: se `DATABASE_URL` manca o non è `postgresql://`/`postgres://`, l'avvio fallisce esplicitamente.
