#!/usr/bin/env python3
"""Apply Nautrix per-site low-latency scheduling/network policy to pinned Chromium."""

from __future__ import annotations

import sys
from pathlib import Path

NETWORK_MARKER = "// NAUTRIX_TRADING_NETWORK_BEGIN"
BLINK_MARKER = "// NAUTRIX_TRADING_SCHEDULER_BEGIN"
FIELD_MARKER = "// NAUTRIX_TRADING_SCHEDULER_FIELD"


def insert_once(text: str, anchor: str, addition: str, marker: str, path: Path) -> str:
    if marker in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"{path}: anchor not found: {anchor!r}")
    return text.replace(anchor, anchor + addition, 1)


def replace_once(text: str, old: str, new: str, marker: str, path: Path) -> str:
    if marker in text:
        return text
    if old not in text:
        raise RuntimeError(f"{path}: expected pattern not found")
    return text.replace(old, new, 1)


def patch_network(source_root: Path) -> None:
    path = source_root / "services/network/url_loader.cc"
    text = path.read_text(encoding="utf-8")
    if NETWORK_MARKER in text:
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
        '#include "base/strings/strcat.h"\n',
        '#include "base/strings/string_split.h"\n#include "base/strings/string_util.h"\n',
        '#include "base/strings/string_split.h"',
        path,
    )

    helper = r'''

// NAUTRIX_TRADING_NETWORK_BEGIN
bool NautrixEnvEnabled(const char* name, bool fallback = true) {
  auto environment = base::Environment::Create();
  const auto raw = environment->GetVar(name);
  if (!raw.has_value()) return fallback;
  return *raw != "0" && !base::EqualsCaseInsensitiveASCII(*raw, "false") &&
         !base::EqualsCaseInsensitiveASCII(*raw, "off");
}

bool NautrixTradingHostMatches(const GURL& url) {
  auto environment = base::Environment::Create();
  const std::string mode =
      environment->GetVar("NAUTRIX_TRADING_MODE").value_or("automatic");
  if (base::EqualsCaseInsensitiveASCII(mode, "normal")) return false;
  if (base::EqualsCaseInsensitiveASCII(mode, "aggressive")) return true;
  if (!base::EqualsCaseInsensitiveASCII(mode, "automatic")) return false;

  const auto raw_sites = environment->GetVar("NAUTRIX_TRADING_SITES");
  if (!raw_sites.has_value() || raw_sites->empty() || !url.has_host()) {
    return false;
  }
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
// NAUTRIX_TRADING_NETWORK_END
'''
    text = insert_once(
        text,
        'BASE_FEATURE(kDelayedCookieNotification, base::FEATURE_DISABLED_BY_DEFAULT);\n',
        helper,
        NETWORK_MARKER,
        path,
    )

    old = '''void URLLoader::ScheduleStart() {
  TRACE_EVENT("loading", "URLLoader::ScheduleStart",
              net::NetLogWithSourceToFlow(url_request_->net_log()));
  bool defer = false;
'''
    new = '''void URLLoader::ScheduleStart() {
  TRACE_EVENT("loading", "URLLoader::ScheduleStart",
              net::NetLogWithSourceToFlow(url_request_->net_log()));
  // NAUTRIX_TRADING_NETWORK_PRIORITY
  // Only latency-critical trading origins are boosted in automatic mode.
  // Normal mode preserves upstream priorities; aggressive mode applies the
  // policy globally. The ResourceScheduler can still enforce correctness.
  if (url_request_ &&
      NautrixEnvEnabled("NAUTRIX_NETWORK_PRIORITY_BOOST") &&
      NautrixTradingHostMatches(url_request_->url())) {
    url_request_->SetPriority(net::HIGHEST);
  }
  bool defer = false;
'''
    if old not in text:
        raise RuntimeError(f"{path}: ScheduleStart anchor not found")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_blink_header(source_root: Path) -> None:
    path = source_root / "third_party/blink/renderer/platform/scheduler/main_thread/frame_scheduler_impl.h"
    text = path.read_text(encoding="utf-8")
    if FIELD_MARKER in text:
        return
    anchor = "  bool is_ad_frame_ = false;\n"
    addition = (
        "\n  // NAUTRIX_TRADING_SCHEDULER_FIELD\n"
        "  // Cached per-document decision; refreshed by TraceUrlChange().\n"
        "  bool nautrix_low_latency_page_ = false;\n"
    )
    text = insert_once(text, anchor, addition, FIELD_MARKER, path)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_blink_impl(source_root: Path) -> None:
    path = source_root / "third_party/blink/renderer/platform/scheduler/main_thread/frame_scheduler_impl.cc"
    text = path.read_text(encoding="utf-8")
    if BLINK_MARKER in text:
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
        '#include "base/metrics/histogram_functions.h"\n',
        '#include "base/strings/string_split.h"\n#include "base/strings/string_util.h"\n',
        '#include "base/strings/string_split.h"',
        path,
    )

    helper = r'''

// NAUTRIX_TRADING_SCHEDULER_BEGIN
bool NautrixSchedulerEnvEnabled(const char* name, bool fallback = true) {
  auto environment = base::Environment::Create();
  const auto raw = environment->GetVar(name);
  if (!raw.has_value()) return fallback;
  return *raw != "0" && !base::EqualsCaseInsensitiveASCII(*raw, "false") &&
         !base::EqualsCaseInsensitiveASCII(*raw, "off");
}

bool NautrixTradingUrlMatches(std::string url) {
  auto environment = base::Environment::Create();
  const std::string mode =
      environment->GetVar("NAUTRIX_TRADING_MODE").value_or("automatic");
  if (base::EqualsCaseInsensitiveASCII(mode, "normal")) return false;
  if (base::EqualsCaseInsensitiveASCII(mode, "aggressive")) return true;
  if (!base::EqualsCaseInsensitiveASCII(mode, "automatic")) return false;

  const auto raw_sites = environment->GetVar("NAUTRIX_TRADING_SITES");
  if (!raw_sites.has_value() || raw_sites->empty()) return false;
  url = base::ToLowerASCII(url);
  const size_t scheme = url.find("://");
  size_t host_start = scheme == std::string::npos ? 0 : scheme + 3;
  size_t host_end = url.find_first_of("/:?#", host_start);
  std::string host = url.substr(host_start, host_end - host_start);
  if (host.empty()) return false;

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
// NAUTRIX_TRADING_SCHEDULER_END
'''
    text = insert_once(text, "namespace {\n", helper, BLINK_MARKER, path)

    old_trace = '''void FrameSchedulerImpl::TraceUrlChange(const String& url) {
  TRACE_EVENT_END("renderer.scheduler.status", url_track_);
  TRACE_EVENT_BEGIN("renderer.scheduler.status", "FrameScheduler.URL",
                    url_track_, "url", url);
}
'''
    new_trace = '''void FrameSchedulerImpl::TraceUrlChange(const String& url) {
  const bool previous_nautrix_low_latency_page = nautrix_low_latency_page_;
  nautrix_low_latency_page_ = NautrixTradingUrlMatches(url.Utf8());
  if (previous_nautrix_low_latency_page != nautrix_low_latency_page_) {
    UpdatePolicy();
  }
  TRACE_EVENT_END("renderer.scheduler.status", url_track_);
  TRACE_EVENT_BEGIN("renderer.scheduler.status", "FrameScheduler.URL",
                    url_track_, "url", url);
}
'''
    if old_trace not in text:
        raise RuntimeError(f"{path}: TraceUrlChange anchor not found")
    text = text.replace(old_trace, new_trace, 1)

    old_lifecycle = '''  if (subresource_loading_paused_ && type == ObserverType::kLoader)
    return SchedulingLifecycleState::kStopped;
  if (type == ObserverType::kLoader &&
      parent_page_scheduler_->OptedOutFromAggressiveThrottling()) {
'''
    new_lifecycle = '''  if (subresource_loading_paused_ && type == ObserverType::kLoader)
    return SchedulingLifecycleState::kStopped;
  if (nautrix_low_latency_page_ &&
      NautrixSchedulerEnvEnabled("NAUTRIX_SELECTIVE_THROTTLING_BYPASS")) {
    return SchedulingLifecycleState::kNotThrottled;
  }
  if (type == ObserverType::kLoader &&
      parent_page_scheduler_->OptedOutFromAggressiveThrottling()) {
'''
    if old_lifecycle not in text:
        raise RuntimeError(f"{path}: lifecycle anchor not found")
    text = text.replace(old_lifecycle, new_lifecycle, 1)

    old_throttle = '''ThrottlingType FrameSchedulerImpl::ComputeThrottlingType() {
  DCHECK(parent_page_scheduler_);

  const bool page_can_be_throttled_intensively =
'''
    new_throttle = '''ThrottlingType FrameSchedulerImpl::ComputeThrottlingType() {
  DCHECK(parent_page_scheduler_);

  if (nautrix_low_latency_page_ &&
      NautrixSchedulerEnvEnabled("NAUTRIX_SELECTIVE_THROTTLING_BYPASS")) {
    return ThrottlingType::kNone;
  }

  const bool page_can_be_throttled_intensively =
'''
    if old_throttle not in text:
        raise RuntimeError(f"{path}: ComputeThrottlingType anchor not found")
    text = text.replace(old_throttle, new_throttle, 1)

    old_priority = '''  if (task_queue->GetPrioritisationType() ==
      MainThreadTaskQueue::QueueTraits::PrioritisationType::kLow) {
    return TaskPriority::kLowPriority;
  }

  return TaskPriority::kNormalPriority;
}
'''
    new_priority = '''  if (task_queue->GetPrioritisationType() ==
      MainThreadTaskQueue::QueueTraits::PrioritisationType::kLow) {
    return TaskPriority::kLowPriority;
  }

  if (nautrix_low_latency_page_) {
    return TaskPriority::kHighPriority;
  }
  return TaskPriority::kNormalPriority;
}
'''
    if old_priority not in text:
        raise RuntimeError(f"{path}: ComputePriority tail anchor not found")
    text = text.replace(old_priority, new_priority, 1)

    path.write_text(text, encoding="utf-8", newline="\n")


def apply(source_root: Path) -> None:
    source_root = source_root.resolve()
    required = [
        source_root / "services/network/url_loader.cc",
        source_root / "third_party/blink/renderer/platform/scheduler/main_thread/frame_scheduler_impl.h",
        source_root / "third_party/blink/renderer/platform/scheduler/main_thread/frame_scheduler_impl.cc",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise RuntimeError("incomplete Chromium checkout; missing:\n  " + "\n  ".join(missing))
    patch_network(source_root)
    patch_blink_header(source_root)
    patch_blink_impl(source_root)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_trading_latency.py <chromium-src>", file=sys.stderr)
        return 2
    try:
        apply(Path(sys.argv[1]))
    except Exception as exc:
        print(f"Nautrix trading-latency patch error: {exc}", file=sys.stderr)
        return 1
    print("Nautrix trading latency patch applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
