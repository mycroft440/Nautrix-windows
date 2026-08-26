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


def _fetch_source(revision: str, path: str) -> str:
    url = f"https://chromium.googlesource.com/chromium/src/+/{revision}/{path}?format=TEXT"
    request = urllib.request.Request(
        url, headers={"User-Agent": "Nautrix-trading-patch-validator/1.0"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        encoded = response.read()
    return base64.b64decode(encoded, validate=True).decode("utf-8")


def main() -> int:
    revision = _pinned_revision()
    prefs_path = "components/performance_manager/user_tuning/prefs.cc"
    source = _fetch_source(revision, prefs_path)
    assert "RegisterProfilePrefs" in source
    assert "kManagedTabDiscardingExceptions" in source
    assert "kForceForegroundPriorityForUrls" in source

    # Chromium's desktop freezing opt-out delegates to the same discard
    # eligibility policy, so the managed discard exception is also the correct
    # future-compatible freezing protection path on this exact revision.
    freezing_checker = _fetch_source(
        revision,
        "chrome/browser/performance_manager/policies/freezing_opt_out_checker.cc",
    )
    assert "IsPageOptedOutOfFreezing" in freezing_checker
    assert "IsPageOptedOutOfDiscarding" in freezing_checker

    # On Windows the foreground/user-blocking path clears EcoQoS and may use
    # ABOVE_NORMAL priority. This is why Nautrix treats the two knobs as one
    # atomic scheduling policy instead of adding competing Win32 calls.
    process_win = _fetch_source(revision, "base/process/process_win.cc")
    assert "SetProcessEcoQoSState" in process_win
    assert "priority == Priority::kUserBlocking" in process_win
    assert "ProcessPowerState::kUnset" in process_win
    assert "ABOVE_NORMAL_PRIORITY_CLASS" in process_win

    module = _load_module()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        target = root / prefs_path
        target.parent.mkdir(parents=True)
        target.write_text(source, encoding="utf-8", newline="\n")

        module.apply(root)
        module.apply(root)

        patched = target.read_text(encoding="utf-8")
        assert patched.count("// NAUTRIX_TRADING_PRIORITY_BEGIN") == 1
        assert 'GetVar("NAUTRIX_TRADING_MODE")' in patched
        assert 'GetVar("NAUTRIX_TRADING_SITES")' in patched
        assert 'NautrixTradingPolicyEnabled("NAUTRIX_FREEZING_PROTECTION")' in patched
        assert 'NautrixTradingPolicyEnabled("NAUTRIX_TRADING_PROCESS_PRIORITY")' in patched
        assert 'NautrixTradingPolicyEnabled("NAUTRIX_DISABLE_ECOQOS")' in patched
        assert 'EqualsCaseInsensitiveASCII(mode, "normal")' in patched
        assert "GetNautrixLifecycleProtectedSites()" in patched
        assert "GetNautrixForegroundPrioritySites()" in patched
        assert "RegisterListPref(kManagedTabDiscardingExceptions" in patched
        assert "RegisterListPref(kForceForegroundPriorityForUrls" in patched

    print(f"Nautrix trading priority/lifecycle patch matches pinned Chromium revision {revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
