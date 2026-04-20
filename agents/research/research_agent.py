"""Research Agent — weekly arXiv scan for ML/quant publications.

Writes results to Neon PostgreSQL (research table + agent_logs).
Triggered by:
  • POST /api/agents/research/run  (manual / external cron)
  • FastAPI startup if no run in the last 7 days
  • CLI: python -m agents.research.research_agent
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from agents.base.base_agent import BaseAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AGENT_NAME = "ResearchAgent"

# Weighted keywords for relevance scoring
_KEYWORD_WEIGHTS: list[tuple[str, float]] = [
    ("reinforcement learning", 1.0),
    ("deep reinforcement", 1.0),
    ("portfolio optimization", 1.0),
    ("algorithmic trading", 1.0),
    ("quantitative trading", 1.0),
    ("high frequency trading", 0.9),
    ("market microstructure", 0.9),
    ("asset allocation", 0.8),
    ("risk management", 0.8),
    ("market prediction", 0.8),
    ("stock prediction", 0.8),
    ("time series forecasting", 0.8),
    ("neural network", 0.7),
    ("deep learning", 0.7),
    ("lstm", 0.7),
    ("transformer", 0.6),
    ("trading", 0.6),
    ("portfolio", 0.6),
    ("forecasting", 0.5),
    ("stock", 0.5),
    ("equity", 0.4),
    ("financial", 0.3),
]

_HIGH_VALUE_CATEGORIES = {"q-fin.PR", "q-fin.TR", "q-fin.CP", "q-fin.RM", "q-fin.ST"}
_MEDIUM_VALUE_CATEGORIES = {"cs.LG", "stat.ML", "cs.AI", "econ.EM"}


class ResearchAgent(BaseAgent):
    """Scans arXiv weekly for ML/quant papers and persists results to Neon."""

    def __init__(self, output_dir: str = "data/research_findings"):
        super().__init__()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── arXiv fetch ────────────────────────────────────────────────────────

    def search_arxiv(
        self,
        search_query: str = "trading OR quantitative finance OR portfolio optimization",
        max_results: int = 20,
    ) -> list[dict]:
        """Fetch papers from arXiv API."""
        base_url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": search_query,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            return self._parse_arxiv_response(response.text)
        except Exception as e:
            logger.error(f"arXiv fetch failed: {e}")
            return []

    def _parse_arxiv_response(self, xml_content: str) -> list[dict]:
        import xml.etree.ElementTree as ET

        papers = []
        try:
            root = ET.fromstring(xml_content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                paper = {
                    "id":         entry.find("atom:id", ns).text,
                    "title":      entry.find("atom:title", ns).text.replace("\n", " ").strip(),
                    "summary":    entry.find("atom:summary", ns).text.replace("\n", " ").strip(),
                    "published":  entry.find("atom:published", ns).text,
                    "authors":    [
                        a.find("atom:name", ns).text
                        for a in entry.findall("atom:author", ns)
                    ],
                    "categories": [
                        c.attrib.get("term", "")
                        for c in entry.findall("atom:category", ns)
                    ],
                    "pdf_url":    "",
                }
                for link in entry.findall("atom:link", ns):
                    if link.attrib.get("title") == "pdf":
                        paper["pdf_url"] = link.attrib.get("href", "")
                        break
                papers.append(paper)
        except Exception as e:
            logger.error(f"XML parse error: {e}")
        return papers

    # ── Scoring & filtering ────────────────────────────────────────────────

    def score_paper(self, paper: dict) -> float:
        """Return a relevance score in [0, 1]."""
        text = (paper.get("title", "") + " " + paper.get("summary", "")).lower()
        categories = set(paper.get("categories", []))

        # Keyword score (capped at 1.0)
        kw_score = 0.0
        for kw, weight in _KEYWORD_WEIGHTS:
            if kw in text:
                kw_score = min(1.0, kw_score + weight * 0.15)

        # Category bonus
        cat_bonus = 0.0
        if categories & _HIGH_VALUE_CATEGORIES:
            cat_bonus = 0.3
        elif categories & _MEDIUM_VALUE_CATEGORIES:
            cat_bonus = 0.15

        # Recency bonus (papers within last 30 days)
        recency_bonus = 0.0
        try:
            pub = datetime.fromisoformat(paper.get("published", "").replace("Z", "+00:00"))
            days_old = (datetime.now(pub.tzinfo) - pub).days
            if days_old <= 7:
                recency_bonus = 0.15
            elif days_old <= 30:
                recency_bonus = 0.08
        except Exception:
            pass

        return min(1.0, round(kw_score + cat_bonus + recency_bonus, 3))

    def filter_relevant_papers(self, papers: list[dict], min_score: float = 0.1) -> list[dict]:
        """Score all papers, return those above min_score sorted by score desc."""
        scored = []
        for paper in papers:
            score = self.score_paper(paper)
            if score >= min_score:
                paper = dict(paper)
                paper["relevance_score"] = score
                scored.append(paper)
        return sorted(scored, key=lambda p: p["relevance_score"], reverse=True)

    # ── Markdown summary ───────────────────────────────────────────────────

    def create_summary(self, papers: list[dict]) -> str:
        date = datetime.now().strftime("%Y-%m-%d")
        lines = [f"# Research Findings — {date}\n", f"Found {len(papers)} relevant papers.\n"]
        for i, p in enumerate(papers, 1):
            score = p.get("relevance_score", 0)
            lines.append(f"### {i}. {p['title']} (score: {score:.2f})\n")
            lines.append(f"- **Published**: {p['published'][:10]}")
            lines.append(f"- **Authors**: {', '.join(p['authors'][:3])}")
            lines.append(f"- **Categories**: {', '.join(p['categories'])}")
            lines.append(f"\n{p['summary'][:500]}…\n")
            if p.get("pdf_url"):
                lines.append(f"- **PDF**: {p['pdf_url']}")
            lines.append("\n---\n")
        return "\n".join(lines)

    # ── DB helpers ─────────────────────────────────────────────────────────

    def _last_run_date(self) -> Optional[datetime]:
        """Return datetime of the most recent research entry, or None."""
        try:
            rows = self.db.get_research(limit=1)
            if rows:
                found = rows[0].get("found_date", "")
                return datetime.strptime(found, "%Y-%m-%d") if found else None
        except Exception:
            pass
        return None

    def should_run_now(self, min_interval_days: int = 7) -> bool:
        """True if we haven't run in the last min_interval_days days (default: 7)."""
        last = self._last_run_date()
        if last is None:
            return True
        return (datetime.now() - last).days >= min_interval_days

    # ── Main run ───────────────────────────────────────────────────────────

    def run_weekly_research(self) -> dict:
        """Full research cycle: fetch → score → persist → log.

        Returns a summary dict with counts and the output file path.
        """
        self.log_activity("active", "Research cycle started")
        logger.info("Research cycle started")

        try:
            papers = self.search_arxiv(max_results=25)
            if not papers:
                self.log_activity("warning", "arXiv returned 0 papers — network issue?")
                return {"total": 0, "saved": 0, "error": "no papers fetched"}

            relevant = self.filter_relevant_papers(papers, min_score=0.1)
            logger.info(f"{len(papers)} fetched, {len(relevant)} relevant")

            # Persist to Neon
            saved = 0
            for paper in relevant:
                try:
                    self.db.save_research({
                        "id":              str(paper.get("id", "")),
                        "title":           str(paper.get("title", "")),
                        "authors":         str(paper.get("authors", [])),
                        "published":       str(paper.get("published", "")),
                        "categories":      str(paper.get("categories", [])),
                        "abstract":        str(paper.get("summary", "")),
                        "pdf_url":         str(paper.get("pdf_url", "")),
                        "relevance_score": float(paper.get("relevance_score", 0)),
                    })
                    saved += 1
                except Exception as e:
                    logger.warning(f"Could not save paper '{paper.get('title', '')}': {e}")

            # Save markdown file
            output_file = self.output_dir / f"research_{datetime.now().strftime('%Y-%m-%d')}.md"
            output_file.write_text(self.create_summary(relevant))

            msg = f"Research complete: {saved}/{len(relevant)} papers saved to Neon (file: {output_file.name})"
            self.log_activity("active", msg)
            logger.info(msg)

            return {
                "total_fetched": len(papers),
                "relevant":      len(relevant),
                "saved_to_db":   saved,
                "output_file":   str(output_file),
                "top_papers":    relevant[:5],
            }

        except Exception as e:
            err = f"Research cycle failed: {e}"
            logger.error(err, exc_info=True)
            try:
                self.log_activity("error", err)
            except Exception:
                pass
            return {"error": str(e)}

    def run(self) -> dict:
        """Alias for run_weekly_research — used by scheduler and CLI."""
        return self.run_weekly_research()


if __name__ == "__main__":
    agent = ResearchAgent()
    result = agent.run()
    print(f"Research complete: {result}")
