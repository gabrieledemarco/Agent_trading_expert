# Deployment con Neon Database

**Architettura**: GitHub Pages + Render API + Neon PostgreSQL
**Database**: Neon PostgreSQL Serverless (Free Tier)

---

## Architettura

```
Utente (Browser)
       |
       v
GitHub Pages (Frontend Statico)
  URL: https://gabrieledemarco.github.io/Agent_trading_expert
       |
       | API Calls (CORS)
       v
Render Web Service (Backend API + Agenti)
  URL: https://agent-trading-expert.onrender.com
       |
       | PostgreSQL Connection (SSL)
       v
Neon PostgreSQL Serverless
  URL: ep-xxx-pooler.us-east-1.aws.neon.tech
```

**Costi**: $0/mese (tutto free tier)

---

## Setup

### 1. Crea Database Neon

1. Vai su https://console.neon.tech
2. Crea progetto: `agent-trading-expert`
3. Region: `us-east-1`, PostgreSQL 16
4. Copia la **Pooled connection string**

Formato:
```
postgresql://[user]:[password]@ep-xxxxx-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
```

### 2. Configura Render

1. Vai su https://dashboard.render.com
2. Seleziona servizio `agent-trading-expert`
3. Environment > Add Environment Variable:
   - **Key**: `DATABASE_URL`
   - **Value**: [connection string Neon]
4. Save Changes (auto-redeploy)

### 3. Verifica

```bash
# Health check (verifica connessione DB)
curl https://agent-trading-expert.onrender.com/health
# Output: {"status":"healthy","database":"postgres"}

# Dashboard summary
curl https://agent-trading-expert.onrender.com/dashboard/summary
```

Nel Neon SQL Editor:
```sql
SELECT COUNT(*) FROM agent_logs;
```

---

## Come Funziona

Il `DataStorageManager` rileva automaticamente il backend:

- Se `DATABASE_URL` e' impostato con prefisso `postgresql://` → usa PostgreSQL (Neon)
- Se `DATABASE_URL` ha prefisso `postgres://` → normalizza automaticamente a `postgresql://`
- Altrimenti → fallback a SQLite locale

Le 7 tabelle (research, specs, models, validation, trades, performance, agent_logs) vengono create automaticamente alla prima connessione.

---

## Rollback

Per tornare a SQLite:
1. Render Dashboard > Environment
2. Rimuovi `DATABASE_URL`
3. Save Changes (auto-redeploy)

---

## Free Tier Neon

- 0.5 GB storage
- 191.9h compute/mese
- 3 GB data transfer/mese
- Backup automatici (7 giorni)
- Auto-pause dopo inattivita'
