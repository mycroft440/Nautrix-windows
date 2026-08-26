#!/usr/bin/env python3
"""Validate Nautrix trading priority patch against the exact pinned Chromium source."""

from __future__ import annotations

import base64
import importlib.util
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_module():
    path = REPO / "tools/apply_trading_priority.py"
    spec = importlib.util.spec_from_file_location("apply_trading_priority", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pinned_revision() -> str:
    for raw in (REPO / "chromium/VERSION").read_text(encoding="utf-8").splitlines():
        key, sep, value = raw.strip().partition("=")
        if sep and key == "REVISION":
            if len(value) != 40:
                raise RuntimeError("Invalid Chromium REVISION")
            return value
    raise RuntimeError("REVISION not found in chromium/VERSION")


def _fetch_source(revision: str) -> str:
    path = "components/performance_manager/user_tuning/prefs.cc"
    url = f"https://chromium.googlesource.com/chromium/src/+/{revision}/{path}?format=TEXT"
    request = urllib.request.Request(
        url, headers={"User-Agent": "Nautrix-trading-patch-validator/1.0"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        encoded = response.read()
    return base64.b64decode(encoded, validate=True).decode("utf-8")


def main() -> int:
    revision = _pinned_revision()
    source = _fetch_source(revision)
    assert "RegisterProfilePrefs" in source
    assert "kManagedTabDiscardingExceptions" in source
    assert "kForceForegroundPriorityForUrls" in source

    module = _load_module()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        target = root / "components/performance_manager/user_tuning/prefs.cc"
        target.parent.mkdir(parents=True)
        target.write_text(source, encoding="utf-8", newline="\n")

        module.apply(root)
        module.apply(root)

        patched = target.read_text(encoding="utf-8")
        assert patched.count("// NAUTRIX_TRADING_PRIORITY_BEGIN") == 1
        assert 'GetVar("NAUTRIX_PRECONNECT_ORIGINS")' in patched
        assert "GetNautrixTradingSites()" in patched
        assert "RegisterListPref(kManagedTabDiscardingExceptions" in patched
        assert "RegisterListPref(kForceForegroundPriorityForUrls" in patched

    print(f"Nautrix trading priority patch matches pinned Chromium revision {revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
