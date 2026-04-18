# PostgreSQL Migration Guide

## Supporto dual-backend

`DataStorageManager` ora supporta sia **SQLite** (default) che **PostgreSQL**.

### Rilevamento automatico

Il backend viene rilevato automaticamente dalla connection string:
- **SQLite**: se non impostata `DATABASE_URL` o non inizia con `postgresql://`
- **PostgreSQL**: se `DATABASE_URL` inizia con `postgresql://`

## Step 1: Usa PostgreSQL nelle applicazioni

### Opzione A: Variabile d'ambiente (consigliato)

```bash
export DATABASE_URL="postgresql://user:password@host/database?sslmode=require"
python your_app.py
```

### Opzione B: Codice

```python
from data.storage.data_manager import DataStorageManager

db = DataStorageManager(
    db_url="postgresql://user:password@host/database?sslmode=require"
)
```

## Step 2: Migra i dati da SQLite

Quando sei pronto a passare a PostgreSQL, usa lo script di migrazione:

```bash
# Default: legge da data/storage/trading_agents.db
python data/storage/migrate_to_postgres.py "postgresql://user:password@host/database"

# Con path SQLite esplicito
python data/storage/migrate_to_postgres.py \
  "postgresql://user:password@host/database" \
  /path/to/your/sqlite.db
```

### Output della migrazione

Lo script:
1. Legge tutti i dati dalla SQLite locale
2. Li carica in PostgreSQL (con `ON CONFLICT DO NOTHING` per evitare duplicati)
3. Verifica i conteggi per assicurare corrispondenza
4. Riporta il successo/fallimento per ogni tabella

Esempio output:
```
INFO:__main__:Starting migration...
INFO:__main__:Migrating research...
✓ Research migrated
✓ Specs migrated
✓ Models migrated
...
Verifying migration...
✓ research: SQLite=5, PostgreSQL=5
✓ specs: SQLite=8, PostgreSQL=8
...
Migration complete!
```

## Step 3: Cambia l'app in produzione

1. Configura `DATABASE_URL` nel tuo hosting cloud
2. Restart dell'applicazione
3. `DataStorageManager` userà automaticamente PostgreSQL

## Per Neon (PostgreSQL serverless)

1. Crea un account su [https://neon.tech](https://neon.tech)
2. Copia la connection string dal dashboard Neon
3. Imposta come `DATABASE_URL`

Esempio:
```bash
export DATABASE_URL="postgresql://user:password@ep-xxxx.us-east-1.aws.neon.tech/dbname?sslmode=require&channel_binding=require"
```

## Backward compatibility

- Existing code che usa `DataStorageManager()` continuerà a funzionare con SQLite
- Nessun cambio di API o contratti
- Tutte le query funzionano identicamente

## Troubleshooting

### "Connection refused"
- Verifica che il host PostgreSQL sia raggiungibile
- Per Neon: assicurati che l'IP sia whitelisted (se necessario)

### "UNIQUE violation" durante migrazione
- Significa che qualche record esiste già in PostgreSQL
- Lo script usa `ON CONFLICT DO NOTHING`, quindi è safe rieseguire

### "psycopg2 not installed"
```bash
pip install psycopg2-binary
```

### Continua a volere SQLite?
Non serve fare nulla — il default è SQLite se `DATABASE_URL` non è impostata.
