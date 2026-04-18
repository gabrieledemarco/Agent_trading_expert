# Piano Operativo — Refactoring Incrementale
> **Ultimo aggiornamento**: 2026-04-18  
> **Branch di lavoro**: `claude/backtest-dashboard-integration-C4up4`  
> **Principio guida**: Strangler Fig — mai rompere un'interfaccia esistente prima che quella nuova sia stabile.

---

## Contesto

Sistema multi-agent per trading quantitativo. Il PDR richiede:
- Integrazione **TradingAgents** (LangGraph) come orchestratore
- **Execution Engine** separato per tutti i calcoli numerici
- Gli agenti: SOLO reasoning/codice/analisi — ZERO calcoli numerici

### Agenti esistenti (da mantenere/refactorare)
| Agente | File | Stato |
|--------|------|-------|
| ResearchAgent | `agents/research/research_agent.py` | ✅ Usabile as-is |
| MLEngineerAgent | `agents/ml_engineer/ml_engineer_agent.py` | ✅ Usabile, genera codice |
| ValidationAgent | `agents/validation/validation_agent.py` | ⚠️ Fa calcoli interni — da refactorare |
| TradingExecutorAgent | `agents/trading/trading_executor.py` | ⚠️ Calcola metriche internamente |
| MonitoringAgent | `agents/monitoring/monitoring_agent.py` | ✅ Quasi as-is |
| ChatAgent | `agents/chat/chat_agent.py` | ✅ Nessuna modifica |

### Agenti da creare (NON esistono)
- **StrategyAgent** — traduce reasoning TradingAgents in codice Python strategia
- **ImprovementAgent** — loop iterativo di ottimizzazione post-validazione

### Componenti nuovi (non agenti)
- **Execution Engine** — servizio FastAPI separato, porta 8001
- **Orchestration Layer** — TradingAgents + LangGraph
- **Redis Queue** — comunicazione asincrona agenti ↔ motore

---

## Mappa Accoppiamenti Critici

```
ValidationAgent ──write──► models/validated/*_validation.json
                                    │ schema v0 (non versionato)
TradingExecutor ──read──────────────┘
        │
        └──write──► trading_logs/metrics_{date}.jsonl
                            │ schema v0 (non versionato)
MonitoringAgent ──read──────┘

Rischio cascata: cambiare un campo rompe tutti e 3 i componenti.

Ulteriori problemi:
- agents.yaml NON letto dagli agenti (usano default hardcoded)
- DataManager: path DB hardcoded "data/storage/trading_agents.db"
- ValidationAgent: calcola Sharpe/MC internamente (viola PDR)
- API: scan directory hardcoded models/versions/, models/validated/
```

---

## Fasi del Piano

### FASE 0 — Test Harness ✅/🔲
> Nessuna modifica funzionale. Solo rete di sicurezza.

- [ ] `tests/fixtures/` — snapshot JSON/JSONL/YAML reali
- [ ] `tests/contracts/test_validation_schema.py` — verifica campi obbligatori
- [ ] `tests/contracts/test_metrics_schema.py` — verifica JSONL metriche
- [ ] `tests/contracts/test_api_contracts.py` — verifica response shapes
- [ ] `tests/contracts/test_db_schema.py` — verifica tabelle SQLite
- [ ] `tests/conftest.py` — fixtures condivise

**Gate**: tutti i test di contratto passano sul codice corrente (baseline verde).

---

### FASE 1 — Config Centralization 🔲
> Rischio BASSO. Zero cambiamenti a logica o schemi.

- [ ] `configs/paths.py` — source of truth per tutti i path
- [ ] `configs/config_loader.py` — singleton per agents.yaml
- [ ] Aggiornare `ValidationAgent.__init__` → usa `Paths.*` (default identici)
- [ ] Aggiornare `TradingExecutor.__init__` → usa `Paths.*`
- [ ] Aggiornare `MonitoringAgent.__init__` → usa `Paths.*`
- [ ] Aggiornare `DataStorageManager.__init__` → usa `Paths.DB_PATH`
- [ ] Aggiornare `api/main.py` → usa `Paths.*`

**Gate**: contratti verdi + comportamento identico.

---

### FASE 2 — Schema Versioning 🔲
> Rischio BASSO. Solo campi addizionali.

- [ ] Aggiungere `"schema_version": "1.0"` a `ValidationAgent` output
- [ ] `data/schemas/validation_v1.json` — JSON Schema formale
- [ ] `data/schemas/metrics_v1.json` — JSON Schema metriche
- [ ] `data/schemas/trade_v1.json` — JSON Schema trade log
- [ ] `data/schemas/execution_request_v1.json` — schema futuro Execution Engine
- [ ] Consumer: aggiungere `_validate_schema()` non bloccante

**Gate**: JSON Schema tests + contratti verdi.

---

### FASE 3 — Pydantic Data Contracts 🔲
> Rischio MEDIO. Tipi forti con fallback.

- [ ] `data/contracts/__init__.py`
- [ ] `data/contracts/validation.py` — `ValidationResult`, `RiskReturnProfile`, `StatisticalRobustness`
- [ ] `data/contracts/performance.py` — `PerformanceRecord`
- [ ] `data/contracts/trade.py` — `TradeRecord`
- [ ] Aggiornare `ValidationAgent` writer → serializza con Pydantic
- [ ] Aggiornare `TradingExecutor` reader → deserializza con Pydantic + fallback
- [ ] Aggiornare `MonitoringAgent` reader → deserializza con Pydantic + fallback

**Gate**: Pydantic validation tests + nessuna regressione API.

---

### FASE 4 — Estrazione Calcolo da ValidationAgent 🔲
> Rischio ALTO. Punto critico del PDR.

