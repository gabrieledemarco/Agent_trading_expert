# Analisi Live Monitor + piano di evoluzione osservabilità

Data: **2026-04-17**  
Scope: `dashboards/dashboard_live.html`

## 1) Cosa espone oggi la pagina Live Monitor

## 1.1 KPI top-level visibili

La pagina espone i seguenti indicatori sintetici:

- `Equity`
- `Daily P&L`
- `Positions`
- `Unrealized`
- `Realized`
- `Win Rate (live)`

## 1.2 Contenuti principali

1. **Active Alerts**: lista di alert testuali.
2. **Equity chart (simulated live)**: serie temporale equity aggiornata periodicamente.
3. **Open Positions table** con 3 simboli (AAPL, MSFT, GOOG) e colonne:
   - side,
   - quantity,
   - entry,
   - mark,
   - unrealized P&L,
   - hold time.
4. **System log (live)**: console con eventi applicativi.

## 1.3 Come vengono generati i dati oggi

- Dati **hardcoded/simulati** in JS locale (non feed realtime backend).
- Aggiornamento ogni `2s` tramite `setInterval`.
- Mark price e equity sono random walk (`Math.random`).
- Log eventi provenienti da array statico `logMessages`.
- Alcuni valori (es. `Positions`, `Realized`, `Win Rate`) restano statici.

Conclusione: la pagina è utile come mock UX, ma non è ancora un monitor operativo affidabile.

---

## 2) Gap principali di monitoring

1. **Assenza di source-of-truth**: nessuna integrazione diretta con stato reale di strategie/ordini.
2. **No per-strategy drill-down**: non si vede “cosa sta facendo ora” ogni strategia.
3. **No execution telemetry**: mancano metriche su latenza ordini, reject ratio, fill ratio, slippage.
4. **No risk telemetry realtime**: manca VaR live per strategia, exposure by symbol/sector, margin usage.
5. **No data quality telemetry**: assenti lag feed, missing bars, heartbeat exchange, stale quotes.
6. **No run context**: non esistono run_id, model_version, deployment hash, modalità trading per strategia.

---

## 3) Dati da aggiungere (priorità)

## 3.1 Portfolio-level (P0)

- `equity`, `cash`, `buying_power`, `gross_exposure`, `net_exposure`
- `realized_pnl_day`, `unrealized_pnl`, `pnl_mtd`, `max_drawdown_live`
- `win_rate_live`, `profit_factor_live`
- `positions_open_count`, `orders_pending_count`

## 3.2 Execution-level (P0)

- `orders_submitted`, `orders_filled`, `orders_rejected`
- `avg_fill_latency_ms`, `p95_fill_latency_ms`
- `avg_slippage_bps`, `fees_today_usd`
- `cancel_replace_rate`

## 3.3 Risk-level (P0)

- `var_95_1d`, `es_95_1d`
- `drawdown_current`, `drawdown_limit`, `drawdown_utilization_pct`
- `concentration_top1/top3`, `leverage`, `beta_portfolio`
- `risk_breach_count_24h`

## 3.4 Feed/System health (P1)

- `feed_latency_ms`, `quote_staleness_ms`
- `bars_missing_count_1h`
- `agent_heartbeat_age_sec` (per agente)
- `queue_depth` per pipeline (signals/orders/risk checks)

## 3.5 Strategy-level (P0-P1)

Per ogni strategia attiva:

- `strategy_name`, `strategy_id`, `model_version`, `status`
- `capital_allocated`, `exposure_gross/net`
- `signals_generated_1h`, `signals_executed_1h`
- `hit_rate_live`, `pnl_day`, `pnl_mtd`, `max_dd_live`
- `open_positions`, `pending_orders`
- `last_signal_ts`, `last_order_ts`, `last_fill_ts`
- `next_action` (es. “WAIT BAR CLOSE”, “RISK CHECK”, “SEND ORDER”)
- `last_error` / `degraded_reason`

---

## 4) Come aggiungere dettaglio operativo sulle singole strategie

## 4.1 Nuova sezione UI: “Strategy Activity Monitor”

Aggiungere una tabella/card dedicata con righe per strategia e colonne:

