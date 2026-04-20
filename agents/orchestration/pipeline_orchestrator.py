"""Pipeline Orchestrator — coordina l'esecuzione sequenziale di tutti gli agenti."""

import logging
import threading
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

PIPELINE_PHASES = ["research", "spec", "ml_engineer", "validation", "improvement", "trading", "monitoring"]


class PipelineOrchestrator:
    """Esegue il pipeline completo o singole fasi in background thread."""

    def __init__(self):
        self._db = None
        self._running = False
        self._lock = threading.Lock()

    @property
    def db(self):
        if self._db is None:
            from data.storage.data_manager import DataStorageManager
            self._db = DataStorageManager()
        return self._db

    def run_full_pipeline(self, stop_after: Optional[str] = None) -> dict:
        """Esegue research → spec → ml_engineer → validation → improvement → monitoring.
        stop_after: nome fase dopo cui fermarsi (es. "validation")
        """
        results = {}
        for phase in PIPELINE_PHASES:
            if phase == "trading":
                continue  # trading gira in loop separato, non nel pipeline one-shot
            results[phase] = self._run_phase(phase)
            if stop_after and phase == stop_after:
                break
        return results

    def run_phase(self, phase: str) -> dict:
        """Esegue una singola fase del pipeline."""
        if phase not in PIPELINE_PHASES:
            return {"error": f"Unknown phase: {phase}. Valid: {PIPELINE_PHASES}"}
        return self._run_phase(phase)

    def _run_phase(self, phase: str) -> dict:
        self.db.log_agent_activity("PipelineOrchestrator", "active", f"Starting phase: {phase}")
        try:
            result = self._dispatch(phase)
            self.db.log_agent_activity("PipelineOrchestrator", "active", f"Phase {phase} complete: {result}")
            return {"phase": phase, "status": "ok", "result": result}
        except Exception as e:
            err = f"Phase {phase} failed: {e}"
            logger.error(err, exc_info=True)
            self.db.log_agent_activity("PipelineOrchestrator", "error", err)
            return {"phase": phase, "status": "error", "error": str(e)}

    def _dispatch(self, phase: str) -> dict:
        if phase == "research":
            from agents.research.research_agent import ResearchAgent
            return ResearchAgent().run()
        elif phase == "spec":
            from agents.spec.spec_agent import SpecAgent
            agent = SpecAgent()
            files = agent.run_spec_generation()
            return {"spec_files": files, "count": len(files)}
        elif phase == "ml_engineer":
            from agents.ml_engineer.ml_engineer_agent import MLEngineerAgent
            agent = MLEngineerAgent()
            models = agent.run_implementation()
            return {"model_files": models, "count": len(models)}
        elif phase == "validation":
            from agents.validation.validation_agent import ValidationAgent
            agent = ValidationAgent()
            statuses = agent.run_validation()
            return {"statuses": statuses, "count": len(statuses)}
        elif phase == "improvement":
            from agents.improvement.improvement_agent import ImprovementAgent
            return ImprovementAgent().run()
        elif phase == "trading":
            from agents.trading.trading_executor import TradingExecutorAgent
            agent = TradingExecutorAgent(paper_trading=True)
            return agent.run_trading_loop(
                symbols=["AAPL", "MSFT"],
                max_iterations=10,
            )
        elif phase == "monitoring":
            from agents.monitoring.monitoring_agent import MonitoringAgent
            agent = MonitoringAgent()
            alerts = agent.run_monitoring_cycle()
            return {"alerts": len(alerts)}
        return {}

    def run_pipeline_chain(self) -> dict:
        """Esegue il pipeline completo come catena sequenziale.

        Research → (se nuovi paper) → Spec → ML → Validation → Improvement
        Ogni fase parte solo se la precedente ha prodotto output.
        """
        results = {}

        # 1. Research — sempre
        r = self._run_phase("research")
        results["research"] = r
        if r.get("status") == "error":
            return results

        # 2. Spec — se research ha trovato paper
        research_result = r.get("result", {})
        if research_result.get("saved_to_db", 0) > 0 or research_result.get("relevant", 0) > 0:
            results["spec"] = self._run_phase("spec")
        else:
            results["spec"] = {"status": "skipped", "reason": "no new research papers"}

        # 3. ML Engineer — se ci sono specs pending
        try:
            pending_specs = self.db.get_specs(status="pending")
            if pending_specs:
                results["ml_engineer"] = self._run_phase("ml_engineer")
            else:
                results["ml_engineer"] = {"status": "skipped", "reason": "no pending specs"}
        except Exception:
            results["ml_engineer"] = self._run_phase("ml_engineer")

        # 4. Validation — sempre (valida modelli implemented)
        results["validation"] = self._run_phase("validation")

        # 5. Improvement — se ci sono modelli rejected
        try:
            rejected = self.db.get_validations(status="rejected")
            if rejected:
                results["improvement"] = self._run_phase("improvement")
            else:
                results["improvement"] = {"status": "skipped", "reason": "no rejected models"}
        except Exception:
            results["improvement"] = {"status": "skipped", "reason": "db error"}

        return results

    def get_pipeline_status(self) -> dict:
        """Stato corrente di ogni fase basato sul DB."""
        try:
            db = self.db
            summary = db.get_dashboard_summary()
            logs = db.get_agent_logs(limit=50)

            # Ultimo run per ogni agente
            last_runs = {}
            for log in logs:
                agent = log.get("agent_name", "")
                if agent not in last_runs:
                    last_runs[agent] = log.get("timestamp", "")

            return {
                "phases": {
                    "research":    {"records": summary.get("research_papers", 0),    "last_run": last_runs.get("ResearchAgent", None)},
                    "spec":        {"records": summary.get("specs_created", 0),       "last_run": last_runs.get("SpecAgent", None)},
                    "ml_engineer": {"records": summary.get("models_implemented", 0),  "last_run": last_runs.get("MLEngineerAgent", None)},
                    "validation":  {"records": summary.get("models_validated", 0),    "last_run": last_runs.get("ValidationAgent", None)},
                    "trading":     {"records": summary.get("total_trades", 0),        "last_run": last_runs.get("TradingExecutorAgent", None)},
                    "monitoring":  {"records": 0,                                     "last_run": last_runs.get("MonitoringAgent", None)},
                },
                "equity": summary.get("current_equity", 0),
                "total_return": summary.get("total_return", 0),
            }
        except Exception as e:
            return {"error": str(e)}
