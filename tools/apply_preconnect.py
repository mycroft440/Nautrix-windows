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
        '#include "base/environment.h"\n#include "base/strings/string_number_conversions.h"\n#include "base/strings/string_split.h"\n',
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
  // Keep configured low-latency origins warm using Chromium's own partitioned
  // PreconnectManager path. No HTTP request is issued here. The keep-alive is
  // bounded and can be disabled from config/latency.ini via the launcher.
  {
    auto nautrix_environment = base::Environment::Create();
    const auto nautrix_origins =
        nautrix_environment->GetVar("NAUTRIX_PRECONNECT_ORIGINS");
    if (nautrix_origins.has_value() && IsPreconnectEnabled()) {
      std::optional<net::ConnectionKeepAliveConfig> keepalive_config;
      const auto keepalive_enabled =
          nautrix_environment->GetVar("NAUTRIX_KEEPALIVE_ENABLED");
      if (!keepalive_enabled.has_value() ||
          (*keepalive_enabled != "0" && *keepalive_enabled != "false" &&
           *keepalive_enabled != "off")) {
        int idle_seconds = 120;
        int ping_seconds = 25;
        if (const auto value = nautrix_environment->GetVar(
                "NAUTRIX_KEEPALIVE_IDLE_SECONDS")) {
          base::StringToInt(*value, &idle_seconds);
        }
        if (const auto value = nautrix_environment->GetVar(
                "NAUTRIX_KEEPALIVE_PING_SECONDS")) {
          base::StringToInt(*value, &ping_seconds);
        }
        idle_seconds = std::max(30, std::min(idle_seconds, 600));
        ping_seconds = std::max(0, std::min(ping_seconds, idle_seconds - 1));
        net::ConnectionKeepAliveConfig config;
        config.idle_timeout_in_seconds = idle_seconds;
        config.ping_interval_in_seconds = ping_seconds;
        config.enable_connection_keep_alive = true;
        config.quic_connection_options = net::features::kQuicConnectionOptions.Get();
        keepalive_config = std::move(config);
      }

      for (const std::string& raw_url :
           base::SplitString(*nautrix_origins, ",", base::TRIM_WHITESPACE,
                             base::SPLIT_WANT_NONEMPTY)) {
        GURL preconnect_url(raw_url);
        if (!preconnect_url.is_valid() || !preconnect_url.has_host() ||
            (preconnect_url.scheme() != url::kHttpScheme &&
             preconnect_url.scheme() != url::kHttpsScheme)) {
          continue;
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
