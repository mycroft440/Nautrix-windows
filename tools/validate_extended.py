#!/usr/bin/env python3
"""Extended repository checks for DNS, latency, PGO, UI and full-build automation."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


def validate_configs() -> None:
    dns = read("config/dns.ini")
    for token in (
        "mode=automatic",
        "prefer_encrypted=1",
        "doh_samples=2",
        "priority_hosts=",
        "2606:4700:4700::1111",
        "2001:4860:4860::8888",
        "2620:fe::fe",
        "2a10:50c0::ad1:ff",
    ):
        assert token in dns, f"missing DNS setting: {token}"

    latency = read("config/latency.ini")
    for token in (
        "enable_happy_eyeballs_v3=1",
        "enable_priority_preconnect=1",
        "enable_quic=1",
        "enable_netlog=0",
        "enable_startup_trace=0",
        "process_priority=above_normal",
    ):
        assert token in latency, f"missing latency setting: {token}"


def validate_native_tools() -> None:
    cmake = read("launcher/CMakeLists.txt")
    assert "NautrixLauncher" in cmake
    assert "NautrixNetworkSettings" in cmake
    assert "winhttp" in cmake
    launcher = read("launcher/nautrix_launcher_impl.inc")
    for token in (
        "QueryDoh(",
        "kDnsTypeAAAA",
        "tcp_v6_median_ms",
        "--nautrix-netlog",
        "--nautrix-trace",
        "NAUTRIX_PRECONNECT_ORIGINS",
    ):
        assert token in launcher


def validate_pgo() -> None:
    baseline = read("chromium/args/Release.gn")
    pgo = read("chromium/args/ReleasePGO.gn")
    assert "chrome_pgo_phase = 0" in baseline
    assert "chrome_pgo_phase = 2" in pgo
    assert "is_official_build = true" in pgo
    assert "is_chrome_branded = false" in pgo
    assert "mini_installer" in read("tools/build_chromium.cmd")
    assert "mini_installer" in read("tools/build_chromium_pgo.cmd")

    with tempfile.TemporaryDirectory() as temp:
        gclient = Path(temp) / ".gclient"
        gclient.write_text(
            'solutions = [{"name": "src", "custom_vars": {}, "custom_deps": {}}]\n',
            encoding="utf-8",
        )
        subprocess.run(
            [sys.executable, str(REPO / "tools/enable_pgo_checkout.py"), str(gclient)],
            check=True,
        )
        text = gclient.read_text(encoding="utf-8")
        assert '"checkout_pgo_profiles": True' in text
        subprocess.run(
            [sys.executable, str(REPO / "tools/enable_pgo_checkout.py"), str(gclient)],
            check=True,
        )
        assert gclient.read_text(encoding="utf-8") == text


def validate_automation() -> None:
    full = read(".github/workflows/full-chromium-build.yml")
    assert "nautrix-chromium" in full
    assert "NautrixSetup.exe" in full
    assert "runtime_smoke.ps1" in full

    regression = read(".github/workflows/runtime-regression.yml")
    for token in (
        "runtime_smoke.ps1",
        "chromium_network_probe.ps1",
        "benchmark_navigation.ps1",
        "profile_browser.ps1",
    ):
        assert token in regression, f"runtime regression missing: {token}"

    bootstrap = read("tools/bootstrap_chromium.cmd")
    assert "apply_preconnect.py" in bootstrap


def main() -> int:
    validate_configs()
    validate_native_tools()
    validate_pgo()
    validate_automation()
    print("Nautrix extended DNS/latency/PGO automation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
