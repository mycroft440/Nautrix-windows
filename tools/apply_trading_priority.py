#!/usr/bin/env python3
"""Apply per-site trading priority/discard protection to Chromium."""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = "// NAUTRIX_TRADING_PRIORITY_BEGIN"


def _insert_once(text: str, anchor: str, addition: str, marker: str, path: Path) -> str:
    if marker in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"{path}: anchor not found: {anchor!r}")
    return text.replace(anchor, anchor + addition, 1)


def apply(source_root: Path) -> None:
    path = source_root / "components/performance_manager/user_tuning/prefs.cc"
    if not path.is_file():
        raise RuntimeError(f"missing Chromium source: {path}")

    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return

    text = _insert_once(
        text,
        '#include "base/json/values_util.h"\n',
        '#include "base/environment.h"\n#include "base/strings/string_split.h"\n#include "base/strings/string_util.h"\n',
        '#include "base/environment.h"',
        path,
    )

    helper = r'''

// NAUTRIX_TRADING_PRIORITY_BEGIN
namespace {

base::Value::List GetNautrixTradingSites() {
  base::Value::List sites;
  auto environment = base::Environment::Create();
  const std::string mode =
      environment->GetVar("NAUTRIX_TRADING_MODE").value_or("automatic");
  if (base::EqualsCaseInsensitiveASCII(mode, "normal")) {
    return sites;
  }

  const auto raw_sites = environment->GetVar("NAUTRIX_TRADING_SITES");
  if (!raw_sites.has_value() || raw_sites->empty()) {
    return sites;
  }

  for (std::string site :
       base::SplitString(*raw_sites, ",", base::TRIM_WHITESPACE,
                         base::SPLIT_WANT_NONEMPTY)) {
    site = base::ToLowerASCII(site);
    if (!site.empty()) {
      sites.Append(std::move(site));
    }
  }
  return sites;
}

}  // namespace
// NAUTRIX_TRADING_PRIORITY_END
'''
    text = _insert_once(
        text,
        "namespace performance_manager::user_tuning::prefs {\n",
        helper,
        MARKER,
        path,
    )

    old = (
        "  registry->RegisterListPref(kManagedTabDiscardingExceptions);\n"
        "  registry->RegisterListPref(kForceForegroundPriorityForUrls);\n"
    )
    new = (
        "  registry->RegisterListPref(kManagedTabDiscardingExceptions,\n"
        "                             GetNautrixTradingSites());\n"
        "  registry->RegisterListPref(kForceForegroundPriorityForUrls,\n"
        "                             GetNautrixTradingSites());\n"
    )
    if old not in text:
        raise RuntimeError(f"{path}: trading preference registration anchor not found")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_trading_priority.py <chromium-src>", file=sys.stderr)
        return 2
    try:
        apply(Path(sys.argv[1]).resolve())
    except Exception as exc:
        print(f"Nautrix trading-priority patch error: {exc}", file=sys.stderr)
        return 1
    print("Nautrix trading-site priority/discard patch applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
