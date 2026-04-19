# Deployment — Render + Neon PostgreSQL

**Architettura**: Render (frontend + API) + Neon PostgreSQL  
**Database**: Neon PostgreSQL Serverless (Free Tier)

---

## Architettura

```
Utente (Browser)
       |
       v
Render Web Service  (frontend HTML + API — stesso server)
  URL: https://agent-trading-expert.onrender.com
  |
  ├── /dashboards/   → HTML statici (FastAPI StaticFiles)
  └── /api/*         → API endpoints (FastAPI)
       |
       | PostgreSQL Connection (SSL)
       v
Neon PostgreSQL Serverless
  URL: ep-xxx-pooler.us-east-1.aws.neon.tech
```

**Costi**: $0/mese (tutto free tier)

**Accesso dashboard**: https://agent-trading-expert.onrender.com/dashboards/

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
# Health check
curl https://agent-trading-expert.onrender.com/health

# Dashboard principale
open https://agent-trading-expert.onrender.com/dashboards/

# API summary
curl https://agent-trading-expert.onrender.com/dashboard/summary
```

Nel Neon SQL Editor:
```sql
SELECT COUNT(*) FROM agent_logs;
```

---

## Come Funziona

`DataStorageManager` richiede `DATABASE_URL` con prefisso `postgresql://` o `postgres://`.  
Le 7 tabelle (research, specs, models, validation, trades, performance, agent_logs) vengono create automaticamente alla prima connessione.

Per popolare il DB con dati demo:
```bash
DATABASE_URL=postgresql://... python scripts/seed_neon.py
```

---

## Free Tier Neon

- 0.5 GB storage
- 191.9h compute/mese
- 3 GB data transfer/mese
- Backup automatici (7 giorni)
- Auto-pause dopo inattività
