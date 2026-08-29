#!/usr/bin/env python3
"""Fast validation for the Nautrix Chromium integration layer."""

from __future__ import annotations

import importlib.util
import os
import re
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_apply_module():
    path = REPO / "tools/apply_nautrix.py"
    spec = importlib.util.spec_from_file_location("apply_nautrix", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load tools/apply_nautrix.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_version() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in (REPO / "chromium/VERSION").read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        key, sep, value = raw.partition("=")
        if not sep:
            raise AssertionError(f"Invalid VERSION line: {raw}")
        values[key] = value

    for required in ("CHANNEL", "VERSION", "REVISION", "MAIN_BRANCH_POSITION"):
        assert values.get(required), f"Missing {required} in chromium/VERSION"
    assert re.fullmatch(r"[0-9a-f]{40}", values["REVISION"]), "REVISION must be a 40-char git SHA"
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", values["VERSION"]), "Invalid Chromium version"
    return values


def _validate_gn_args() -> None:
    args = (REPO / "chromium/args/Release.gn").read_text(encoding="utf-8")
    assert 'target_cpu = "x64"' in args
    assert "is_official_build = true" in args, "End-user Chromium builds must use official optimization level"
    assert "is_official_build = false" not in args
    assert "is_component_build = false" in args
    assert "chrome_pgo_phase = 0" in args, "Baseline build must keep PGO explicit and reproducible"
    assert "is_chrome_branded = false" in args
    assert "is_chrome_branded = true" not in args
    assert "google_default_client_id" not in args.lower()
    assert "google_default_client_secret" not in args.lower()


def _validate_google_browser_credentials_disabled() -> None:
    build = (REPO / "tools/build_chromium.cmd").read_text(encoding="utf-8")
    for variable in (
        "GOOGLE_API_KEY",
        "GOOGLE_DEFAULT_CLIENT_ID",
        "GOOGLE_DEFAULT_CLIENT_SECRET",
    ):
        assert f'set "{variable}="' in build, f"{variable} must be cleared during production build"

    bootstrap = (REPO / "tools/bootstrap_chromium.cmd").read_text(encoding="utf-8")
    for token in (
        "rev-parse --verify HEAD",
        "refs/remotes/origin/main",
        "checkout --force --detach",
        "fetch --no-tags origin %REVISION%",
        ":FetchPinnedRevisionWithRetry",
        "FETCH_ATTEMPT!/5",
        ":SyncChromiumWithRetry",
        "SYNC_ATTEMPT!/4",
        "Partial checkout detected; continuing with resumable gclient sync.",
    ):
        assert token in bootstrap, f"Interrupted/transient Chromium checkout recovery is missing: {token}"


def _validate_dns_and_latency_config() -> None:
    dns = (REPO / "config/dns.ini").read_text(encoding="utf-8")
    latency = (REPO / "config/latency.ini").read_text(encoding="utf-8")
    launcher = (
        (REPO / "launcher/nautrix_launcher.cpp").read_text(encoding="utf-8")
        + (REPO / "launcher/nautrix_launcher_impl.inc").read_text(encoding="utf-8")
    )

    for required in (
        "mode=automatic",
        "samples=",
        "timeout_ms=",
        "minimum_improvement_percent=",
        "priority_hosts=",
        "connect_timeout_ms=",
        "connect_weight=",
        "provider=cloudflare|",
        "provider=google|",
        "provider=quad9|",
    ):
        assert required in dns, f"Missing DNS configuration: {required}"

    assert "enable_happy_eyeballs_v3=" in latency
    for symbol in (
        "BenchmarkProvider",
        "ParseDnsAddresses",
        "ConnectTcp443",
        "settings.priority_hosts",
        "NetworkSignature",
        "NAUTRIX_DNS_MODE",
        "NAUTRIX_DNS_NAMESERVERS",
        "HappyEyeballsV3",
    ):
        assert symbol in launcher, f"Native launcher missing {symbol}"


def _validate_canonical_launcher_and_user_config() -> None:
    obsolete = REPO / "launcher/main.cpp"
    assert not obsolete.exists(), "Obsolete launcher/main.cpp must not shadow the built launcher"

    cmake = (REPO / "launcher/CMakeLists.txt").read_text(encoding="utf-8")
    assert "nautrix_launcher.cpp" in cmake
    assert "main.cpp" not in cmake

    user_config = (REPO / "launcher/user_config.h").read_text(encoding="utf-8")
    for token in (
        'LocalStateDirectory() / L"Config"',
        'L"dns.ini"',
        'L"latency.ini"',
        "copy_options::skip_existing",
    ):
        assert token in user_config, f"Per-user configuration is missing: {token}"

    launcher = (REPO / "launcher/nautrix_launcher.cpp").read_text(encoding="utf-8")
    assert "PrepareUserConfigDirectory(packaged_config_dir)" in launcher
    assert "--nautrix-use-config-dir-directly" in launcher
    assert 'owned.emplace_back(L"--config-dir=" + effective_config_dir.wstring())' in launcher
    assert "BuildInjectedArgs(effective_config_dir / L\"latency.ini\")" in launcher

    settings = (REPO / "launcher/network_settings.cpp").read_text(encoding="utf-8")
    assert "PrepareUserConfigDirectory(result)" in settings
    assert "nautrix_config::LocalStateDirectory()" in settings


def _validate_no_embedded_engine() -> None:
    forbidden = ("Microsoft.Web.WebView2", "#include <WebView2.h>", "CreateCoreWebView2")
    generated_or_external = {".git", ".chromium-work", ".chromium-cache", ".launcher-build", "dist", "artifacts", "__pycache__"}
    source_extensions = {".md", ".py", ".cmd", ".ps1", ".gn", ".ini", ".cpp", ".h", ".yml", ".yaml", ".txt", ""}
    for directory, child_directories, filenames in os.walk(REPO):
        child_directories[:] = [name for name in child_directories if name not in generated_or_external]
        for filename in filenames:
            path = Path(directory, filename)
            if path.suffix.lower() not in source_extensions or path.name == "validate_nautrix.py":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in forbidden:
                assert needle not in text, f"Embedded-engine dependency still present in {path}: {needle}"


def _network_service_fixture() -> str:
    return '''#include "base/strings/string_number_conversions.h"
#include "net/base/address_list.h"
namespace network {
namespace {
NetworkService* g_network_service = nullptr;
}  // namespace

void NetworkService::ConfigureStubHostResolver(
    net::InsecureDnsMode insecure_dns_mode,
    bool happy_eyeballs_v3_enabled,
    net::SecureDnsMode secure_dns_mode,
    const net::DnsOverHttpsConfig& dns_over_https_config,
    bool additional_dns_types_enabled,
    const std::vector<net::IPEndPoint>& fallback_doh_nameservers) {
  // Enable or disable the insecure part of DnsClient. "DnsClient" is the class
  host_resolver_manager_->SetInsecureDnsClientEnabled(
      insecure_dns_mode, additional_dns_types_enabled);

  // Configure DNS over HTTPS.
  net::DnsConfigOverrides overrides;
  overrides.dns_over_https_config = dns_over_https_config;
  overrides.secure_dns_mode = secure_dns_mode;
  overrides.allow_dns_over_https_upgrade = true;
  overrides.fallback_doh_nameservers = fallback_doh_nameservers;
  host_resolver_manager_->SetDnsConfigOverrides(overrides);
}
}  // namespace network
'''


def _validate_product_and_dns_layer() -> None:
    module = _load_apply_module()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        branding = root / "chrome/app/theme/chromium/BRANDING"
        modes = root / "chrome/install_static/chromium_install_modes.h"
        strings = root / "chrome/app/chromium_strings.grd"
        network_service = root / "services/network/network_service.cc"

        branding.parent.mkdir(parents=True)
        modes.parent.mkdir(parents=True)
        strings.parent.mkdir(parents=True, exist_ok=True)
        network_service.parent.mkdir(parents=True, exist_ok=True)

        branding.write_text(
            "COMPANY_FULLNAME=The Chromium Authors\nCOMPANY_SHORTNAME=The Chromium Authors\n"
            "PRODUCT_FULLNAME=Chromium\nPRODUCT_SHORTNAME=Chromium\n"
            "PRODUCT_INSTALLER_FULLNAME=Chromium Installer\nPRODUCT_INSTALLER_SHORTNAME=Chromium Installer\n"
            "COPYRIGHT=Copyright 2017 The Chromium Authors. All rights reserved.\n"
            "MAC_BUNDLE_ID=org.chromium.Chromium\nMAC_CREATOR_CODE=Cr24\n",
            encoding="utf-8",
        )
        modes.write_text(
            'inline constexpr char kSafeBrowsingName[] = "chromium";\n'
            'inline constexpr wchar_t kProductPathName[] = L"Chromium";\n'
            '.base_app_name = L"Chromium",\n.base_app_id = L"Chromium",\n'
            '.browser_prog_id_prefix = L"ChromiumHTM",\nL"Chromium HTML Document",\n'
            '.direct_launch_url_scheme = "chromium",\n'
            '.pdf_prog_id_prefix = L"ChromiumPDF",\nL"Chromium PDF Document",\n'
            'L"{7D2B3E1D-D096-4594-9D8F-A6667F12E0AC}",\n'
            '.toast_activator_clsid = {0x635EFA6F,\n'
            '                                  0x08D6,\n'
            '                                  0x4EC9,\n'
            '                                  {0xBD, 0x14, 0x8A, 0x0F, 0xDE, 0x97, 0x51,\n'
            '                                   0x59}},\n'
            '.elevator_clsid = {0xD133B120,\n'
            '                           0x6DB4,\n'
            '                           0x4D6B,\n'
            '                           {0x8B, 0xFE, 0x83, 0xBF, 0x8C, 0xA1, 0xB1,\n'
            '                            0xB0}},\n'
            '.elevator_iid = {0xbb19a0e5,\n'
            '                         0xc6,\n'
            '                         0x4966,\n'
            '                         {0x94, 0xb2, 0x5a, 0xfe, 0xc6, 0xfe, 0xd9,\n'
            '                          0x3a}},\n'
            '.tracing_service_clsid = {0x83f69367,\n'
            '                                  0x442d,\n'
            '                                  0x447f,\n'
            '                                  {0x8b, 0xcc, 0x0e, 0x3f, 0x97, 0xbe, 0x9c,\n'
            '                                   0xf2}},\n'
            '.tracing_service_iid = {0xa3fd580a,\n'
            '                                0xffd4,\n'
            '                                0x4075,\n'
            '                                {0x91, 0x74, 0x75, 0xd0, 0xb1, 0x99, 0xd3,\n'
            '                                 0xcb}},\n'
            'L"S-1-15-2-3251537155-1984446955-2931258699-841473695-"\n'
            '            L"1938553385-"\n'
            '            L"924012148-",\n',
            encoding="utf-8",
        )
        strings.write_text(
            '<grit><message desc="Chromium product" url="https://chromium.org">'
            'Welcome to Chromium</message></grit>\n',
            encoding="utf-8",
        )
        network_service.write_text(_network_service_fixture(), encoding="utf-8")

        module.apply(root)
        module.apply(root)

        assert "PRODUCT_FULLNAME=Nautrix" in branding.read_text(encoding="utf-8")
        patched_modes = modes.read_text(encoding="utf-8")
        assert 'kSafeBrowsingName[] = "nautrix"' in patched_modes
        assert 'kProductPathName[] = L"Nautrix"' in patched_modes
        assert '.direct_launch_url_scheme = "nautrix"' in patched_modes
        for unique_identity in (
            "A7564E8E-A0AE-4BD2-8312-6E563FCDC031",
            "0xEF7084E3",
            "0x9CDC8406",
            "0xCF9474A8",
            "0x1009CE63",
            "0xC84620C3",
            "S-1-15-2-1678718263-3522501877-2723596049-3126371815-",
        ):
            assert unique_identity in patched_modes
        for chromium_identity in (
            "7D2B3E1D-D096-4594-9D8F-A6667F12E0AC",
            "0x635EFA6F",
            "0xD133B120",
            "0xbb19a0e5",
            "0x83f69367",
            "0xa3fd580a",
            "S-1-15-2-3251537155-1984446955-2931258699-841473695-",
        ):
            assert chromium_identity not in patched_modes

        patched_strings = strings.read_text(encoding="utf-8")
        assert "Welcome to Nautrix" in patched_strings
        assert 'url="https://chromium.org"' in patched_strings

        patched_network = network_service.read_text(encoding="utf-8")
        assert patched_network.count("// NAUTRIX_DNS_OVERRIDE_BEGIN") == 1
        assert "GetVar(kNautrixDnsNameserversEnv)" in patched_network
        assert "overrides->nameservers" in patched_network
        assert "effective_doh_config" in patched_network
        assert "const bool nautrix_dns_active" in patched_network
        assert "if (nautrix_dns_active)" in patched_network
        assert "overrides.allow_dns_over_https_upgrade = false" in patched_network
        assert "SetDnsConfigOverrides(overrides)" in patched_network


def main() -> int:
    values = _parse_version()
    _validate_gn_args()
    _validate_google_browser_credentials_disabled()
    _validate_dns_and_latency_config()
    _validate_canonical_launcher_and_user_config()
    _validate_no_embedded_engine()
    _validate_product_and_dns_layer()
    print(
        f"Nautrix Chromium layer validated: {values['CHANNEL']} "
        f"{values['VERSION']} @ {values['REVISION']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
