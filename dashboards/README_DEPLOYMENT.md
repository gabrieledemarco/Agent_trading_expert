# Dashboard Deployment Guide

## Two Versions Available

### **Version 1: Static HTML (GitHub Pages)**
- **File**: `dashboard_backtest.html`
- **Data**: Hardcoded JSON (6 models)
- **Hosting**: GitHub Pages, Netlify, Vercel (no backend needed)
- **Use case**: View pre-generated validation results, no live connection

```bash
# Deploy to GitHub Pages
git add dashboards/dashboard_backtest.html
git push origin main

# Then enable GitHub Pages in repo settings (/ or /docs folder)
```

### **Version 2: Live API Dashboard (Requires Server)**
- **File**: `dashboard_backtest_live.html`
- **Data**: Fetched from your Execution Engine API in real-time
- **Hosting**: GitHub Pages (frontend) + API server (backend)
- **Use case**: Live monitoring, dynamic strategy updates

## Deployment Flow

### Step 1: Deploy Execution Engine API Server

The API server must run somewhere with internet access:

**Option A: Railway (recommended for fast deploy)**
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Initialize and deploy
railway init
railway up
```

Config: `railway.toml`
```toml
[build]
builder = "python"
pythonVersion = "3.11"

[deploy]
startCommand = "uvicorn execution_engine.app:app --host 0.0.0.0 --port $PORT"
```

**Option B: Heroku**
```bash
heroku create your-trading-api
git push heroku main
```

Procfile:
```
web: uvicorn execution_engine.app:app --host 0.0.0.0 --port $PORT
```

**Option C: VPS (AWS, DigitalOcean, Linode)**
```bash
# SSH into VPS
ssh user@your-server.com

# Clone and setup
git clone https://github.com/you/Agent_trading_expert.git
cd Agent_trading_expert
pip install -r requirements.txt

# Run with supervisor or systemd
uvicorn execution_engine.app:app --host 0.0.0.0 --port 8001
```

### Step 2: Deploy Dashboard Frontend

**Option A: GitHub Pages (Recommended)**
```bash
# Push to GitHub
git add dashboards/dashboard_backtest_live.html
git push origin main

# Access at: https://your-username.github.io/Agent_trading_expert/dashboards/dashboard_backtest_live.html
```

**Option B: Netlify (Drag & Drop)**
1. Go to https://netlify.com
2. Drag & drop the `dashboards/` folder
3. Netlify automatically deploys

**Option C: Self-hosted**
```bash
# Copy to web server
scp dashboards/dashboard_backtest_live.html user@server:/var/www/html/

# Access at: https://your-domain.com/dashboard_backtest_live.html
```

### Step 3: Configure API Endpoint

When you open `dashboard_backtest_live.html`:

1. Enter your API server URL:
   ```
   http://localhost:8001          # Local development
   https://your-api.railway.app   # Railway deployment
   https://your-domain.com:8001   # VPS with domain
   ```

2. Click "Test Connection" ✓

3. Click "Load Strategies" or "Load Summary"

## CORS Configuration

The Execution Engine already has CORS enabled for all origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # All domains can call the API
    allow_methods=["*"],
    allow_headers=["*"],
)
```

So GitHub Pages ↔ API Server calls will work automatically.

## Troubleshooting

### "Connection failed" on Test Connection

**Check 1**: Is the API server running?
```bash
curl https://your-api-server.com/health
```

Should return:
```json
{"status": "ok", "version": "0.1.0", ...}
```

**Check 2**: Is the URL correct?
- Check for typos in the API URL input
- Check that the port is correct (default 8001)

**Check 3**: CORS issue?
- Check browser console (F12 → Network)
- Look for "CORS policy" errors
- The API server already allows all origins, so this shouldn't happen

### "No strategies found"

The API returns empty strategies if:
1. The `/models/validated/` directory is empty
2. All validation JSONs have `validation_status` != "APPROVED"

Fix: Run validation agents to populate the validated directory.

## Development vs Production

### Development (Local)
```bash
# Terminal 1: Run API server
python -m uvicorn execution_engine.app:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2: Open dashboard
open dashboards/dashboard_backtest_live.html
# Or serve with: python -m http.server 8000
```

Then in the dashboard, use `http://localhost:8001`

### Production (GitHub Pages + Railway)

- Dashboard: `https://your-username.github.io/Agent_trading_expert/dashboards/dashboard_backtest_live.html`
- API: `https://your-trading-api.railway.app`

Note: Enter the full HTTPS URL with no trailing slash.

## API Endpoints Used by Dashboard

| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/health` | GET | Health check | `{status, version, started_at}` |
| `/strategies` | GET | List validated models | `{count, strategies: [{model_name, status, risk_score, sharpe_ratio, ...}]}` |
| `/dashboard/summary` | GET | Summary metrics | `{research_papers, specs_created, models_implemented, ...}` |

All endpoints are read-only (GET) and have no authentication required.

## To Add Authentication Later

If you want to protect the API:

```python
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.get("/strategies")
def list_strategies(credentials: HTTPAuthCredentials = Depends(security)):
    token = credentials.credentials
    # Validate token here
    return {...}
```

Then update the dashboard fetch:
```javascript
const resp = await fetch(url, {
    headers: {
        'Authorization': `Bearer ${YOUR_TOKEN}`
    }
});
```
