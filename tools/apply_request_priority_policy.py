#!/usr/bin/env python3
"""Refine Nautrix trading request priority by resource class."""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = "// NAUTRIX_CRITICAL_REQUEST_POLICY_BEGIN"


def apply(source_root: Path) -> None:
    path = source_root / "services/network/url_loader.cc"
    if not path.is_file():
        raise RuntimeError(f"missing Chromium source: {path}")
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    if "// NAUTRIX_TRADING_NETWORK_BEGIN" not in text:
        raise RuntimeError("apply_trading_latency.py must run before request priority policy")

    helper_anchor = "// NAUTRIX_TRADING_NETWORK_END\n"
    helper = r'''

// NAUTRIX_CRITICAL_REQUEST_POLICY_BEGIN
bool NautrixCriticalTradingRequest(const net::URLRequest& request) {
  auto environment = base::Environment::Create();
  const std::string policy =
      environment->GetVar("NAUTRIX_REQUEST_PRIORITY_POLICY").value_or("critical");
  if (base::EqualsCaseInsensitiveASCII(policy, "off") || policy == "0") {
    return false;
  }
  if (base::EqualsCaseInsensitiveASCII(policy, "all")) {
    return true;
  }

  // Writes and command-like requests are latency-sensitive. They retain normal
  // HTTP semantics; this only changes scheduler priority.
  const std::string method = base::ToUpperASCII(request.method());
  if (method != "GET" && method != "HEAD") return true;

  const GURL& url = request.url();
  const std::string path = base::ToLowerASCII(url.PathForRequest());
  static constexpr const char* kStaticSuffixes[] = {
      ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg",
      ".ico", ".css", ".woff", ".woff2", ".ttf", ".otf", ".mp4",
      ".webm", ".mp3", ".wav"};
  for (const char* suffix : kStaticSuffixes) {
    if (base::EndsWith(path, suffix, base::CompareCase::SENSITIVE)) return false;
  }

  static constexpr const char* kCriticalTokens[] = {
      "/api", "/ws", "websocket", "socket", "stream", "order",
      "orderbook", "depth", "ticker", "trade", "market", "kline",
      "candles", "chart", "quote", "price", "bookticker", "aggtrade"};
  for (const char* token : kCriticalTokens) {
    if (path.find(token) != std::string::npos) return true;
  }

  // Main document/root navigation stays responsive; secondary static and
  // unclassified subresources keep Chromium's native scheduler priority.
  return url.path().empty() || url.path() == "/";
}
// NAUTRIX_CRITICAL_REQUEST_POLICY_END
'''
    if helper_anchor not in text:
        raise RuntimeError(f"{path}: trading network helper anchor not found")
    text = text.replace(helper_anchor, helper_anchor + helper, 1)

    old = '''  if (url_request_ &&
      NautrixEnvEnabled("NAUTRIX_NETWORK_PRIORITY_BOOST") &&
      NautrixTradingHostMatches(url_request_->url())) {
    url_request_->SetPriority(net::HIGHEST);
  }
'''
    new = '''  if (url_request_ &&
      NautrixEnvEnabled("NAUTRIX_NETWORK_PRIORITY_BOOST") &&
      NautrixTradingHostMatches(url_request_->url()) &&
      NautrixCriticalTradingRequest(*url_request_)) {
    url_request_->SetPriority(net::HIGHEST);
  }
'''
    if old not in text:
        raise RuntimeError(f"{path}: trading priority block not found")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_request_priority_policy.py <chromium-src>", file=sys.stderr)
        return 2
    try:
        apply(Path(sys.argv[1]).resolve())
    except Exception as exc:
        print(f"Nautrix request-priority patch error: {exc}", file=sys.stderr)
        return 1
    print("Nautrix critical request-priority policy applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
