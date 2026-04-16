# 1. OBJECTIVE

Implementare un sistema di trading automatizzato cloud-native che gira su HuggingFace Spaces con database Supabase, capace di:

- **Esecuzione agenti 24/7** senza necessità di server fisico
- **Dati market live streaming** in tempo reale
- **Dashboard real-time** per monitoraggio agenti e performance strategie
- **Notifiche automatiche** su Discord/Telegram

# 2. CONTEXT SUMMARY

Il progetto attuale è un sistema multi-agent per trading (ResearchAgent, SpecAgent, MLEngineerAgent, TradingExecutor, MonitoringAgent) attualmente configurato per esecuzione locale o Docker.

**Problemi da risolvere:**
- Docker locale richiede PC sempre acceso
- GitHub Actions ha limiti di esecuzione
- Nessun storage cloud per dati persistenti
- Dashboard non è real-time

**Architettura target:**
- **Frontend/Dashboard**: HuggingFace Spaces (Gradio/Streamlit)
- **Backend/API**: Python su HuggingFace Spaces
- **Database**: Supabase (PostgreSQL serverless)
- **Notifiche**: Discord/Telegram webhooks
- **Dati market**: yfinance API o Alpha Vantage per live streaming

# 3. APPROACH OVERVIEW

L'architettura si basa su HuggingFace Spaces come piattaforma host, che offre:
- Hosting gratuito per app Python
- GPU opzionali per ML
- SSL automatico
- Costo zero per repo pubblici

Supabase fornisce:
- Database PostgreSQL serverless
- Realtime subscriptions per aggiornamenti live
- REST APIs automatiche
- 500MB storage gratuito

**Flusso dati:**
1. Agenti schedulati via GitHub Actions o cron HF Spaces
2. Trading eseguito su dati live (yfinance/Alpha Vantage)
3. Performance salvate in Supabase
4. Dashboard subscribe a cambiamenti realtime
5. Notifiche inviate automaticamente

# 4. IMPLEMENTATION STEPS

## Step 1: Configurazione Supabase

**Goal:** Creare database cloud con schema per trading system

**Method:**
1. Creare account Supabase (gratuito)
2. Creare nuovo progetto
3. Eseguire SQL per creare tabelle:

```sql
-- Tabelle principali
CREATE TABLE agents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  status TEXT DEFAULT 'idle',
  last_run TIMESTAMP,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE research_papers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT,
  authors TEXT[],
  abstract TEXT,
  arxiv_id TEXT UNIQUE,
  relevance_score FLOAT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE specs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id UUID REFERENCES research_papers(id),
  model_name TEXT,
  architecture TEXT,
  parameters JSONB,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  spec_id UUID REFERENCES specs(id),
  name TEXT,
  version TEXT,
  metrics JSONB,
  status TEXT DEFAULT 'training',
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID REFERENCES models(id),
  symbol TEXT NOT NULL,
  action TEXT NOT NULL,
  quantity FLOAT NOT NULL,
  price FLOAT NOT NULL,
  executed_at TIMESTAMP DEFAULT now(),
  status TEXT DEFAULT 'pending'
);

CREATE TABLE performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_id UUID REFERENCES models(id),
  equity FLOAT,
  total_return FLOAT,
  sharpe_ratio FLOAT,
  max_drawdown FLOAT,
  win_rate FLOAT,
  recorded_at TIMESTAMP DEFAULT now()
);

CREATE TABLE agent_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name TEXT NOT NULL,
  message TEXT,
  level TEXT DEFAULT 'info',
  metadata JSONB,
  created_at TIMESTAMP DEFAULT now()
);

-- Abilita realtime
ALTER PUBLICATION supabase_realtime ADD TABLE performance;
ALTER PUBLICATION supabase_realtime ADD TABLE trades;
ALTER PUBLICATION supabase_realtime ADD TABLE agent_logs;
```

**Reference:** Supabase Dashboard > SQL Editor

---

## Step 2: Creare App HuggingFace Spaces

**Goal:** Setup ambiente host su HF Spaces

**Method:**
1. Creare nuovo Space su huggingface.co
2. Selezionare:
   - **SDK**: Gradio (per UI) o Python (solo API)
   - **Space hardware**: CPU (gratuito)
   - **Repository type**: Public
3. Configurare `requirements.txt`:

```
fastapi
uvicorn
supabase
yfinance
python-dotenv
httpx
pandas
numpy
scikit-learn
```

