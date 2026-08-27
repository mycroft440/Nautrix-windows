#!/usr/bin/env python3
"""Apply Nautrix priority-origin preconnect to Chromium's existing PreconnectManager path."""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = "// NAUTRIX_PRIORITY_PRECONNECT_BEGIN"


def insert_once(text: str, anchor: str, addition: str, marker: str, path: Path) -> str:
    if marker in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"{path}: anchor not found: {anchor!r}")
    return text.replace(anchor, anchor + addition, 1)


def apply(source_root: Path) -> None:
    path = source_root / "chrome/browser/navigation_predictor/search_engine_preconnector.cc"
    if not path.is_file():
        raise RuntimeError(f"missing Chromium source: {path}")
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return

    text = insert_once(
        text,
        '#include "base/functional/bind.h"\n',
        '#include "base/environment.h"\n#include "base/strings/string_number_conversions.h"\n#include "base/strings/string_split.h"\n#include "base/strings/string_util.h"\n',
        '#include "base/environment.h"',
        path,
    )

    anchor = (
        "  DCHECK(ShouldBeEnabledForOffTheRecord() ||\n"
        "         !browser_context_->IsOffTheRecord());\n"
        "  DCHECK(!timer_.IsRunning());\n"
    )
    injection = r'''

  // NAUTRIX_PRIORITY_PRECONNECT_BEGIN
  // Keep configured low-latency origins warm using Chromium's partitioned
  // PreconnectManager. Trading origins get a longer active keep-alive, while
  // non-trading origins use the bounded background tier. No HTTP request is
  // issued by this warm-up path.
  {
    auto nautrix_environment = base::Environment::Create();
    const auto nautrix_origins =
        nautrix_environment->GetVar("NAUTRIX_PRECONNECT_ORIGINS");
    if (nautrix_origins.has_value() && IsPreconnectEnabled()) {
      const auto trading_sites_value =
          nautrix_environment->GetVar("NAUTRIX_TRADING_SITES");
      const auto trading_sites = base::SplitString(
          trading_sites_value.value_or(""), ",", base::TRIM_WHITESPACE,
          base::SPLIT_WANT_NONEMPTY);
      const auto adaptive_value =
          nautrix_environment->GetVar("NAUTRIX_ADAPTIVE_KEEPALIVE");
      const bool adaptive = !adaptive_value.has_value() ||
          (*adaptive_value != "0" && *adaptive_value != "false" &&
           *adaptive_value != "off");

      auto read_seconds = [&](const char* name, int fallback) {
        int value = fallback;
        if (const auto raw = nautrix_environment->GetVar(name)) {
          base::StringToInt(*raw, &value);
        }
        return value;
      };
      const int default_idle = read_seconds("NAUTRIX_KEEPALIVE_IDLE_SECONDS", 120);
      const int default_ping = read_seconds("NAUTRIX_KEEPALIVE_PING_SECONDS", 25);
      const int active_idle = read_seconds("NAUTRIX_KEEPALIVE_ACTIVE_IDLE_SECONDS", 180);
      const int active_ping = read_seconds("NAUTRIX_KEEPALIVE_ACTIVE_PING_SECONDS", 20);
      const int background_idle = read_seconds("NAUTRIX_KEEPALIVE_BACKGROUND_IDLE_SECONDS", 45);
      const int background_ping = read_seconds("NAUTRIX_KEEPALIVE_BACKGROUND_PING_SECONDS", 0);
      const auto keepalive_enabled =
          nautrix_environment->GetVar("NAUTRIX_KEEPALIVE_ENABLED");
      const bool keepalive_on = !keepalive_enabled.has_value() ||
          (*keepalive_enabled != "0" && *keepalive_enabled != "false" &&
           *keepalive_enabled != "off");

      for (const std::string& raw_url :
           base::SplitString(*nautrix_origins, ",", base::TRIM_WHITESPACE,
                             base::SPLIT_WANT_NONEMPTY)) {
        GURL preconnect_url(raw_url);
        if (!preconnect_url.is_valid() || !preconnect_url.has_host() ||
            (preconnect_url.scheme() != url::kHttpScheme &&
             preconnect_url.scheme() != url::kHttpsScheme)) {
          continue;
        }

        bool trading_origin = false;
        const std::string host = base::ToLowerASCII(preconnect_url.host());
        for (const std::string& site_raw : trading_sites) {
          const std::string site = base::ToLowerASCII(site_raw);
          if (host == site ||
              (host.size() > site.size() && base::EndsWith(host, "." + site,
                                                           base::CompareCase::SENSITIVE))) {
            trading_origin = true;
            break;
          }
        }

        std::optional<net::ConnectionKeepAliveConfig> keepalive_config;
        if (keepalive_on) {
          int idle_seconds = default_idle;
          int ping_seconds = default_ping;
          if (adaptive) {
            idle_seconds = trading_origin ? active_idle : background_idle;
            ping_seconds = trading_origin ? active_ping : background_ping;
          }
          idle_seconds = std::max(15, std::min(idle_seconds, 600));
          ping_seconds = std::max(0, std::min(ping_seconds, idle_seconds - 1));
          net::ConnectionKeepAliveConfig config;
          config.idle_timeout_in_seconds = idle_seconds;
          config.ping_interval_in_seconds = ping_seconds;
          config.enable_connection_keep_alive = true;
          config.quic_connection_options = net::features::kQuicConnectionOptions.Get();
          keepalive_config = std::move(config);
        }

        net::SchemefulSite schemeful_site(preconnect_url);
        auto network_anonymization_key =
            net::NetworkAnonymizationKey::CreateSameSite(
                std::move(schemeful_site));
        GetPreconnectManager().StartPreconnectUrl(
            preconnect_url, /*allow_credentials=*/true,
            network_anonymization_key,
            predictors::kLoadingPredictorPreconnectTrafficAnnotation,
            /*storage_partition_config=*/nullptr,
            network::GetNoOpNetworkRestrictionsId(),
            keepalive_config,
            mojo::PendingRemote<
                network::mojom::ConnectionChangeObserverClient>());
      }
    }
  }
  // NAUTRIX_PRIORITY_PRECONNECT_END
'''
    text = insert_once(text, anchor, injection, MARKER, path)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_preconnect.py <chromium-src>", file=sys.stderr)
        return 2
    try:
        apply(Path(sys.argv[1]).resolve())
    except Exception as exc:
        print(f"Nautrix preconnect patch error: {exc}", file=sys.stderr)
        return 1
    print("Nautrix priority-preconnect patch applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
