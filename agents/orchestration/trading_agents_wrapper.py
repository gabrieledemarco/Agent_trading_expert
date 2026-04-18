"""TradingAgentsWrapper — LangGraph orchestration with USE_TRADING_AGENTS feature flag.

When USE_TRADING_AGENTS=false (default), the wrapper runs the existing
agent pipeline directly without LangGraph overhead.

When USE_TRADING_AGENTS=true, it wraps TradingAgentsGraph.propagate()
for LLM-driven market reasoning.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

USE_TRADING_AGENTS = os.getenv("USE_TRADING_AGENTS", "false").lower() == "true"


@dataclass
class AgentDecision:
    """Structured decision from the orchestration layer."""
    ticker: str
    date: str
    action: str          # "buy" | "sell" | "hold"
    confidence: float    # 0.0 – 1.0
    reasoning: str
    source: str          # "trading_agents" | "local_pipeline"
    metadata: dict = field(default_factory=dict)


class TradingAgentsWrapper:
    """Unified interface for getting trade decisions.

    Hides whether TradingAgents/LangGraph or the local pipeline
    is running behind the scenes.
    """

    def __init__(
        self,
        llm_provider: str = "anthropic",
        model_name: str = "claude-sonnet-4-6",
        max_debate_rounds: int = 2,
    ):
        self.llm_provider = llm_provider
        self.model_name = model_name
        self.max_debate_rounds = max_debate_rounds
        self._graph = None  # lazy LangGraph instance

    # ── Public ────────────────────────────────────────────────────────────────

    def propagate(self, ticker: str, date: str) -> AgentDecision:
        """Get a trade decision for ticker on date."""
        if USE_TRADING_AGENTS:
            return self._propagate_trading_agents(ticker, date)
        return self._propagate_local(ticker, date)

    def reflect_and_remember(self, ticker: str, pnl: float) -> None:
        """Feed PnL back to the agent for reinforcement."""
        if USE_TRADING_AGENTS and self._graph is not None:
            try:
                self._graph.reflect_and_remember(pnl)
                logger.info("[%s] reflect_and_remember pnl=%.4f", ticker, pnl)
            except Exception as e:
                logger.warning("reflect_and_remember failed: %s", e)
        else:
            logger.info("[%s] PnL feedback (local): %.4f", ticker, pnl)

    # ── TradingAgents path ────────────────────────────────────────────────────

    def _propagate_trading_agents(self, ticker: str, date: str) -> AgentDecision:
        """Run TradingAgentsGraph.propagate() via LangGraph."""
        graph = self._get_graph()
        try:
            raw_result = graph.propagate(ticker, date)
            return self._parse_graph_result(ticker, date, raw_result)
        except Exception as e:
            logger.error("TradingAgentsGraph.propagate failed: %s — falling back to local", e)
            return self._propagate_local(ticker, date)

    def _get_graph(self):
        """Lazy-load TradingAgentsGraph."""
        if self._graph is None:
            try:
                from tradingagents.graph.trading_state_graph import TradingAgentsGraph
                self._graph = TradingAgentsGraph(
                    config={
                        "llm_provider": self.llm_provider,
                        "backend_url": f"https://api.anthropic.com",
                        "deep_think_llm": self.model_name,
                        "quick_think_llm": self.model_name,
                        "max_debate_rounds": self.max_debate_rounds,
                        "online_tools": False,
                    }
                )
                logger.info("TradingAgentsGraph initialized (model=%s)", self.model_name)
            except ImportError:
                logger.warning("tradingagents package not found — install with: pip install tradingagents")
                raise
        return self._graph

    def _parse_graph_result(self, ticker: str, date: str, raw: Any) -> AgentDecision:
        """Parse TradingAgentsGraph output into AgentDecision."""
        if isinstance(raw, str):
            text = raw.lower()
            if "buy" in text:
                action, confidence = "buy", 0.7
            elif "sell" in text:
                action, confidence = "sell", 0.7
            else:
                action, confidence = "hold", 0.5
            return AgentDecision(
                ticker=ticker, date=date, action=action,
                confidence=confidence, reasoning=raw[:500],
                source="trading_agents",
            )
        if isinstance(raw, dict):
            return AgentDecision(
                ticker=ticker, date=date,
                action=raw.get("action", "hold"),
                confidence=float(raw.get("confidence", 0.5)),
                reasoning=str(raw.get("reasoning", "")),
                source="trading_agents",
                metadata=raw,
            )
        return AgentDecision(
            ticker=ticker, date=date, action="hold",
            confidence=0.5, reasoning=str(raw),
            source="trading_agents",
        )

    # ── Local pipeline path ───────────────────────────────────────────────────

    def _propagate_local(self, ticker: str, date: str) -> AgentDecision:
        """Simple local signal generation (no LangGraph)."""
        try:
            from agents.trading.trading_executor import TradingExecutorAgent
            executor = TradingExecutorAgent(paper_trading=True)
            data = executor.fetch_realtime_data(ticker)
            signal = executor.generate_signal(None, data) if data else "hold"
        except Exception as e:
            logger.warning("Local signal generation failed: %s", e)
            signal = "hold"

        return AgentDecision(
            ticker=ticker,
            date=date,
            action=signal,
            confidence=0.6 if signal != "hold" else 0.5,
            reasoning=f"Local MA crossover signal for {ticker} on {date}",
            source="local_pipeline",
        )


# ── LangGraph state definition (used when USE_TRADING_AGENTS=true) ────────────

def _build_langgraph_pipeline(wrapper: TradingAgentsWrapper):
    """Build a minimal LangGraph pipeline around the wrapper.

    Only called when USE_TRADING_AGENTS=true and langgraph is installed.
    """
    try:
        from langgraph.graph import StateGraph, END
        from typing import TypedDict

        class TradingState(TypedDict):
            ticker: str
            date: str
            decision: Optional[AgentDecision]
            pnl: float

        def decide_node(state: TradingState) -> TradingState:
            decision = wrapper.propagate(state["ticker"], state["date"])
            return {**state, "decision": decision}

        def feedback_node(state: TradingState) -> TradingState:
            if state.get("pnl") is not None:
                wrapper.reflect_and_remember(state["ticker"], state["pnl"])
            return state

        graph = StateGraph(TradingState)
        graph.add_node("decide", decide_node)
        graph.add_node("feedback", feedback_node)
        graph.add_edge("decide", "feedback")
        graph.add_edge("feedback", END)
        graph.set_entry_point("decide")

        return graph.compile()
    except ImportError:
        logger.warning("langgraph not available — LangGraph pipeline disabled")
        return None
