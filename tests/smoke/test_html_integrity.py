"""Smoke tests for all 16 dashboard HTML pages.

Checks structural requirements without a browser:
- lang="en" present
- nav.js included
- dashboard_utils.js included
- No inline toggleSidebar() definition
- No stale dashboard_data.js / config.js references
- No duplicate id= attributes within a single file
"""
import re
from pathlib import Path

import pytest

DASHBOARDS = Path(__file__).parent.parent.parent / "dashboards"
HTML_FILES = sorted(DASHBOARDS.glob("*.html"))


@pytest.fixture(params=[p for p in HTML_FILES], ids=[p.name for p in HTML_FILES])
def page(request):
    return request.param.name, request.param.read_text(encoding="utf-8")


class TestHtmlStructure:
    def test_lang_en(self, page):
        name, src = page
        assert 'lang="en"' in src, f"{name}: missing lang=\"en\""

    def test_nav_js_included(self, page):
        name, src = page
        assert 'nav.js' in src, f"{name}: missing nav.js"

    def test_dashboard_utils_js_included(self, page):
        name, src = page
        assert 'dashboard_utils.js' in src, f"{name}: missing dashboard_utils.js"

    def test_no_inline_togglesidebar(self, page):
        name, src = page
        assert 'function toggleSidebar' not in src, (
            f"{name}: inline toggleSidebar() definition found (should be in nav.js)"
        )

    def test_no_stale_script_deps(self, page):
        name, src = page
        for dep in ("dashboard_data.js", "config.js"):
            assert dep not in src, f"{name}: stale script dependency '{dep}' found"

    def test_no_duplicate_ids(self, page):
        name, src = page
        ids = re.findall(r'\bid="([^"]+)"', src)
        seen, dupes = set(), set()
        for i in ids:
            if i in seen:
                dupes.add(i)
            seen.add(i)
        assert not dupes, f"{name}: duplicate id(s): {dupes}"

    def test_has_terminal_grid(self, page):
        name, src = page
        assert 'class="terminal"' in src, f"{name}: missing .terminal grid container"

    def test_has_bottombar(self, page):
        name, src = page
        assert 'class="bottombar"' in src, f"{name}: missing .bottombar footer"
