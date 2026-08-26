#!/usr/bin/env python3
"""Warm Chromium's spare renderer only for imminent Nautrix trading navigations."""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = "// NAUTRIX_TRADING_WARMUP_BEGIN"


def insert_once(text: str, anchor: str, addition: str, marker: str, path: Path) -> str:
    if marker in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"{path}: anchor not found: {anchor!r}")
    return text.replace(anchor, anchor + addition, 1)


def apply(source_root: Path) -> None:
    path = source_root.resolve() / "chrome/browser/ui/navigator/browser_navigator.cc"
    if not path.is_file():
        raise RuntimeError(f"missing pinned Chromium source: {path}")
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return

    text = insert_once(
        text,
        '#include "base/feature_list.h"\n',
        '#include "base/environment.h"\n',
        '#include "base/environment.h"',
        path,
    )
    text = insert_once(
        text,
        '#include "base/strings/utf_string_conversions.h"\n',
        '#include "base/strings/string_split.h"\n#include "base/strings/string_util.h"\n',
        '#include "base/strings/string_split.h"',
        path,
    )

    helper = r'''

// NAUTRIX_TRADING_WARMUP_BEGIN
bool NautrixNavigatorEnvEnabled(const char* name, bool fallback = true) {
  auto environment = base::Environment::Create();
  const auto raw = environment->GetVar(name);
  if (!raw.has_value()) return fallback;
  return *raw != "0" && !base::EqualsCaseInsensitiveASCII(*raw, "false") &&
         !base::EqualsCaseInsensitiveASCII(*raw, "off");
}

bool NautrixTradingNavigationMatches(const GURL& url) {
  auto environment = base::Environment::Create();
  const std::string mode =
      environment->GetVar("NAUTRIX_TRADING_MODE").value_or("automatic");
  if (base::EqualsCaseInsensitiveASCII(mode, "normal")) return false;
  if (base::EqualsCaseInsensitiveASCII(mode, "aggressive")) return true;
  if (!base::EqualsCaseInsensitiveASCII(mode, "automatic") || !url.has_host())
    return false;

  const auto raw_sites = environment->GetVar("NAUTRIX_TRADING_SITES");
  if (!raw_sites.has_value() || raw_sites->empty()) return false;
  const std::string host = base::ToLowerASCII(url.host());
  for (std::string site :
       base::SplitString(*raw_sites, ",", base::TRIM_WHITESPACE,
                         base::SPLIT_WANT_NONEMPTY)) {
    site = base::ToLowerASCII(site);
    if (host == site ||
        (host.size() > site.size() &&
         host.compare(host.size() - site.size(), site.size(), site) == 0 &&
         host[host.size() - site.size() - 1] == '.')) {
      return true;
    }
  }
  return false;
}
// NAUTRIX_TRADING_WARMUP_END
'''
    text = insert_once(text, "namespace {\n", helper, MARKER, path)

    anchor = '''  if (params->browser && params->browser->IsDeleteScheduled()) {
    return nullptr;
  }
'''
    addition = '''

  // NAUTRIX_TRADING_SPARE_RENDERER_WARMUP
  // Warm one Chromium-managed spare renderer only when a latency-sensitive
  // trading navigation is actually imminent. Chromium remains responsible for
  // spare-process lifetime and reuse; Nautrix never keeps an oversized pool.
  if (NautrixNavigatorEnvEnabled("NAUTRIX_SPARE_RENDERER_WARMUP") &&
      NautrixNavigatorEnvEnabled("NAUTRIX_INTENT_PRECONNECT") &&
      NautrixTradingNavigationMatches(params->url)) {
    content::RenderProcessHost::WarmupSpareRenderProcessHost(
        params->initiating_profile);
  }
'''
    if anchor not in text:
        raise RuntimeError(f"{path}: NavigateImpl warmup anchor not found")
    text = text.replace(anchor, anchor + addition, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_trading_warmup.py <chromium-src>", file=sys.stderr)
        return 2
    try:
        apply(Path(sys.argv[1]))
    except Exception as exc:
        print(f"Nautrix trading warmup patch error: {exc}", file=sys.stderr)
        return 1
    print("Nautrix trading spare-renderer warmup patch applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
