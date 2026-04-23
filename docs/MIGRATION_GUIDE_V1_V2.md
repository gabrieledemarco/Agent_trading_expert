# Migration Guide — V1 → V2

## Scopo

Questa guida descrive l'upgrade documentale/architetturale verso V2 (event-driven, Neon DB, deploy Render).

## Breaking changes (target architecture)

- `docs/ARCHITECTURE_MAP.md` → `docs/ARCHITECTURE_V2.md`
- separazione esplicita tra:
  - **Model validation (MLEngineer)**
  - **Strategy validation L1-L5 (ValidationAgent)**
- introduzione schema SQL V2 in `migrations/V2__architecture.sql`
- introduzione `render.yaml` come baseline deploy-as-code

## Procedura consigliata

1. **Backup DB Neon**
   ```bash
   pg_dump "$DATABASE_URL" > backup_v1.sql
   ```
2. **Crea branch Neon dedicato** (staging/dev).
3. **Applica migrazione V2**
   ```bash
   psql "$DATABASE_URL" -f migrations/V2__architecture.sql
   ```
4. **Verifica schema** (tabelle/triggers/event channel).
5. **Aggiorna Render env vars** (vedi `.env.example` e `DEPLOYMENT_NEON.md`).
6. **Deploy su ambiente staging**.
7. **Smoke test** API (`/health`, `/dashboard/summary`, `/strategies`).

## Verifiche SQL rapide

```sql
SELECT to_regclass('public.strategies');
SELECT to_regclass('public.models_v2');
SELECT to_regclass('public.backtest_reports');
SELECT to_regclass('public.validations_v2');
```

```sql
SELECT tgname, tgrelid::regclass
FROM pg_trigger
WHERE tgname IN (
  'trg_spec_created',
  'trg_model_state_changed',
  'trg_backtest_completed',
  'trg_validation_result'
);
```

## Rollback

1. Rollback applicativo: redeploy del commit precedente su Render.
2. Rollback DB: restore da backup (`backup_v1.sql`) o reset branch Neon.

## Nota

La V2 documenta lo **stato target**: alcune componenti applicative possono essere ancora in transizione nel codice runtime.
