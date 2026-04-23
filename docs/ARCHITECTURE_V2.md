# Agent Trading Expert — Architettura V2

![Architecture](https://img.shields.io/badge/Architecture-V2-blue)
![Stack](https://img.shields.io/badge/Stack-FastAPI%20%7C%20Neon%20%7C%20Render-green)

## Visione

Pipeline event-driven end-to-end: dalla ricerca paper alla strategia validata, fino al deploy paper trading.

## Stack ufficiale

| Componente | Tecnologia | Note |
|---|---|---|
| Versionamento | GitHub | PR obbligatorie su `main` |
| Deploy | Render Web Service | Auto-deploy da repository |
| Database | Neon PostgreSQL | `DATABASE_URL` obbligatoria |
| Event Bus | PostgreSQL LISTEN/NOTIFY | Nessuna infra aggiuntiva necessaria |
| API | FastAPI | OpenAPI auto-generata |
| Backtesting | VectorBT | Rolling/Walk-forward/Monte Carlo |
| Risk & Perf | empyrical + QuantStats | Metriche finanziarie standard |
| Model Metrics | scikit-learn | MSE/MAE/R2/Directional Accuracy |

---

## Accuratezza vs Validazione (ruoli separati)

| Concetto | Definizione | Chi lo fa | Quando |
|---|---|---|---|
| Accuratezza del modello | Qualità predittiva ML puro (MSE, MAE, R², directional accuracy) | MLEngineer | Durante training |
| Validazione della strategia | Qualità sistema completo (segnali, sizing, costi, execution, rischio) | ValidationAgent | Dopo backtest |

### Regola architetturale

- **MLEngineer** rifiuta modelli non predittivi (evita sprechi di pipeline).
- **ValidationAgent** rifiuta strategie non profittevoli/fragili anche se il modello è accurato.

---

## Agenti core (target)

## 1) ResearchEngine
**Input**: query di ricerca  
**Output**: `StrategySpec` (YAML validato)

Flusso:
1. Ricerca arXiv
2. Sintesi e normalizzazione specifiche
3. Validazione schema

Evento: `spec.created`

## 2) MLEngineer
**Input**: `StrategySpec`  
**Output**: `ValidatedModel`

### Model validation minima (ML puro)

| Metrica | Soglia |
|---|---|
| Directional Accuracy | `>= 0.52` |
| R² | `>= 0.05` |
| Train/Test gap | `<= 0.15` |

Eventi:
- `model.validated`
- `model.rejected`

## 3) StrategyEngineer
**Input**: `ValidatedModel` + market data  
**Output**: `StrategyPackage` + backtest report

Backtest richiesti:
- rolling window
- monte carlo
- walk-forward
- regime stress test

Evento: `backtest.completed`

## 4) ValidationAgent (L1-L5)
**Input**: `StrategyPackage`  
**Output**: `ValidationResult` + `FeedbackPayload`

| Livello | Scopo |
|---|---|
| L1 | Sanity tecnica codice |
| L2 | Realismo esecuzione / no lookahead |
| L3 | Performance netta dopo costi |
| L4 | Risk controls (drawdown, VaR/CVaR, ruin) |
| L5 | Robustezza cross-scenario/regime |

Soglie default:

```yaml
default:
  sharpe_ratio: {min: 0.5}
  max_drawdown: {max: 0.20}
  profit_factor: {min: 1.2}
  risk_of_ruin: {max: 0.05}
  monte_carlo_pvalue: {max: 0.05}
```

Branch:
- `APPROVED -> execution.pending`
- `WARNING -> auto-tune + retry`
- `REJECTED -> feedback + retry (max 3)`

## 5) ExecutionEngine
**Input**: strategia APPROVED  
**Output**: ordini paper/live

Modalità:
- paper trading (default)
- live trading (toggle controllato)

Evento: `execution.started`

---

## Servizi stateless (target)

- `MonitorService`: metriche da DB, alerting.
- `ChatInterface`: query utente via API/WebSocket, sola lettura stato.

---

## Diagramma pipeline

```text
ResearchEngine -> MLEngineer -> StrategyEngineer -> ValidationAgent -> ExecutionEngine
                                 |                   |
                                 |                   +-> feedback/retry loop (max 3)
                                 +-> model.rejected
```

---

## Stato strategia (target)

`draft -> backtest_pending -> backtest_running -> validation_pending -> approved/rejected/warning -> deployed/human_review/archived`

---

## Deploy baseline

- Database: Neon PostgreSQL
- Runtime: Render Web Service
- Source: GitHub

Configurazione e runbook:
- `render.yaml`
- `DEPLOYMENT_NEON.md`
- `migrations/V2__architecture.sql`
- `docs/MIGRATION_GUIDE_V1_V2.md`
