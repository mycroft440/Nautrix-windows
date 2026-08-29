#!/usr/bin/env python3
"""Validate Nautrix branding and Windows identity on pinned Chromium."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

from upstream_fetch import fetch_gitiles_text

REPO = Path(__file__).resolve().parents[1]


def load_module():
    path = REPO / "tools/apply_nautrix.py"
    spec = importlib.util.spec_from_file_location("apply_nautrix", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pinned_revision() -> str:
    for raw in (REPO / "chromium/VERSION").read_text(encoding="utf-8").splitlines():
        key, separator, value = raw.strip().partition("=")
        if separator and key == "REVISION":
            if len(value) != 40:
                raise RuntimeError("Invalid Chromium REVISION")
            return value
    raise RuntimeError("REVISION not found in chromium/VERSION")


def main() -> int:
    revision = pinned_revision()
    paths = (
        "chrome/app/theme/chromium/BRANDING",
        "chrome/install_static/chromium_install_modes.h",
        "chrome/app/chromium_strings.grd",
        "services/network/network_service.cc",
    )
    sources = {
        path: fetch_gitiles_text(
            revision,
            path,
            user_agent="Nautrix-product-identity-validator/1.0",
            timeout=45,
        )
        for path in paths
    }

    module = load_module()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for relative, source in sources.items():
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source, encoding="utf-8", newline="\n")

        module.apply(root)
        module.apply(root)

        modes = (root / "chrome/install_static/chromium_install_modes.h").read_text(
            encoding="utf-8"
        )
        unique_tokens = (
            'kSafeBrowsingName[] = "nautrix"',
            'kProductPathName[] = L"Nautrix"',
            "A7564E8E-A0AE-4BD2-8312-6E563FCDC031",
            "0xEF7084E3",
            "0x9CDC8406",
            "0xCF9474A8",
            "0x1009CE63",
            "0xC84620C3",
            "S-1-15-2-1678718263-3522501877-2723596049-3126371815-",
        )
        for token in unique_tokens:
            assert modes.count(token) == 1, f"Missing or duplicate Nautrix identity: {token}"

        inherited_tokens = (
            "7D2B3E1D-D096-4594-9D8F-A6667F12E0AC",
            "0x635EFA6F",
            "0xD133B120",
            "0xbb19a0e5",
            "0x83f69367",
            "0xa3fd580a",
            "S-1-15-2-3251537155-1984446955-2931258699-841473695-",
        )
        for token in inherited_tokens:
            assert token not in modes, f"Chromium identity was not replaced: {token}"

    print(f"Nautrix product identity matches pinned Chromium revision {revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
