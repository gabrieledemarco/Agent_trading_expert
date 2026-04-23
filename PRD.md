# PRD — Agent Trading Expert (V2 target)

## Obiettivo

Costruire una pipeline event-driven di trading research che separi chiaramente:

1. **Model validation (MLEngineer)**: accuratezza predittiva ML
2. **Strategy validation (ValidationAgent)**: performance/risk/robustness della strategia completa

## Stack approvato

- GitHub (versionamento)
- Render (deploy)
- Neon PostgreSQL (persistenza)
- FastAPI (API)
- PostgreSQL LISTEN/NOTIFY (event bus)

## Regola architetturale fondamentale

| Livello | Owner | Domanda |
|---|---|---|
| Model Validation | MLEngineer | Il modello è predittivamente utile? |
| Strategy Validation | ValidationAgent | La strategia è profittevole, gestibile e robusta? |

## Flusso V2

```text
ResearchEngine -> MLEngineer -> StrategyEngineer -> ValidationAgent -> ExecutionEngine
                                      ^                  |
                                      |------retry/feedback loop-----|
```

## Stati strategia (target)

`draft -> backtest_pending -> backtest_running -> validation_pending -> approved/rejected/warning -> deployed/human_review/archived`

## Documentazione di riferimento

- Architettura: `docs/ARCHITECTURE_V2.md`
- Deploy: `DEPLOYMENT_NEON.md`
- Migrazione V1→V2: `docs/MIGRATION_GUIDE_V1_V2.md`
- Schema DB/trigger: `migrations/V2__architecture.sql`
