#!/usr/bin/env python3
"""Validate Nautrix new-tab resources against exact pinned Chromium."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

from upstream_fetch import fetch_gitiles_text


REPO = Path(__file__).resolve().parents[1]
PINNED_FILES = (
    "chrome/browser/resources/new_tab_page_third_party/"
    "new_tab_page_third_party.html",
    "chrome/browser/resources/new_tab_page_third_party/"
    "new_tab_page_third_party.ts",
    "chrome/browser/search/search.cc",
)


def pinned_revision() -> str:
    for raw in (REPO / "chromium/VERSION").read_text(
            encoding="utf-8").splitlines():
        key, separator, value = raw.strip().partition("=")
        if separator and key == "REVISION":
            if len(value) != 40:
                raise RuntimeError("Invalid Chromium REVISION")
            return value
    raise RuntimeError("REVISION not found in chromium/VERSION")


def load_patch_module():
    path = REPO / "tools/apply_new_tab_page.py"
    spec = importlib.util.spec_from_file_location("apply_new_tab_page", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    revision = pinned_revision()
    sources = {
        path: fetch_gitiles_text(
            revision,
            path,
            user_agent="Nautrix-new-tab-validator/1.0",
            timeout=60,
        )
        for path in PINNED_FILES
    }

    module = load_patch_module()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for path, content in sources.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")

        module.apply(root)
        module.apply(root)

        html = (root / PINNED_FILES[0]).read_text(encoding="utf-8")
        script = (root / PINNED_FILES[1]).read_text(encoding="utf-8")
        routing = (root / PINNED_FILES[2]).read_text(encoding="utf-8")

        expected_html = (
            REPO / "chromium/overrides/new_tab_page_third_party/"
            "new_tab_page_third_party.html"
        ).read_text(encoding="utf-8")
        expected_script = (
            REPO / "chromium/overrides/new_tab_page_third_party/"
            "new_tab_page_third_party.ts"
        ).read_text(encoding="utf-8")
        assert html == expected_html
        assert script == expected_script

        assert html.count("<!-- NAUTRIX_NEW_TAB_PAGE_BEGIN -->") == 1
        assert 'id="search-engine"' in html
        assert '<option value="google">Google</option>' in html
        assert 'id="search-form"' in html
        assert 'id="search-input"' in html
        assert "Página inicial armazenada no Nautrix" in html
        assert "http://" not in html
        assert "https://" not in html
        assert html.count("<cr-most-visited>") == 1

        assert script.count("// NAUTRIX_NEW_TAB_PAGE_BEGIN") == 1
        assert "return 'google';" in script
        assert "nautrix.searchEngine" in script
        assert "window.localStorage.getItem" in script
        assert "window.localStorage.setItem" in script
        assert "encodeURIComponent(query)" in script
        assert "window.location.assign" in script
        assert "https://www.google.com/search?q=" in script
        assert "https://www.bing.com/search?q=" in script
        assert "https://duckduckgo.com/?q=" in script
        assert "https://search.brave.com/search?q=" in script

        assert routing.count("// NAUTRIX_NEW_TAB_ROUTING_BEGIN") == 1
        assert (
            "const GURL local_url(chrome::kChromeUINewTabPageThirdPartyURL);"
            in routing
        )
        assert "return NewTabURLDetails(local_url, NEW_TAB_URL_VALID);" in routing
        assert "#if !BUILDFLAG(IS_ANDROID)" in routing
        assert "#endif  // !BUILDFLAG(IS_ANDROID)" in routing

    print(
        "Nautrix offline new-tab page matches pinned Chromium revision "
        f"{revision}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