4. Creare file `app.py` con struttura base

**Reference:** huggingface.co/spaces

---

## Step 3: Implementare API Backend

**Goal:** Creare endpoint REST per gestione agenti e trading

**Method:**
In `app.py`:

```python
from fastapi import FastAPI
from supabase import create_client
import yfinance as yf
from dotenv import load_dotenv

app = FastAPI()
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Endpoints esistenti da adattare
@app.post("/research")
async def run_research():
    """Esegue ResearchAgent e salva risultati"""
    # Implementare logica ResearchAgent
    pass

@app.post("/trade/execute")
async def execute_trade(request: TradeRequest):
    """Esegue trade live con dati real-time"""
    # Fetch dati live
    ticker = yf.Ticker(request.symbol)
    data = ticker.history(period="1m")
    current_price = data['Close'].iloc[-1]
    
    # Salva in Supabase
    supabase.table('trades').insert({...})
    pass

@app.get("/realtime/performance")
async def get_realtime_performance():
    """Ritorna performance con subscription realtime"""
    return supabase.table('performance').select('*').order('recorded_at', desc=True).limit(1).execute()
```

**Reference:** `api/main.py` (codice esistente da adattare)

---

## Step 4: Implementare Dashboard Real-time

**Goal:** Creare UI per monitoraggio con aggiornamenti live

**Method:**
Opzione A - **Gradio** (consigliato per HF Spaces):
```python
import gradio as gr
import supabase
from supabase.lib import client_utils

def get_live_performance():
    response = supabase.table('performance').select('*').order('recorded_at', desc=True).limit(1).execute()
    return response.data[0] if response.data else {}

def update_dashboard():
    perf = get_live_performance()
    trades = supabase.table('trades').select('*').order('executed_at', desc=True).limit(10).execute()
    return perf, trades.data

with gr.Blocks() as demo:
    gr.Label(value="Trading Dashboard")
    performance_display = gr.JSON(label="Performance")
    trades_table = gr.Dataframe(label="Recent Trades")
    
    demo.load(update_dashboard, None, [performance_display, trades_table])

# Abilita realtime con refresh automatico
demo.load(fn=update_dashboard, every=5)  # refresh ogni 5 secondi
```

Opzione B - **Streamlit** con Supabase realtime:
```python
import streamlit as st
from supabase import create_client
import pandas as pd

st.set_page_config(page_title="Trading Dashboard", page_icon="📈")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Query con realtime
st.title("📈 Trading Agents Dashboard")

# Performance metrics
perf = supabase.table('performance').select('*').order('recorded_at', desc=True).limit(1).execute()
if perf.data:
    p = perf.data[0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Equity", f"${p['equity']:,.2f}")
    col2.metric("Return", f"{p['total_return']*100:.2f}%")
    col3.metric("Sharpe", f"{p['sharpe_ratio']:.2f}")
    col4.metric("Win Rate", f"{p['win_rate']*100:.1f}%")

# Trades in tempo reale
st.subheader("Recent Trades")
trades = supabase.table('trades').select('*').order('executed_at', desc=True).limit(20).execute()
df = pd.DataFrame(trades.data)
st.dataframe(df)

# Auto-refresh
st.auto_refresh = st.empty()
```

**Reference:** `dashboards/index.html` (ispirazione per layout)

---

## Step 5: Integrare Dati Live Streaming

**Goal:** Ottenere prezzi real-time per trading

**Method:**
1. **yfinance** (gratuito):
```python
import yfinance as yf

def get_live_price(symbols: list) -> dict:
    prices = {}
    for symbol in symbols:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d", interval="1m")
        prices[symbol] = {
            "price": data['Close'].iloc[-1],
            "volume": data['Volume'].iloc[-1],
            "timestamp": data.index[-1]
        }
    return prices
```

2. **Alpha Vantage** (API key richiesta):
```python
import httpx

ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")

def get_alpha_vantage_quote(symbol):
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}"
    response = httpx.get(url).json()
    return response['Global Quote']
```

3. **Salvare dati in Supabase**:
```python
def save_market_data(symbol, data):
    supabase.table('market_data').insert({
        "symbol": symbol,
        "price": data['price'],
        "volume": data['volume'],
        "timestamp": data['timestamp']
    }).execute()
```

**Reference:** `configs/agents.yaml` (simboli configurati: AAPL, MSFT, GOOG, AMZN, TSLA)

