"""Research Agent - Weekly research for ML/quant publications."""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import feedparser
import requests
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResearchAgent:
    """Agent responsible for researching new ML/quant publications."""

    def __init__(self, output_dir: str = "data/research_findings"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.categories = [
            ("q-fin.PR", "Quantitative Finance: Portfolio Management"),
            ("cs.LG", "Machine Learning"),
            ("stat.ML", "Machine Learning (Statistics)"),
        ]

    def search_arxiv(
        self,
        search_query: str = "trading OR quantitative finance OR portfolio optimization",
        max_results: int = 10,
    ) -> list[dict]:
        """Search arXiv for relevant papers."""
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
            logger.error(f"Error searching arXiv: {e}")
            return []

    def _parse_arxiv_response(self, xml_content: str) -> list[dict]:
        """Parse arXiv XML response."""
        import xml.etree.ElementTree as ET

        papers = []
        try:
            root = ET.fromstring(xml_content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                paper = {
                    "id": entry.find("atom:id", ns).text,
                    "title": entry.find("atom:title", ns).text.replace("\n", " "),
                    "summary": entry.find("atom:summary", ns).text.replace("\n", " "),
                    "published": entry.find("atom:published", ns).text,
                    "authors": [
                        author.find("atom:name", ns).text
                        for author in entry.findall("atom:author", ns)
                    ],
                    "categories": [
                        cat.attrib.get("term", "")
                        for cat in entry.findall("atom:category", ns)
                    ],
                }
                # Add PDF link
                for link in entry.findall("atom:link", ns):
                    if link.attrib.get("title") == "pdf":
                        paper["pdf_url"] = link.attrib.get("href", "")
                        break

                papers.append(paper)
        except Exception as e:
            logger.error(f"Error parsing XML: {e}")

        return papers

    def filter_relevant_papers(self, papers: list[dict]) -> list[dict]:
        """Filter papers relevant to trading/ML."""
        keywords = [
            "trading",
            "portfolio",
            "asset allocation",
            "reinforcement learning",
            "deep learning",
            "time series",
            "forecasting",
            "risk management",
            "market prediction",
            "stock",
        ]

        relevant = []
        for paper in papers:
            text = (paper.get("title", "") + " " + paper.get("summary", "")).lower()
            if any(kw in text for kw in keywords):
                relevant.append(paper)

        return relevant

    def create_summary(self, papers: list[dict]) -> str:
        """Create markdown summary of research findings."""
        date = datetime.now().strftime("%Y-%m-%d")
        summary = f"""# Research Findings - {date}

## Summary
Found {len(papers)} relevant papers this week.

"""

        for i, paper in enumerate(papers, 1):
            summary += f"""### {i}. {paper['title']}

- **ID**: {paper['id']}
- **Published**: {paper['published'][:10]}
- **Authors**: {', '.join(paper['authors'][:3])}
- **Categories**: {', '.join(paper['categories'])}

**Abstract**:
{paper['summary'][:500]}...

"""

            if paper.get("pdf_url"):
                summary += f"- **PDF**: {paper['pdf_url']}\n"

            summary += "\n---\n\n"

        return summary

    def run_weekly_research(self) -> str:
        """Run weekly research and save findings."""
        logger.info("Starting weekly research...")

        # Search for papers
        papers = self.search_arxiv(max_results=20)

        # Filter relevant
        relevant = self.filter_relevant_papers(papers)
        logger.info(f"Found {len(relevant)} relevant papers")

        # Create summary
        summary = self.create_summary(relevant)

        # Save to file
        output_file = self.output_dir / f"research_{datetime.now().strftime('%Y-%m-%d')}.md"
        output_file.write_text(summary)
        logger.info(f"Saved research findings to {output_file}")

        return str(output_file)


if __name__ == "__main__":
    agent = ResearchAgent()
    output = agent.run_weekly_research()
    print(f"Research complete. Output: {output}")