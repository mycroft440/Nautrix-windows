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
        "www.binance.com",
        "www.bybit.com",
        "www.okx.com",
        "www.tradingview.com",
        "2606:4700:4700::1111",
        "2001:4860:4860::8888",
        "2620:fe::fe",
        "2a10:50c0::ad1:ff",
    ):
        assert token in dns, f"missing DNS setting: {token}"

    latency = read("config/latency.ini")
    for token in (
        "trading_mode=automatic",
        "enable_happy_eyeballs_v3=1",
        "enable_priority_preconnect=1",
        "enable_quic=1",
        "enable_connection_keepalive=1",
        "keepalive_idle_seconds=120",
        "keepalive_ping_seconds=25",
        "enable_network_priority_boost=1",
        "enable_selective_throttling_bypass=1",
        "enable_intent_preconnect=1",
        "enable_high_resolution_timer=1",
        "enable_freezing_protection=1",
        "enable_trading_process_priority=1",
        "disable_ecoqos_for_trading=1",
        "enable_spare_renderer_warmup=1",
        "optimistic_dns_for_tcp=ab",
        "websocket_over_http3=ab",
        "enable_https_svcb=1",
        "enable_windows_nic_diagnostics=1",
        "metrics_percentiles=p50,p95,p99",
        "trading_sites=",
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

    launcher_impl = read("launcher/nautrix_launcher_impl.inc")
    for token in (
        "QueryDoh(",
        "kDnsTypeAAAA",
        "tcp_v6_median_ms",
        "--nautrix-netlog",
        "--nautrix-trace",
        "NAUTRIX_PRECONNECT_ORIGINS",
    ):
        assert token in launcher_impl

    launcher = read("launcher/nautrix_launcher.cpp")
    for token in (
        "NAUTRIX_TRADING_MODE",
        "NAUTRIX_TRADING_SITES",
        "NAUTRIX_KEEPALIVE_ENABLED",
        "NAUTRIX_NETWORK_PRIORITY_BOOST",
        "NAUTRIX_SELECTIVE_THROTTLING_BYPASS",
        "NAUTRIX_HIGH_RES_TIMER",
        "NAUTRIX_FREEZING_PROTECTION",
        "NAUTRIX_TRADING_PROCESS_PRIORITY",
        "NAUTRIX_DISABLE_ECOQOS",
        "NAUTRIX_SPARE_RENDERER_WARMUP",
        "OptimisticDnsForTcp",
        "EnableWebsocketsOverHttp3",
        "StableAbBucket",
    ):
        assert token in launcher, f"missing launcher latency token: {token}"
    assert "PreferWarmRendererProcess" not in launcher
    assert "SpareRendererForSitePerProcess" not in launcher


def validate_trading_latency_tools() -> None:
    patch = read("tools/apply_trading_latency.py")
    for token in (
        "url_request_->SetPriority(net::HIGHEST)",
        "NAUTRIX_TRADING_MODE",
        "NAUTRIX_TRADING_SITES",
        "NAUTRIX_SELECTIVE_THROTTLING_BYPASS",
        "NAUTRIX_HIGH_RES_TIMER",
        "base::Time::EnableHighResolutionTimer(true)",
        "base::Time::ActivateHighResolutionTimer(true)",
        "base::Time::ActivateHighResolutionTimer(false)",
        "return ThrottlingType::kNone",
        "return TaskPriority::kHighPriority",
    ):
        assert token in patch, f"missing trading patch token: {token}"

    priority = read("tools/apply_trading_priority.py")
    for token in (
        "NAUTRIX_FREEZING_PROTECTION",
        "NAUTRIX_TRADING_PROCESS_PRIORITY",
        "NAUTRIX_DISABLE_ECOQOS",
        "GetNautrixLifecycleProtectedSites",
        "GetNautrixForegroundPrioritySites",
        "kManagedTabDiscardingExceptions",
        "kForceForegroundPriorityForUrls",
    ):
        assert token in priority, f"missing trading priority token: {token}"

    warmup = read("tools/apply_trading_warmup.py")
    for token in (
        "NAUTRIX_SPARE_RENDERER_WARMUP",
        "NAUTRIX_INTENT_PRECONNECT",
        "SpareRenderProcessHostManager::Get().WarmupSpare",
        "spare_render_process_host_manager.h",
    ):
        assert token in warmup, f"missing trading warmup token: {token}"
    assert "WarmupSpareRenderProcessHost" not in warmup

    preconnect = read("tools/apply_preconnect.py")
    for token in (
        "ConnectionKeepAliveConfig",
        "NAUTRIX_KEEPALIVE_IDLE_SECONDS",
        "NAUTRIX_KEEPALIVE_PING_SECONDS",
        "enable_connection_keep_alive = true",
    ):
        assert token in preconnect, f"missing keepalive token: {token}"

    mode_switch = read("tools/set_trading_mode.ps1")
    for token in ("automatic", "normal", "aggressive", "trading_mode=$Mode"):
        assert token in mode_switch, f"missing trading-mode switch token: {token}"

    nic = read("tools/windows_nic_diagnostics.ps1")
    for token in ("Get-NetAdapter", "Get-NetAdapterRss", "Get-NetAdapterRsc", "Read-only"):
        assert token in nic, f"missing NIC diagnostic token: {token}"
    assert "Set-NetAdapter" not in nic, "NIC diagnostics must remain read-only"

    benchmark = read("tools/benchmark_navigation.ps1")
    for token in ("p50_ms", "p95_ms", "p99_ms", "Get-Percentile"):
        assert token in benchmark, f"missing tail-latency metric: {token}"


def validate_pgo() -> None:
    baseline = read("chromium/args/Release.gn")
    pgo = read("chromium/args/ReleasePGO.gn")
    training = read("chromium/args/ReleasePGOTraining.gn")
    custom_build = read("tools/build_chromium_pgo_custom.cmd")
    profile = read("tools/generate_nautrix_pgo_profile.cmd")

    assert "chrome_pgo_phase = 0" in baseline
    assert "chrome_pgo_phase = 2" in pgo
    assert "is_official_build = true" in pgo
    assert "is_chrome_branded = false" in pgo
    assert "chrome_pgo_phase = 1" in training
    assert "is_official_build = true" in training
    assert "tools\\pgo\\generate_profile.py" in profile
    assert "profile.profdata" in profile
    assert "pgo_data_path" in custom_build
    assert "profile.profdata" in custom_build
    assert "chrome_pgo_phase = 2" in custom_build
    assert "mini_installer" in custom_build
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
    assert "runtime_smoke.ps1" in full
    assert "package_test_installer.ps1" in full
    assert "verify_test_package.ps1" in full
    assert "install_test_package.ps1" in full
    assert "UninstallAfterTest" in full

    package = read("tools/package_test_installer.ps1")
    for token in (
        "mini_installer.exe",
        "chrome.exe",
        "NautrixLauncher.exe",
        "NautrixNetworkSettings.exe",
        "install_command = 'NautrixSetup.exe'",
        "automated_install_test = 'Install-Nautrix-Test.cmd'",
        "Install-Nautrix-Test.ps1",
        "Install-Nautrix-Test.cmd",
        "Start-Nautrix.cmd",
        "MANIFEST.json",
        "SHA256SUMS.txt",
        "GetFullPath($OutputDir)",
        "Verify-Nautrix-TestPackage.ps1",
        "Refusing to overwrite",
    ):
        assert token in package, f"test package missing: {token}"
    assert "initial_preferences.json" not in package, (
        "native installer package must not depend on post-install shortcut suppression"
    )

    verify = read("tools/verify_test_package.ps1")
    for token in (
        "NautrixSetup.exe",
        "Get-FileHash",
        "Checksum mismatch",
        "Size mismatch",
        "Duplicate payload manifest entry",
        "Package path must be relative",
        "MANIFEST.json",
        "NautrixLauncher.exe",
        "Install-Nautrix-Test.ps1",
        "Assert-InstalledPayload",
        "Get-NautrixProgIdCommands",
        "--single-argument",
        "must not copy payload after setup",
    ):
        assert token in verify, f"test package verifier missing: {token}"

    install = read("tools/install_test_package.ps1")
    for token in (
        "--do-not-launch-chrome",
        "NautrixLauncher.exe",
        "NautrixNetworkSettings.exe",
        "Assert-InstalledPayload",
        "Assert-NativeShortcuts",
        "Assert-ProgIdRouting",
        "Get-NautrixProgIdCommands",
        "NautrixHTM",
        "--single-argument",
        "UninstallAfterTest",
        "--force-uninstall",
        "Wait-NautrixUninstalled",
        "finally",
        "Stop-NautrixProcesses",
        "Test-package verification failed before installation",
        "Native installer did not deploy required Nautrix payload",
    ):
        assert token in install, f"native installer test missing: {token}"
    assert "--installerdata=" not in install, (
        "native installer test must execute NautrixSetup.exe without installerdata"
    )
    assert "Copy-Item" not in install, (
        "native installer test must not repair a missing installer payload"
    )

    runner = read("tools/start_installed_nautrix.cmd")
    assert "NautrixLauncher.exe" in runner
    assert "--browser=" in runner

    install_cmd = read("tools/install_test_package.cmd")
    assert "Verify-Nautrix-TestPackage.ps1" in install_cmd

    footprint = read("tools/measure_launcher_footprint.ps1")
    assert "Total native-helper size" in footprint

    subprocess.run(
        [sys.executable, str(REPO / "tools/validate_test_package.py")],
        check=True,
    )

    regression = read(".github/workflows/runtime-regression.yml")
    for token in (
        "runtime_smoke.ps1",
        "chromium_network_probe.ps1",
        "benchmark_navigation.ps1",
        "profile_browser.ps1",
    ):
        assert token in regression, f"runtime regression missing: {token}"

    bootstrap = read("tools/bootstrap_chromium.cmd")
    for token in (
        "apply_installer_integration.py",
        "apply_preconnect.py",
        "apply_trading_priority.py",
        "apply_trading_latency.py",
        "apply_trading_warmup.py",
    ):
        assert token in bootstrap, f"bootstrap missing: {token}"


def main() -> int:
    validate_configs()
    validate_native_tools()
    validate_trading_latency_tools()
    validate_pgo()
    validate_automation()
    print("Nautrix extended DNS/trading-latency/PGO/installer automation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
