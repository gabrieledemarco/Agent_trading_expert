# RCA: motivo rottura pagina Overview dopo integrazione Live Monitor

Data: **2026-04-17**

## Sintomo

La pagina Overview risultava instabile/intermittente dopo la PR Live Monitor (refresh API multipli dalla dashboard).

## Causa individuata

Il backend creava una nuova istanza di `DataStorageManager()` in più endpoint ad ogni richiesta (`/dashboard/summary`, `/dashboard/agent-activity`, `/dashboard/strategy/{strategy_name}`, `/live/monitor`).

Questo comportamento ri-eseguiva continuamente l'inizializzazione DB (con connessioni SQLite e `PRAGMA journal_mode=WAL`), aumentando contention e latenza quando Overview e Live Monitor facevano polling concorrente.

## Perché impattava Overview

Overview dipende da endpoint dashboard ad alta frequenza. Con più richieste in parallelo, la creazione ripetuta del manager produceva overhead non necessario e poteva degradare i tempi di risposta, facendo percepire la pagina come “spaccata” (widget non aggiornati o aggiornamenti intermittenti).

## Correzione applicata

- Introdotto singleton condiviso con `@lru_cache(maxsize=1)` in `api/main.py`:
  - `get_data_storage_manager()`
- Sostituita la creazione per-request di `DataStorageManager()` negli endpoint dashboard/live con il singleton condiviso.

## Azioni di follow-up

1. Aggiungere test di regressione con polling concorrente su `/dashboard/summary` e `/live/monitor`.
2. Aggiungere metriche di latenza endpoint (p50/p95).
3. Valutare un livello cache read-only per snapshot dashboard.
