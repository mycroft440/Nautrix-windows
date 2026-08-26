#!/usr/bin/env python3
"""Validate Nautrix network/preconnect patches against exact pinned Chromium files."""

from __future__ import annotations

import base64
import importlib.util
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_module(filename: str, name: str):
    path = REPO / "tools" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pinned_revision() -> str:
    for raw in (REPO / "chromium/VERSION").read_text(encoding="utf-8").splitlines():
        key, sep, value = raw.strip().partition("=")
        if sep and key == "REVISION":
            if len(value) != 40:
                raise RuntimeError("Invalid Chromium REVISION")
            return value
    raise RuntimeError("REVISION not found in chromium/VERSION")


def fetch_source(revision: str, path: str) -> str:
    url = f"https://chromium.googlesource.com/chromium/src/+/{revision}/{path}?format=TEXT"
    request = urllib.request.Request(url, headers={"User-Agent": "Nautrix-upstream-patch-validator/2.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        encoded = response.read()
    try:
        return base64.b64decode(encoded, validate=True).decode("utf-8")
    except Exception as exc:
        raise RuntimeError(f"Invalid Gitiles source response for {path}") from exc


def main() -> int:
    revision = pinned_revision()
    network_source = fetch_source(revision, "services/network/network_service.cc")
    preconnect_source = fetch_source(revision, "chrome/browser/navigation_predictor/search_engine_preconnector.cc")
    assert "NetworkService::ConfigureStubHostResolver" in network_source
    assert "SearchEnginePreconnector::PreconnectDSE" in preconnect_source

    dns_module = load_module("apply_nautrix.py", "apply_nautrix")
    preconnect_module = load_module("apply_preconnect.py", "apply_preconnect")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        network = root / "services/network/network_service.cc"
        preconnect = root / "chrome/browser/navigation_predictor/search_engine_preconnector.cc"
        network.parent.mkdir(parents=True)
        preconnect.parent.mkdir(parents=True)
        network.write_text(network_source, encoding="utf-8", newline="\n")
        preconnect.write_text(preconnect_source, encoding="utf-8", newline="\n")

        dns_module._patch_network_service_dns(root)
        dns_module._patch_network_service_dns(root)
        preconnect_module.apply(root)
        preconnect_module.apply(root)

        patched_network = network.read_text(encoding="utf-8")
        assert patched_network.count("// NAUTRIX_DNS_OVERRIDE_BEGIN") == 1
        assert "const bool nautrix_dns_active" in patched_network
        assert "overrides.allow_dns_over_https_upgrade = false" in patched_network
        assert "SetDnsConfigOverrides(overrides)" in patched_network

        patched_preconnect = preconnect.read_text(encoding="utf-8")
        assert patched_preconnect.count("// NAUTRIX_PRIORITY_PRECONNECT_BEGIN") == 1
        assert "NAUTRIX_PRECONNECT_ORIGINS" in patched_preconnect
        assert "GetPreconnectManager().StartPreconnectUrl" in patched_preconnect
        assert "kLoadingPredictorPreconnectTrafficAnnotation" in patched_preconnect
        assert "GetNoOpNetworkRestrictionsId" in patched_preconnect

    print(f"Nautrix DNS/preconnect patches match pinned Chromium revision {revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
