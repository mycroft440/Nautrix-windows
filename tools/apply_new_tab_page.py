#!/usr/bin/env python3
"""Apply the Nautrix offline new-tab experience to pinned Chromium."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
OVERRIDES = REPO / "chromium/overrides/new_tab_page_third_party"
RESOURCE_ROOT = Path("chrome/browser/resources/new_tab_page_third_party")
HTML_MARKER = "<!-- NAUTRIX_NEW_TAB_PAGE_BEGIN -->"
SCRIPT_MARKER = "// NAUTRIX_NEW_TAB_PAGE_BEGIN"
ROUTING_MARKER = "// NAUTRIX_NEW_TAB_ROUTING_BEGIN"


def _patch_new_tab_routing(source_root: Path) -> None:
    path = source_root / "chrome/browser/search/search.cc"
    text = path.read_text(encoding="utf-8")
    if ROUTING_MARKER in text:
        return

    upstream = """#if BUILDFLAG(IS_ANDROID)
    const GURL local_url;
#else
    const bool default_is_google = DefaultSearchProviderIsGoogle(profile);
    const GURL local_url(default_is_google
                             ? chrome::ChromeUINewTabPageURLAsGURL()
                             : GURL(chrome::kChromeUINewTabPageThirdPartyURL));
    if (default_is_google) {
      return NewTabURLDetails(local_url, NEW_TAB_URL_VALID);
    }
#endif
"""
    replacement = """#if !BUILDFLAG(IS_ANDROID)
    // NAUTRIX_NEW_TAB_ROUTING_BEGIN
    // Always use Nautrix's local page. Its selector decides where searches go.
    const GURL local_url(chrome::kChromeUINewTabPageThirdPartyURL);
    return NewTabURLDetails(local_url, NEW_TAB_URL_VALID);
    // NAUTRIX_NEW_TAB_ROUTING_END
#else
    const GURL local_url;
"""
    if upstream not in text:
        raise RuntimeError(f"{path}: desktop new-tab routing anchor not found")
    text = text.replace(upstream, replacement, 1)

    tail = """    return NewTabURLDetails(search_provider_url, NEW_TAB_URL_VALID);
  }
"""
    patched_tail = """    return NewTabURLDetails(search_provider_url, NEW_TAB_URL_VALID);
#endif  // !BUILDFLAG(IS_ANDROID)
  }
"""
    if tail not in text:
        raise RuntimeError(f"{path}: new-tab routing tail anchor not found")
    path.write_text(
        text.replace(tail, patched_tail, 1), encoding="utf-8", newline="\n"
    )


def apply(source_root: Path) -> None:
    source_root = source_root.resolve()
    targets = {
        "new_tab_page_third_party.html": HTML_MARKER,
        "new_tab_page_third_party.ts": SCRIPT_MARKER,
    }
    required = [
        source_root / RESOURCE_ROOT / filename for filename in targets
    ] + [source_root / "chrome/browser/search/search.cc"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Pinned Chromium new-tab files are missing:\n  " + "\n  ".join(missing)
        )

    for filename, marker in targets.items():
        override = OVERRIDES / filename
        if not override.is_file():
            raise RuntimeError(f"Nautrix new-tab override is missing: {override}")
        content = override.read_text(encoding="utf-8")
        if marker not in content:
            raise RuntimeError(f"Nautrix marker is missing from {override}")
        destination = source_root / RESOURCE_ROOT / filename
        shutil.copyfile(override, destination)

    _patch_new_tab_routing(source_root)
    (source_root / ".nautrix-new-tab-page").write_text(
        "Nautrix offline new-tab page applied.\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_new_tab_page.py <chromium-src>", file=sys.stderr)
        return 2
    try:
        apply(Path(sys.argv[1]))
    except Exception as exc:
        print(f"Nautrix new-tab patch error: {exc}", file=sys.stderr)
        return 1
    print("Nautrix offline new-tab page applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
