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
    ]

    for old, new in replacements:
        if old.startswith(".direct_launch_url_scheme") and old not in text and new not in text:
            continue
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