- [ ] `execution_engine/computation_service.py` — estrae `analyze_risk_return_profile()` e `evaluate_statistical_robustness()`
- [ ] Test parità numerica: output identico bit-per-bit per tutti e 6 i modelli
- [ ] Refactor `ValidationAgent` → delega a `ComputationService`
- [ ] Refactor `TradingExecutor.calculate_metrics()` → usa `models/backtest.py` direttamente
- [ ] `ComputationService` istanziato con `engine_url=None` → modalità locale

**Gate**: test parità + validation JSON identici ai precedenti + contratti verdi.

---

### FASE 5 — Execution Engine Stub 🔲
> Rischio MEDIO. Nuovo servizio con fallback locale.

**Struttura:**
```
execution_engine/
├── __init__.py
├── api.py              # FastAPI porta 8001
├── sandbox.py          # RestrictedPython wrapper
├── runner.py           # Esegue codice strategia
├── backtest.py         # Importa models/backtest.py
├── metrics.py          # Calcolo metriche
├── queue_worker.py     # Consumer Redis (Fase 6)
└── models.py           # ExecutionRequest, ExecutionResult (Pydantic)
```

- [ ] `execution_engine/models.py` — contratti JSON Engine
- [ ] `execution_engine/api.py` — `GET /health`, `POST /execute`
- [ ] `execution_engine/sandbox.py` — RestrictedPython + whitelist
- [ ] `execution_engine/runner.py` — esecuzione deterministica
- [ ] `execution_engine/backtest.py` — wrapper deterministico
- [ ] `ComputationService` → dual mode: locale o HTTP verso Engine
- [ ] Test dual-mode

**Gate**: `GET /health` verde + ComputationService funziona in entrambe le modalità.

---

### FASE 6 — Queue + TradingAgents + Nuovi Agenti 🔲
> Rischio ALTO. Solo dopo che fasi 0-5 sono stabili.

- [ ] `agents/base/execution_client.py` — interfaccia Redis asincrona
- [ ] `execution_engine/queue_worker.py` — consumer Redis
- [ ] `agents/orchestration/trading_agents_wrapper.py` — wrapper TradingAgentsGraph
- [ ] `agents/strategy/strategy_agent.py` — **NUOVO** agente
- [ ] `agents/improvement/improvement_agent.py` — **NUOVO** agente
- [ ] Feature flag `USE_TRADING_AGENTS=false` default
- [ ] LangGraph workflow completo
- [ ] `reflect_and_remember()` feedback loop

**Gate**: end-to-end test Research→Strategy→Backtest→Validation.

---

## Timeline

| Settimana | Fasi | Gate |
|-----------|------|------|
| 1 | FASE 0 + FASE 1 | Baseline verde + config unificata |
| 2 | FASE 2 + FASE 3 inizio | Schema versioning + Pydantic writer |
| 3 | FASE 3 fine + FASE 4.1 | Pydantic reader + ComputationService creato |
| 4 | FASE 4.2-4.3 + FASE 5.1-5.2 | Parità numerica + Engine stub |
| 5 | FASE 5.3 | Dual-mode + stabilizzazione |
| 6-8 | FASE 6 | TradingAgents + nuovi agenti |

---

## Stack Tecnologico Target

| Layer | Tecnologia |
|-------|-----------|
| Agent orchestration | TradingAgents + LangGraph |
| LLM backend | Anthropic Claude |
| Execution Engine | FastAPI + RestrictedPython |
| Backtest | backtrader (già dep TradingAgents) |
| Queue | Redis Streams |
| Cache dati | Redis |
| DB dev | SQLite (esiste) |
| DB prod | PostgreSQL (futura migrazione) |
| Model registry | MLflow |
| Data contracts | Pydantic v2 |

---

## Matrice Rischi

| Fase | Rischio | Mitigazione |
|------|---------|-------------|
| 0 | Nessuno | — |
| 1 | Basso | Default identici ai valori precedenti |
| 2 | Basso | Consumer ignorano campi sconosciuti |
| 3 | Medio | Fallback al dict parsing se `ValidationError` |
| 4 | Alto | Test parità numerica obbligatori pre-merge |
| 5 | Medio | `engine_url=None` attiva modalità locale |
| 6 | Alto | Feature flag `USE_TRADING_AGENTS=false` default |

---

## Interfaccia Agent ↔ Execution Engine

**Request (agenti → motore):**
```json
{
  "strategy_id": "uuid-v4",
  "strategy_code": "def run(data, params): ...",
  "parameters": {"lookback": 20, "threshold": 0.02},
  "dataset": {"symbols": ["AAPL"], "start": "2021-01-01", "end": "2023-12-31", "frequency": "1d"},
  "backtest_config": {"initial_capital": 10000, "transaction_cost": 0.001, "walk_forward_windows": 12, "seed": 42}
}
```

**Response (motore → agenti):**
```json
{
  "strategy_id": "uuid-v4",
  "status": "success",
  "metrics": {
    "sharpe_ratio": 1.25, "total_return": 0.18, "max_drawdown": 0.07,
    "win_rate": 0.58, "num_trades": 145, "annual_return": 0.15,
    "volatility": 0.12, "sortino_ratio": 1.8, "calmar_ratio": 2.1
  },
  "walk_forward": [{"window": 1, "is_sharpe": 1.1, "oos_sharpe": 0.8}],
  "equity_curve": [["2021-01-04", 10000]],
  "trade_log": [{"date": "", "symbol": "", "action": "", "qty": 0, "price": 0}],
  "error": null
}
```

---

*Piano generato il 2026-04-18. Aggiornare i checkbox man mano che le fasi vengono completate.*
