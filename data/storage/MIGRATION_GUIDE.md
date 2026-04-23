# Migration Guide — da SQLite locale a Neon PostgreSQL

Questo progetto usa in produzione **Neon PostgreSQL**.

Se hai dati storici in SQLite, usa questo runbook per migrare.

## 1) Prerequisiti

- Python environment con dipendenze installate
- Connection string Neon valida
- Script `data/storage/migrate_to_postgres.py` presente nel repo

## 2) Esecuzione migrazione

```bash
python data/storage/migrate_to_postgres.py \
  "postgresql://user:password@host/database?sslmode=require" \
  data/storage/trading_agents.db
```

Parametro 1: URL PostgreSQL target (Neon)  
Parametro 2: path SQLite sorgente (opzionale, default `data/storage/trading_agents.db`)

## 3) Verifiche

Esegui query nel database Neon:

```sql
SELECT COUNT(*) FROM research;
SELECT COUNT(*) FROM specs;
SELECT COUNT(*) FROM models;
SELECT COUNT(*) FROM validation;
SELECT COUNT(*) FROM trades;
SELECT COUNT(*) FROM performance;
SELECT COUNT(*) FROM agent_logs;
```

## 4) Switch applicativo

Dopo la migrazione, configura in Render:

- `DATABASE_URL=postgresql://...`

Riavvia il servizio.

## 5) Troubleshooting

### DATABASE_URL non valida
Assicurati che inizi con `postgresql://` (o `postgres://`) e includa `sslmode=require`.

### Errori duplicati
Lo script usa strategie di inserimento safe (`ON CONFLICT`) quando applicabile.

### Connessione rifiutata
Controlla credenziali, hostname Neon, DB name e eventuali policy di rete.