- Stato (`RUNNING`, `DEGRADED`, `PAUSED`, `STOPPED`)
- Fase corrente (`SCAN`, `SIGNAL`, `RISK_CHECK`, `ORDERING`, `RECONCILIATION`)
- Ultimo evento (`event_type`, timestamp)
- Durata fase corrente (secondi)
- P&L live e DD live
- Open positions / pending orders
- Health score (0-100)

### Drill-down per riga

Click sulla strategia apre pannello con:

- timeline ultimi eventi (max 100),
- ultimi ordini (status transitions),
- ultimi segnali con confidence,
- breach risk e auto-azioni applicate (throttle, stop, reduce size).

## 4.2 Event model minimo (consigliato)

Introdurre un envelope eventi uniforme:

```json
{
  "ts": "2026-04-17T12:34:56Z",
  "strategy_id": "intraday_momentum_v3",
  "event_type": "ORDER_FILLED",
  "severity": "INFO",
  "stage": "ORDERING",
  "correlation_id": "run-20260417-xyz",
  "payload": { "symbol": "AAPL", "qty": 10, "slippage_bps": 3.2 }
}
```

## 4.3 Endpoint da introdurre

1. `GET /api/live/portfolio`
2. `GET /api/live/positions`
3. `GET /api/live/alerts`
4. `GET /api/live/strategies`
5. `GET /api/live/strategies/{strategy_id}/events?limit=100`
6. `GET /api/live/system-health`
7. (opzionale realtime) `WS /api/live/stream`

> Nota: usare prefisso `/api/live/*` evita collisioni con route statiche `/dashboard/*`.

---

## 5) Piano implementativo da validare

## Fase 0 — Contratto dati + naming (1 giorno)

- Definire schema JSON v1 per portfolio, strategy snapshot, strategy events.
- Definire stato strategia e macchina a stati standard (`RUNNING/DEGRADED/PAUSED/...`).
- Definire SLO monitoraggio (es. freschezza dati < 5s).

**Deliverable:** `docs/live_monitor_data_contract_v1.md`.

## Fase 1 — Backend read-model (2-3 giorni)

- Creare layer aggregazione `LiveMonitoringService` (read-only).
- Esportare endpoint REST `GET /api/live/*`.
- Collegare data source reali: trading executor, risk manager, order state, feed health.

**Acceptance:** endpoint rispondono con dati reali (no random) e timestamp aggiornati.

## Fase 2 — Frontend wiring Live Monitor (2 giorni)

- Sostituire simulazione JS (`Math.random`, `logMessages`) con fetch/polling.
- Render KPI e tabella posizioni da API.
- Inserire Strategy Activity Monitor con stato/fase/evento ultimo.

**Acceptance:** dashboard riflette lo stato runtime entro refresh target.

## Fase 3 — Realtime e drill-down (2-3 giorni)

- Aggiungere websocket per eventi strategia/order.
- Timeline eventi per strategia + filtri severity/event_type.
- Evidenziare anomalie (latency spike, reject burst, stale feed).

**Acceptance:** ogni strategia ha tracciamento evento-per-evento e contesto operativo.

## Fase 4 — Hardening e qualità (1-2 giorni)

- Contract test API + smoke UI.
- Alerting su metriche chiave (reject ratio, feed lag, DD breach).
- Fallback UI quando feed degradato.

**Acceptance:** dashboard “fail-soft” e allarmi consistenti.

---

## 6) KPI di successo del miglioramento

- 0 metriche critiche simulate in pagina live.
- Freshness p95 snapshot live < 5s.
- Copertura strategy-level: 100% strategie attive con stato/fase/ultimo evento.
- Riduzione MTTR incidenti runtime > 40% (grazie a telemetry + timeline).

---

## 7) Decisioni da validare con te

1. Refresh target: polling 2s o websocket 1s event-driven?
2. Quali metriche execution sono obbligatorie in P0 (latency/slippage/reject)?
3. Quale livello di dettaglio per timeline eventi (50, 100, 500)?
4. Vuoi vista unica multi-strategy o pagina dettaglio dedicata per strategia?
