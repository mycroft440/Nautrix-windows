#!/usr/bin/env python3
"""Apply the Nautrix product/network layer to a pinned Chromium checkout."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _replace_required(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        return text.replace(old, new)
    if new in text:
        return text
    raise RuntimeError(f"{label}: expected upstream pattern not found: {old!r}")


def _insert_once(text: str, anchor: str, addition: str, marker: str, label: str) -> str:
    if marker in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"{label}: insertion anchor not found: {anchor!r}")
    return text.replace(anchor, anchor + addition, 1)


def _patch_branding(source_root: Path) -> None:
    path = source_root / "chrome/app/theme/chromium/BRANDING"
    text = path.read_text(encoding="utf-8")
    replacements = {
        "COMPANY_FULLNAME": "Nautrix",
        "COMPANY_SHORTNAME": "Nautrix",
        "PRODUCT_FULLNAME": "Nautrix",
        "PRODUCT_SHORTNAME": "Nautrix",
        "PRODUCT_INSTALLER_FULLNAME": "Nautrix Installer",
        "PRODUCT_INSTALLER_SHORTNAME": "Nautrix Installer",
        "COPYRIGHT": "Copyright 2026 Nautrix contributors.",
        "MAC_BUNDLE_ID": "app.nautrix.browser",
    }

    for key, value in replacements.items():
        pattern = re.compile(rf"(?m)^{re.escape(key)}=.*$")
        if not pattern.search(text):
            raise RuntimeError(f"{path}: missing branding key {key}")
        text = pattern.sub(f"{key}={value}", text)

    path.write_text(text, encoding="utf-8", newline="\n")


def _patch_windows_install_identity(source_root: Path) -> None:
    path = source_root / "chrome/install_static/chromium_install_modes.h"
    text = path.read_text(encoding="utf-8")

    replacements = [
        ('inline constexpr char kSafeBrowsingName[] = "chromium";',
         'inline constexpr char kSafeBrowsingName[] = "nautrix";'),
        ('inline constexpr wchar_t kProductPathName[] = L"Chromium";',
         'inline constexpr wchar_t kProductPathName[] = L"Nautrix";'),
        ('.base_app_name = L"Chromium",', '.base_app_name = L"Nautrix",'),
        ('.base_app_id = L"Chromium",', '.base_app_id = L"Nautrix",'),
        ('.browser_prog_id_prefix = L"ChromiumHTM",',
         '.browser_prog_id_prefix = L"NautrixHTM",'),
        ('L"Chromium HTML Document",', 'L"Nautrix HTML Document",'),
        ('.direct_launch_url_scheme = "chromium",',
         '.direct_launch_url_scheme = "nautrix",'),
        ('.pdf_prog_id_prefix = L"ChromiumPDF",',
         '.pdf_prog_id_prefix = L"NautrixPDF",'),
        ('L"Chromium PDF Document",', 'L"Nautrix PDF Document",'),
        ('L"{7D2B3E1D-D096-4594-9D8F-A6667F12E0AC}",',
         'L"{A7564E8E-A0AE-4BD2-8312-6E563FCDC031}",'),
    ]

    for old, new in replacements:
        if old.startswith(".direct_launch_url_scheme") and old not in text and new not in text:
            continue
        text = _replace_required(text, old, new, str(path))

    identity_replacements = [
        (
            """.toast_activator_clsid = {0x635EFA6F,
                                  0x08D6,
                                  0x4EC9,
                                  {0xBD, 0x14, 0x8A, 0x0F, 0xDE, 0x97, 0x51,
                                   0x59}},""",
            """.toast_activator_clsid = {0xEF7084E3,
                                  0x562E,
                                  0x484B,
                                  {0x9C, 0x01, 0x90, 0x0B, 0x7B, 0xA8, 0x2E,
                                   0x6E}},""",
        ),
        (
            """.elevator_clsid = {0xD133B120,
                           0x6DB4,
                           0x4D6B,
                           {0x8B, 0xFE, 0x83, 0xBF, 0x8C, 0xA1, 0xB1,
                            0xB0}},""",
            """.elevator_clsid = {0x9CDC8406,
                           0x56F7,
                           0x497D,
                           {0xAF, 0x00, 0x7B, 0xCC, 0x23, 0x25, 0x75,
                            0x08}},""",
        ),
        (
            """.elevator_iid = {0xbb19a0e5,
                         0xc6,
                         0x4966,
                         {0x94, 0xb2, 0x5a, 0xfe, 0xc6, 0xfe, 0xd9,
                          0x3a}},""",
            """.elevator_iid = {0xCF9474A8,
                         0xFB77,
                         0x4679,
                         {0xB3, 0x9F, 0x51, 0x22, 0x21, 0x7E, 0xB4,
                          0xB5}},""",
        ),
        (
            """.tracing_service_clsid = {0x83f69367,
                                  0x442d,
                                  0x447f,
                                  {0x8b, 0xcc, 0x0e, 0x3f, 0x97, 0xbe, 0x9c,
                                   0xf2}},""",
            """.tracing_service_clsid = {0x1009CE63,
                                  0x7DB2,
                                  0x44F0,
                                  {0x8E, 0x7D, 0x64, 0x98, 0x2A, 0xD3, 0xD4,
                                   0x14}},""",
        ),
        (
            """.tracing_service_iid = {0xa3fd580a,
                                0xffd4,
                                0x4075,
                                {0x91, 0x74, 0x75, 0xd0, 0xb1, 0x99, 0xd3,
                                 0xcb}},""",
            """.tracing_service_iid = {0xC84620C3,
                                0x4A0A,
                                0x4779,
                                {0xB6, 0x02, 0x53, 0xD2, 0xFA, 0x0E, 0xC3,
                                 0x52}},""",
        ),
        (
            """L"S-1-15-2-3251537155-1984446955-2931258699-841473695-"
            L"1938553385-"
            L"924012148-",""",
            """L"S-1-15-2-1678718263-3522501877-2723596049-3126371815-"
            L"1400289899-"
            L"912135048-",""",
        ),
    ]

    for old, new in identity_replacements:
        text = _replace_required(text, old, new, str(path))

    path.write_text(text, encoding="utf-8", newline="\n")


def _patch_visible_product_strings(source_root: Path) -> None:
    path = source_root / "chrome/app/chromium_strings.grd"
    text = path.read_text(encoding="utf-8")

    def repl(match: re.Match[str]) -> str:
        visible = match.group(1).replace("Chromium", "Nautrix")
        return ">" + visible + "<"

    patched = re.sub(r">([^<>]*)<", repl, text)
    path.write_text(patched, encoding="utf-8", newline="\n")


def _patch_network_service_dns(source_root: Path) -> None:
    """Add Nautrix browser-local DNS overrides to Chromium's Network Service."""

    path = source_root / "services/network/network_service.cc"
    text = path.read_text(encoding="utf-8")

    if "// NAUTRIX_DNS_OVERRIDE_BEGIN" in text:
        return

    text = _insert_once(
        text,
        '#include "base/strings/string_number_conversions.h"\n',
        '#include "base/strings/string_split.h"\n',
        '#include "base/strings/string_split.h"',
        str(path),
    )
    text = _insert_once(
        text,
        '#include "net/base/address_list.h"\n',
        '#include "net/base/ip_address.h"\n#include "net/base/ip_endpoint.h"\n',
        '#include "net/base/ip_address.h"',
        str(path),
    )

    helper = r"""
// NAUTRIX_DNS_OVERRIDE_BEGIN
constexpr char kNautrixDnsModeEnv[] = "NAUTRIX_DNS_MODE";
constexpr char kNautrixDnsNameserversEnv[] = "NAUTRIX_DNS_NAMESERVERS";
constexpr char kNautrixDohTemplatesEnv[] = "NAUTRIX_DOH_TEMPLATES";

std::optional<std::vector<net::IPEndPoint>> GetNautrixDnsNameservers(
    base::Environment* environment) {
  const auto raw = environment->GetVar(kNautrixDnsNameserversEnv);
  if (!raw.has_value() || raw->empty()) {
    return std::nullopt;
  }

  std::vector<net::IPEndPoint> nameservers;
  for (const std::string& literal :
       base::SplitString(*raw, ",", base::TRIM_WHITESPACE,
                         base::SPLIT_WANT_NONEMPTY)) {
    net::IPAddress address;
    if (!address.AssignFromIPLiteral(literal)) {
      LOG(WARNING) << "Nautrix ignored invalid DNS nameserver: " << literal;
      return std::nullopt;
    }
    nameservers.emplace_back(std::move(address), 53);
  }

  if (nameservers.empty()) {
    return std::nullopt;
  }
  return nameservers;
}

bool ApplyNautrixDnsEnvironment(
    net::InsecureDnsMode* insecure_dns_mode,
    net::SecureDnsMode* secure_dns_mode,
    net::DnsOverHttpsConfig* doh_config,
    net::DnsConfigOverrides* overrides) {
  auto environment = base::Environment::Create();
  const auto mode = environment->GetVar(kNautrixDnsModeEnv);
  if (!mode.has_value() || mode->empty()) {
    return false;
  }

  auto nameservers = GetNautrixDnsNameservers(environment.get());
  if (nameservers.has_value()) {
    overrides->nameservers = *nameservers;
  }

  if (*mode == "plain") {
    if (!nameservers.has_value()) {
      LOG(WARNING) << "Nautrix plain DNS requested without valid nameservers.";
      return false;
    }
    *insecure_dns_mode = net::InsecureDnsMode::kEnabledBuiltIn;
    *secure_dns_mode = net::SecureDnsMode::kOff;
    return true;
  }

  if (*mode != "secure" && *mode != "automatic") {
    LOG(WARNING) << "Nautrix ignored unknown DNS mode: " << *mode;
    return false;
  }

  const auto raw_doh = environment->GetVar(kNautrixDohTemplatesEnv);
  if (!raw_doh.has_value() || raw_doh->empty()) {
    LOG(WARNING) << "Nautrix secure DNS requested without a DoH template.";
    return false;
  }

  net::DnsOverHttpsConfig parsed =
      net::DnsOverHttpsConfig::FromStringLax(*raw_doh);
  if (parsed.servers().empty()) {
    LOG(WARNING) << "Nautrix ignored invalid DoH configuration.";
    return false;
  }

  *doh_config = std::move(parsed);
  *secure_dns_mode = *mode == "secure" ? net::SecureDnsMode::kSecure
                                       : net::SecureDnsMode::kAutomatic;
  if (nameservers.has_value()) {
    *insecure_dns_mode = net::InsecureDnsMode::kEnabledBuiltIn;
  }
  return true;
}
// NAUTRIX_DNS_OVERRIDE_END

"""
    text = _insert_once(
        text,
        "NetworkService* g_network_service = nullptr;\n",
        helper,
        "// NAUTRIX_DNS_OVERRIDE_BEGIN",
        str(path),
    )

    configure_anchor = (
        '  // Enable or disable the insecure part of DnsClient. "DnsClient" is the class\n'
    )
    configure_injection = r"""  net::SecureDnsMode effective_secure_dns_mode = secure_dns_mode;
  net::DnsOverHttpsConfig effective_doh_config = dns_over_https_config;
  net::DnsConfigOverrides nautrix_dns_overrides;
  const bool nautrix_dns_active =
      ApplyNautrixDnsEnvironment(&insecure_dns_mode,
                                 &effective_secure_dns_mode,
                                 &effective_doh_config,
                                 &nautrix_dns_overrides);

"""
    text = _insert_once(
        text,
        configure_anchor,
        configure_injection,
        "effective_secure_dns_mode = secure_dns_mode",
        str(path),
    )

    old_overrides = """  net::DnsConfigOverrides overrides;
  overrides.dns_over_https_config = dns_over_https_config;
  overrides.secure_dns_mode = secure_dns_mode;
"""
    new_overrides = """  net::DnsConfigOverrides overrides = std::move(nautrix_dns_overrides);
  overrides.dns_over_https_config = effective_doh_config;
  overrides.secure_dns_mode = effective_secure_dns_mode;
"""
    text = _replace_required(text, old_overrides, new_overrides, str(path))
    text = _insert_once(
        text,
        "  overrides.fallback_doh_nameservers = fallback_doh_nameservers;\n",
        "  if (nautrix_dns_active) {\n"
        "    overrides.allow_dns_over_https_upgrade = false;\n"
        "  }\n",
        "if (nautrix_dns_active)",
        str(path),
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def apply(source_root: Path) -> None:
    source_root = source_root.resolve()
    required = [
        source_root / "chrome/app/theme/chromium/BRANDING",
        source_root / "chrome/install_static/chromium_install_modes.h",
        source_root / "chrome/app/chromium_strings.grd",
        source_root / "services/network/network_service.cc",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Not a complete Chromium source checkout; missing:\n  " +
            "\n  ".join(missing)
        )

    _patch_branding(source_root)
    _patch_windows_install_identity(source_root)
    _patch_visible_product_strings(source_root)
    _patch_network_service_dns(source_root)

    marker = source_root / ".nautrix-product-layer"
    marker.write_text(
        "Nautrix downstream product/network layer applied.\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_nautrix.py <chromium-src>", file=sys.stderr)
        return 2
    try:
        apply(Path(sys.argv[1]))
    except Exception as exc:
        print(f"Nautrix product-layer error: {exc}", file=sys.stderr)
        return 1

    print("Nautrix product/network layer applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
