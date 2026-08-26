#!/usr/bin/env python3
"""Validate Nautrix trading latency/keepalive patches against pinned Chromium."""

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
    raise RuntimeError("REVISION not found")


def fetch_text(revision: str, path: str) -> str:
    url = f"https://chromium.googlesource.com/chromium/src/+/{revision}/{path}?format=TEXT"
    request = urllib.request.Request(url, headers={"User-Agent": "Nautrix-latency-validator/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        encoded = response.read()
    return base64.b64decode(encoded, validate=True).decode("utf-8")


def write_source(root: Path, path: str, content: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    revision = pinned_revision()
    source_paths = [
        "services/network/url_loader.cc",
        "third_party/blink/renderer/platform/scheduler/main_thread/frame_scheduler_impl.h",
        "third_party/blink/renderer/platform/scheduler/main_thread/frame_scheduler_impl.cc",
        "chrome/browser/navigation_predictor/search_engine_preconnector.cc",
    ]
    sources = {path: fetch_text(revision, path) for path in source_paths}

    # Validate the experimental network symbols used by the launcher exist on
    # the exact Chromium pin rather than trusting current-main documentation.
    net_features = fetch_text(revision, "net/base/features.cc")
    for token in (
        "kOptimisticDnsForTcp",
        "kEnableIntermediateDnsResults",
        "kAdjustIPv6FallbackTime",
        "kIPv6FallbackBasedOnRTT",
        "kEnableWebsocketsOverHttp3",
    ):
        assert token in net_features, f"pinned Chromium missing network feature: {token}"

    # Chromium exposes a native reusable spare renderer. Nautrix deliberately
    # preserves this mechanism instead of injecting unsupported feature names.
    render_process_host = fetch_text(revision, "content/public/browser/render_process_host.h")
    assert "WarmupSpareRenderProcessHost" in render_process_host
    assert "spare RenderProcessHost" in render_process_host

    trading = load_module("apply_trading_latency.py", "apply_trading_latency")
    preconnect = load_module("apply_preconnect.py", "apply_preconnect")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for path, content in sources.items():
            write_source(root, path, content)

        trading.apply(root)
        trading.apply(root)
        preconnect.apply(root)
        preconnect.apply(root)

        url_loader = (root / source_paths[0]).read_text(encoding="utf-8")
        frame_h = (root / source_paths[1]).read_text(encoding="utf-8")
        frame_cc = (root / source_paths[2]).read_text(encoding="utf-8")
        preconnect_cc = (root / source_paths[3]).read_text(encoding="utf-8")

        assert url_loader.count("// NAUTRIX_TRADING_NETWORK_BEGIN") == 1
        assert "url_request_->SetPriority(net::HIGHEST)" in url_loader
        assert "NAUTRIX_TRADING_MODE" in url_loader
        assert "NAUTRIX_NETWORK_PRIORITY_BOOST" in url_loader

        assert frame_h.count("// NAUTRIX_TRADING_SCHEDULER_FIELD") == 1
        assert frame_cc.count("// NAUTRIX_TRADING_SCHEDULER_BEGIN") == 1
        assert "nautrix_low_latency_page_" in frame_cc
        assert "NAUTRIX_SELECTIVE_THROTTLING_BYPASS" in frame_cc
        assert "return ThrottlingType::kNone" in frame_cc
        assert "return TaskPriority::kHighPriority" in frame_cc

        assert preconnect_cc.count("// NAUTRIX_PRIORITY_PRECONNECT_BEGIN") == 1
        assert "ConnectionKeepAliveConfig" in preconnect_cc
        assert "NAUTRIX_KEEPALIVE_IDLE_SECONDS" in preconnect_cc
        assert "NAUTRIX_KEEPALIVE_PING_SECONDS" in preconnect_cc
        assert "enable_connection_keep_alive = true" in preconnect_cc

    print(f"Nautrix trading latency patches match pinned Chromium revision {revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
