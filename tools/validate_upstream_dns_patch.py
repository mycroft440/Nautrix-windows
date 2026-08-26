#!/usr/bin/env python3
"""Validate the Nautrix DNS patch against the exact pinned Chromium source file."""

from __future__ import annotations

import base64
import importlib.util
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load_apply_module():
    path = REPO / "tools/apply_nautrix.py"
    spec = importlib.util.spec_from_file_location("apply_nautrix", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load tools/apply_nautrix.py")
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


def fetch_network_service(revision: str) -> str:
    url = (
        "https://chromium.googlesource.com/chromium/src/+/"
        f"{revision}/services/network/network_service.cc?format=TEXT"
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Nautrix-upstream-patch-validator/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        encoded = response.read()
    try:
        return base64.b64decode(encoded, validate=True).decode("utf-8")
    except Exception as exc:
        raise RuntimeError("Chromium Gitiles response was not valid base64 source") from exc


def main() -> int:
    revision = pinned_revision()
    source = fetch_network_service(revision)
    assert "NetworkService::ConfigureStubHostResolver" in source

    module = load_apply_module()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        target = root / "services/network/network_service.cc"
        target.parent.mkdir(parents=True)
        target.write_text(source, encoding="utf-8", newline="\n")

        module._patch_network_service_dns(root)
        module._patch_network_service_dns(root)

        patched = target.read_text(encoding="utf-8")
        assert patched.count("// NAUTRIX_DNS_OVERRIDE_BEGIN") == 1
        assert "const bool nautrix_dns_active" in patched
        assert "nautrix_dns_overrides" in patched
        assert "overrides.allow_dns_over_https_upgrade = false" in patched
        assert "SetDnsConfigOverrides(overrides)" in patched

    print(f"Nautrix DNS patch matches pinned Chromium revision {revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
