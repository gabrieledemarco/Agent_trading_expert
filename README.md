# Trading Agents

Self-hosted multi-agent system for ML-based trading with automated research, model development, and trading execution.

## Overview

This system implements a multi-agent architecture for quantitative trading:

1. **ResearchAgent** - Weekly research for new ML/quant publications from arXiv
2. **SpecAgent** - Transform research papers into technical specifications
3. **MLEngineerAgent** - Implement, validate, and test ML models
4. **TradingExecutorAgent** - Execute and monitor trading strategies

## Architecture

```
Weekly Research → Spec Creation → Model Implementation → Testing → Live Trading
     ↓                   ↓                ↓                ↓          ↓
ResearchAgent    SpecAgent       MLEngineerAgent   Testing    TradingExecutor
     ↓                   ↓                ↓                ↓          ↓
  arXiv/API        Action Plan      ML Models      Validation    Real-time
                                   + Backtesting                  Execution
```

## Quick Start

### Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run research agent
python -m agents.research.research_agent

# Run spec generation
python -m agents.spec.spec_agent

# Run model implementation
python -m agents.ml_engineer.ml_engineer_agent

# Run trading executor
python -m agents.trading.trading_executor
```

### Docker Setup

```bash
docker-compose -f configs/docker-compose.yaml up
```

### Kubernetes Setup

```bash
kubectl apply -f configs/kubernetes.yaml
```

## GitHub Actions Workflows

The system uses GitHub Actions for workflow automation:

- **weekly-research.yml** - Runs every Monday to search arXiv
- **spec-generation.yml** - Generates technical specs from research
- **model-validation.yml** - Tests and validates new models
- **trading-execution.yml** - Executes trading strategies

### Running Workflows

```bash
# Trigger research manually
gh workflow run weekly-research.yml

# Trigger trading execution
gh workflow run trading-execution.yml -f model_version=model_v1 -f symbols=AAPL,MSFT
```

## Configuration

Edit `configs/agents.yaml` to configure:

- Agent schedules
- Trading parameters
- Data sources
- Risk management rules

## API

Start the API server:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Available endpoints:

- `GET /` - API info
- `GET /health` - Health check
- `POST /research` - Run research
- `GET /models` - List models
- `POST /trade/execute` - Execute trade
- `GET /performance` - Get performance

## Testing

```bash
pytest tests/ -v
```

## Risk Warning

⚠️ **Important**: This system is for educational and research purposes.
- Default to paper trading (no real money)
- Always validate models with out-of-sample testing
- Review risk management settings before live trading

## License

MIT