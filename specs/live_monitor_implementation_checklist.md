# Checklist implementazione Live Monitor (dati reali, no random)

Data: **2026-04-17**  
Stato decisione: ✅ approvato piano live monitor / ❌ non approvato fix 404

## Obiettivo vincolante

- [ ] La pagina `dashboard_live.html` non deve usare dati casuali (`Math.random`) o dataset hardcoded per KPI/posizioni/log.
- [ ] Tutti i widget core devono leggere dati reali delle strategie tramite API backend.

---

## Fase 1 — Backend readiness (P0)

### Endpoint monitor live
- [ ] Esporre endpoint aggregato `GET /live/monitor` con payload unico.
- [ ] Includere sezioni: `portfolio`, `alerts`, `equity_history`, `open_positions`, `strategy_activity`, `system_logs`, `feed_status`.
- [ ] Garantire `timestamp` nel payload per data freshness.

### Source of truth
- [ ] Leggere strategie da `models/validated/*_validation.json`.
- [ ] Leggere trade/log/performance dal `DataStorageManager` (SQLite).
- [ ] Calcolare `open_positions` da trade eseguiti (BUY/LONG vs SELL/SHORT).

### Criteri minimi
- [ ] Nessun fallback a `Math.random` lato backend.
- [ ] Se mancano dati reali, rispondere con array vuoti e valori null-safe, non sintetici casuali.

---

## Fase 2 — Frontend wiring (P0)

### KPI e stato generale
- [ ] Sostituire aggiornamento simulato con `fetch('/live/monitor')`.
- [ ] Aggiornare KPI (`equity`, `daily_pnl`, `positions_count`, `unrealized`, `realized`, `win_rate_live`) da API.
- [ ] Aggiornare `feedStatus`, `lastUpdate`, `tickCount` senza calcoli random.

### Equity chart
- [ ] Popolare il grafico esclusivamente da `equity_history` backend.
- [ ] Rimuovere qualsiasi random walk locale.

### Open positions
- [ ] Rendere tabella da `open_positions` API.
- [ ] Gestire stato empty con messaggio esplicito “Nessuna posizione aperta”.

### Strategy Activity Monitor
- [ ] Aggiungere sezione/tabella dedicata per strategia.
- [ ] Colonne minime: strategy, status, stage, sharpe, max DD, trades, last activity.
- [ ] Color coding su stato/rischio (es. sharpe < 0 rosso, DD > soglia rosso).

### System logs
- [ ] Popolare log console da `system_logs` API.
- [ ] Mostrare `agent_name`, `timestamp`, `message`, `status`.

---

## Fase 3 — Qualità e hardening (P1)

### Error handling
- [ ] Gestire errori API con alert visibile in pagina.
- [ ] Evitare crash UI se payload parziale/mancante.

### Performance/Freshness
- [ ] Refresh polling target: 5s (configurabile).
- [ ] Limitare history chart a max 60 punti.

### Sicurezza/igiene
- [ ] Non usare `innerHTML` con dati non trusted senza sanitizzazione.
- [ ] Mantenere CSP coerente.

---

## Fase 4 — Test checklist (Go/No-Go)

### Test manuali
- [ ] Avvio server: `uvicorn api.main:app --host 127.0.0.1 --port 8000`
- [ ] `GET /live/monitor` risponde 200 e JSON valido.
- [ ] Apertura `dashboard_live.html`: KPI aggiornati da API.
- [ ] Nessun movimento dati se DB non cambia (assenza random drift).
- [ ] Strategy table popolata da strategie validate.

### Test automatici (da aggiungere)
- [ ] Unit test endpoint `/live/monitor` con payload shape.
- [ ] Test integrazione: coerenza `positions_count == len(open_positions)`.
- [ ] Test regressione: assenza pattern `Math.random` in `dashboard_live.html`.

---

## Definition of Done

- [ ] `dashboard_live.html` usa solo dati backend per i blocchi core.
- [ ] Nessuna metrica live dipende da generatori casuali lato client.
- [ ] Esiste tabella “Strategy Activity Monitor” con stato operativo per singola strategia.
- [ ] I test minimi passano e la pagina resta stabile con payload vuoto/parziale.