---

## Step 6: Implementare Notifiche

**Goal:** Alert automatici su Discord/Telegram

**Method:**

### Discord Webhook:
```python
import httpx

async def notify_discord(message: str, embed: dict = None):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    payload = {"content": message}
    if embed:
        payload["embeds"] = [embed]
    
    await httpx.AsyncClient().post(webhook_url, json=payload)

# Esempi di notifica
async def notify_trade_executed(trade):
    await notify_discord(
        f"🚀 Trade eseguito: {trade['action']} {trade['quantity']} {trade['symbol']} @ ${trade['price']}",
        {"color": 3066993, "fields": [...]}
    )

async def notify_alert(alert_type, message):
    colors = {"warning": 16776960, "error": 15158332, "success": 3066993}
    await notify_discord(f"⚠️ {alert_type}: {message}", {"color": colors.get(alert_type, 0)})
```

### Telegram Bot:
```python
import httpx

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def notify_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    await httpx.AsyncClient().post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    })
```

### Notifiche da GitHub Actions:
```yaml
# .github/workflows/notify.yml
- name: Discord Notification
  uses: withdraw/discord-gh-action@v1
  with:
    webhook: ${{ secrets.DISCORD_WEBHOOK }}
    message: "🎯 Trade eseguito: ${{ github.event.inputs.symbol }}"
```

**Reference:** `configs/agents.yaml` (alert_thresholds già configurati)

---

## Step 7: Configurare Scheduling

**Goal:** Esecuzione automatica periodica agenti

**Method:**

### Opzione A - GitHub Actions Cron:
```yaml
# .github/workflows/scheduled-research.yml
on:
  schedule:
    - cron: '0 6 * * 1'  # Lunedì ore 6
  workflow_dispatch:

jobs:
  research:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Research Agent
        run: python -m agents.research.research_agent
      - name: Save to Supabase
        run: |
          curl -X POST ${{ secrets.SUPABASE_URL }}/rest/v1/research_papers \
            -H "apikey: ${{ secrets.SUPABASE_KEY }}" \
            -H "Authorization: Bearer ${{ secrets.SUPABASE_KEY }}"
```

### Opzione B - HuggingFace Spaces Scheduled Jobs:
```python
# Aggiungere a app.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('cron', day_of_week='mon', hour=6)
async def scheduled_research():
    # Logica research
    pass

scheduler.start()
```

### Opzione C - External Trigger:
```bash
# Trigger manuale da qualsiasi postazione
curl -X POST "https://{space-id}.hf.space/research" \
  -H "Authorization: Bearer {API_KEY}"
```

---

## Step 8: Deploy Finale

**Goal:** Sistema completo in produzione

**Method:**
1. **Push codice su HF Spaces:**
```bash
git remote add space https://huggingface.co/spaces/{username}/{space-name}
git push space main
```

2. **Configurare secrets su HF Spaces:**
   - SUPABASE_URL
   - SUPABASE_KEY
   - DISCORD_WEBHOOK (opzionale)
   - TELEGRAM_BOT_TOKEN (opzionale)
   - ALPHA_VANTAGE_KEY (opzionale)

3. **Verificare funzionamento:**
   - Dashboard accessibile via URL
   - Endpoint API rispondono
   - Dati in tempo reale aggiornati

---

# 5. TESTING AND VALIDATION

## Criteri di successo

1. **Dashboard accessibile** - URL pubblico funzionante
2. **Dati real-time** - prezzi aggiornati ogni minuto
3. **Notifiche funzionanti** - alert su Discord/Telegram
4. **Scheduling attivo** - agenti eseguiti automaticamente
5. **Storage persistente** - dati salvati in Supabase

## Test da eseguire

| Test | Metodo | Successo |
|------|--------|----------|
| API health | `GET /health` | 200 OK |
| Trade execution | `POST /trade/execute` | Trade salvato in DB |
| Live prices | `GET /price/AAPL` | Prezzo aggiornato |
| Dashboard load | Apri URL | UI visibile in <3s |
| Realtime update | Esegui trade | Tabella aggiorna |
| Notifica Discord | Trigger trade | Messaggio su Discord |
| Scheduling | Attesa cron | Workflow eseguito |

## Monitoraggio continuo

- **Uptime**: HF Spaces offre uptime monitoring
- **Logs**: HF Spaces dashboard logs
- **Alerts**: Notifiche su errori critici
