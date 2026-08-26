#!/usr/bin/env python3
"""Validate Nautrix trading latency/keepalive/warmup patches against pinned Chromium."""

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
        "chrome/browser/ui/navigator/browser_navigator.cc",
    ]
    sources = {path: fetch_text(revision, path) for path in source_paths}

    # Validate experimental network symbols on the exact Chromium pin.
    net_features = fetch_text(revision, "net/base/features.cc")
    for token in (
        "kOptimisticDnsForTcp",
        "kEnableIntermediateDnsResults",
        "kAdjustIPv6FallbackTime",
        "kIPv6FallbackBasedOnRTT",
        "kEnableWebsocketsOverHttp3",
    ):
        assert token in net_features, f"pinned Chromium missing network feature: {token}"

    # The Windows timer API requires each successful activation to be paired
    # with a later deactivation. The Nautrix patch enforces that invariant.
    time_header = fetch_text(revision, "base/time/time.h")
    assert "EnableHighResolutionTimer(bool enable)" in time_header
    assert "ActivateHighResolutionTimer(bool activate)" in time_header
    assert "Each successful activate call must be paired" in time_header

    # Use the actual spare-renderer manager API exposed by Chromium 152. This
    # API is explicitly intended for imminent navigations.
    spare_manager = fetch_text(
        revision, "content/public/browser/spare_render_process_host_manager.h"
    )
    assert "class CONTENT_EXPORT SpareRenderProcessHostManager" in spare_manager
    assert "WarmupSpare(BrowserContext* browser_context)" in spare_manager
    assert "navigation is imminent" in spare_manager

    trading = load_module("apply_trading_latency.py", "apply_trading_latency")
    preconnect = load_module("apply_preconnect.py", "apply_preconnect")
    warmup = load_module("apply_trading_warmup.py", "apply_trading_warmup")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for path, content in sources.items():
            write_source(root, path, content)

        trading.apply(root)
        trading.apply(root)
        preconnect.apply(root)
        preconnect.apply(root)
        warmup.apply(root)
        warmup.apply(root)

        url_loader = (root / source_paths[0]).read_text(encoding="utf-8")
        frame_h = (root / source_paths[1]).read_text(encoding="utf-8")
        frame_cc = (root / source_paths[2]).read_text(encoding="utf-8")
        preconnect_cc = (root / source_paths[3]).read_text(encoding="utf-8")
        navigator_cc = (root / source_paths[4]).read_text(encoding="utf-8")

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
        assert "NAUTRIX_HIGH_RES_TIMER" in frame_cc
        assert "frame_type_ == FrameType::kMainFrame" in frame_cc
        assert "base::Time::EnableHighResolutionTimer(true)" in frame_cc
        assert "base::Time::ActivateHighResolutionTimer(true)" in frame_cc
        # One deactivation for URL/mode changes and one for destruction.
        assert frame_cc.count("base::Time::ActivateHighResolutionTimer(false)") >= 2

        assert preconnect_cc.count("// NAUTRIX_PRIORITY_PRECONNECT_BEGIN") == 1
        assert "ConnectionKeepAliveConfig" in preconnect_cc
        assert "NAUTRIX_KEEPALIVE_IDLE_SECONDS" in preconnect_cc
        assert "NAUTRIX_KEEPALIVE_PING_SECONDS" in preconnect_cc
        assert "enable_connection_keep_alive = true" in preconnect_cc

        assert navigator_cc.count("// NAUTRIX_TRADING_WARMUP_BEGIN") == 1
        assert 'NAUTRIX_SPARE_RENDERER_WARMUP' in navigator_cc
        assert 'NAUTRIX_INTENT_PRECONNECT' in navigator_cc
        assert '#include "content/public/browser/spare_render_process_host_manager.h"' in navigator_cc
        assert "SpareRenderProcessHostManager::Get().WarmupSpare(" in navigator_cc
        assert "params->initiating_profile" in navigator_cc
        assert "WarmupSpareRenderProcessHost" not in navigator_cc

    print(f"Nautrix trading latency/warmup patches match pinned Chromium revision {revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
