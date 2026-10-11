"""Lightweight regression checks for the static stylesheet.

These tests parse ``orion_app/static/styles.css`` as text and assert that the
design tokens and core class selectors the UI depends on are still present.
They are intentionally dependency-free (no CSS parser required) so they stay
fast and run everywhere pytest runs.
"""

import re
from pathlib import Path

import pytest

STYLESHEET = Path(__file__).resolve().parents[1] / "orion_app" / "static" / "styles.css"

REQUIRED_VARIABLES = ("--accent", "--gold", "--danger")

REQUIRED_SELECTORS = (
    ".shell",
    ".sidebar",
    ".brand-mark",
    ".nav",
    ".hero",
    ".taskman-border-wrap",
    ".sidebar-taskman-card",
    ".tm-row",
)


@pytest.fixture(scope="module")
def css_text() -> str:
    assert STYLESHEET.is_file(), f"stylesheet missing at {STYLESHEET}"
    return STYLESHEET.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", REQUIRED_VARIABLES)
def test_required_custom_properties_defined(css_text: str, name: str) -> None:
    pattern = re.compile(rf"{re.escape(name)}\s*:\s*[^;]+;")
    assert pattern.search(css_text), f"missing custom property definition: {name}"


@pytest.mark.parametrize("selector", REQUIRED_SELECTORS)
def test_required_selectors_present(css_text: str, selector: str) -> None:
    assert selector in css_text, f"missing core selector: {selector}"


def test_balanced_braces(css_text: str) -> None:
    assert css_text.count("{") == css_text.count("}"), "unbalanced braces in stylesheet"


def test_taskman_grid_token_used(css_text: str) -> None:
    assert "--tm-grid" in css_text, "shared --tm-grid token was removed"
    assert "var(--tm-grid" in css_text, "--tm-grid is defined but never referenced"
