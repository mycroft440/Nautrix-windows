#!/usr/bin/env python3
"""Apply Nautrix resource-efficiency defaults after the latency patches.

This layer deliberately keeps Chromium's process model, GPU acceleration,
Site Isolation, sandbox, cache sizing and native background lifecycle intact.
It only makes the existing Nautrix trading exceptions narrower and bounds
speculative connection work.
"""

from __future__ import annotations

import sys
from pathlib import Path

PREFS_MARKER = "// NAUTRIX_RESOURCE_EFFICIENCY_PREFS"
SCHEDULER_MARKER = "// NAUTRIX_RESOURCE_EFFICIENCY_SCHEDULER"
PRECONNECT_MARKER = "// NAUTRIX_RESOURCE_EFFICIENCY_PRECONNECT"


def replace_once(text: str, old: str, new: str, path: Path) -> str:
    if old not in text:
        raise RuntimeError(f"{path}: expected anchor not found: {old[:120]!r}")
    return text.replace(old, new, 1)


def patch_prefs(source_root: Path) -> None:
    path = source_root / "components/performance_manager/user_tuning/prefs.cc"
    text = path.read_text(encoding="utf-8")
    if PREFS_MARKER in text:
        return
    if "// NAUTRIX_TRADING_PRIORITY_BEGIN" not in text:
        raise RuntimeError(f"{path}: trading priority patch must be applied first")

    if '#include "base/strings/string_number_conversions.h"\n' not in text:
        text = replace_once(
            text,
            '#include "base/strings/string_split.h"\n',
            '#include "base/strings/string_number_conversions.h"\n'
            '#include "base/strings/string_split.h"\n',
            path,
        )

    helper = r'''

// NAUTRIX_RESOURCE_EFFICIENCY_PREFS
int NautrixMemorySaverState() {
  return NautrixTradingPolicyEnabled("NAUTRIX_MEMORY_SAVER_ENABLED")
             ? static_cast<int>(MemorySaverModeState::kEnabled)
             : static_cast<int>(MemorySaverModeState::kDisabled);
}

int NautrixMemorySaverAggressiveness() {
  auto environment = base::Environment::Create();
  const std::string value = base::ToLowerASCII(
      environment->GetVar("NAUTRIX_MEMORY_SAVER_AGGRESSIVENESS")
          .value_or("medium"));
  if (value == "conservative") {
    return static_cast<int>(MemorySaverModeAggressiveness::kConservative);
  }
  if (value == "aggressive") {
    return static_cast<int>(MemorySaverModeAggressiveness::kAggressive);
  }
  return static_cast<int>(MemorySaverModeAggressiveness::kMedium);
}

int NautrixMemorySaverDiscardMinutes() {
  auto environment = base::Environment::Create();
  int minutes = kDefaultMemorySaverModeTimeBeforeDiscardInMinutes;
  if (const auto value =
          environment->GetVar("NAUTRIX_MEMORY_SAVER_DISCARD_MINUTES")) {
    base::StringToInt(*value, &minutes);
  }
  return std::max(15, std::min(minutes, 1440));
}

base::Value::List GetNautrixCriticalTradingSites() {
  base::Value::List sites;
  auto environment = base::Environment::Create();
  const auto raw_sites = environment->GetVar("NAUTRIX_CRITICAL_TRADING_SITES");
  if (!raw_sites.has_value() || raw_sites->empty()) {
    return sites;
  }
  for (std::string site :
       base::SplitString(*raw_sites, ",", base::TRIM_WHITESPACE,
                         base::SPLIT_WANT_NONEMPTY)) {
    site = base::ToLowerASCII(site);
    if (!site.empty()) sites.Append(std::move(site));
  }
  return sites;
}
'''
    anchor = "\n}  // namespace\n// NAUTRIX_TRADING_PRIORITY_END\n"
    text = replace_once(text, anchor, helper + anchor, path)

    old_lifecycle = '''base::Value::List GetNautrixLifecycleProtectedSites() {
  if (!NautrixTradingPolicyEnabled("NAUTRIX_FREEZING_PROTECTION")) {
    return {};
  }
  return GetNautrixTradingSites();
}
'''
    new_lifecycle = '''base::Value::List GetNautrixLifecycleProtectedSites() {
  if (!NautrixTradingPolicyEnabled("NAUTRIX_FREEZING_PROTECTION")) {
    return {};
  }
  // Visible/recent pages are already protected by Chromium. Keep permanent
  // discard/freezing exceptions only for sites explicitly declared critical.
  return GetNautrixCriticalTradingSites();
}
'''
    text = replace_once(text, old_lifecycle, new_lifecycle, path)

    old_foreground = '''  return GetNautrixTradingSites();
}

}  // namespace
// NAUTRIX_TRADING_PRIORITY_END
'''
    new_foreground = '''  return GetNautrixCriticalTradingSites();
}
'''
    # The resource helper now sits between this function and the namespace end.
    if old_foreground in text:
        text = text.replace(old_foreground, new_foreground + helper + anchor, 1)
    else:
        # Normal path after helper insertion: replace the single return inside
        # GetNautrixForegroundPrioritySites without touching the earlier helper.
        function_start = text.find("base::Value::List GetNautrixForegroundPrioritySites()")
        function_end = text.find("\n}\n", function_start)
        if function_start < 0 or function_end < 0:
            raise RuntimeError(f"{path}: foreground priority helper not found")
        section = text[function_start : function_end + 3]
        if "return GetNautrixTradingSites();" not in section:
            raise RuntimeError(f"{path}: foreground priority return anchor not found")
        section = section.replace(
            "return GetNautrixTradingSites();",
            "return GetNautrixCriticalTradingSites();",
            1,
        )
        text = text[:function_start] + section + text[function_end + 3 :]

    text = replace_once(
        text,
        '''  registry->RegisterIntegerPref(
      kMemorySaverModeTimeBeforeDiscardInMinutes,
      kDefaultMemorySaverModeTimeBeforeDiscardInMinutes);
''',
        '''  registry->RegisterIntegerPref(
      kMemorySaverModeTimeBeforeDiscardInMinutes,
      NautrixMemorySaverDiscardMinutes());
''',
        path,
    )
    text = replace_once(
        text,
        '''  registry->RegisterIntegerPref(
      kMemorySaverModeState, static_cast<int>(MemorySaverModeState::kDisabled));
''',
        '''  registry->RegisterIntegerPref(kMemorySaverModeState,
                                NautrixMemorySaverState());
''',
        path,
    )
    text = replace_once(
        text,
        '''  registry->RegisterIntegerPref(
      kMemorySaverModeAggressiveness,
      static_cast<int>(MemorySaverModeAggressiveness::kMedium));
''',
        '''  registry->RegisterIntegerPref(kMemorySaverModeAggressiveness,
                                NautrixMemorySaverAggressiveness());
''',
        path,
    )

    path.write_text(text, encoding="utf-8", newline="\n")


def patch_scheduler(source_root: Path) -> None:
    path = source_root / "third_party/blink/renderer/platform/scheduler/main_thread/frame_scheduler_impl.cc"
    text = path.read_text(encoding="utf-8")
    if SCHEDULER_MARKER in text:
        return
    if "// NAUTRIX_TRADING_SCHEDULER_BEGIN" not in text:
        raise RuntimeError(f"{path}: trading scheduler patch must be applied first")

    text = replace_once(
        text,
        "// NAUTRIX_TRADING_SCHEDULER_END\n",
        "// NAUTRIX_RESOURCE_EFFICIENCY_SCHEDULER\n"
        "// Hidden idle trading pages use upstream throttling. Active connections\n"
        "// can remain latency-critical without making every hidden tab exempt.\n"
        "// NAUTRIX_TRADING_SCHEDULER_END\n",
        path,
    )

    text = text.replace(
        '''  if (nautrix_low_latency_page_ &&
      NautrixSchedulerEnvEnabled("NAUTRIX_SELECTIVE_THROTTLING_BYPASS")) {
''',
        '''  if (nautrix_low_latency_page_ &&
      NautrixSchedulerEnvEnabled("NAUTRIX_SELECTIVE_THROTTLING_BYPASS") &&
      (parent_page_scheduler_->IsPageVisible() ||
       (NautrixSchedulerEnvEnabled("NAUTRIX_BACKGROUND_CONNECTION_BYPASS") &&
        has_active_connection_))) {
''',
    )

    text = replace_once(
        text,
        '''      frame_type_ == FrameType::kMainFrame && nautrix_low_latency_page_ &&
      NautrixSchedulerEnvEnabled("NAUTRIX_HIGH_RES_TIMER");
''',
        '''      frame_type_ == FrameType::kMainFrame && nautrix_low_latency_page_ &&
      parent_page_scheduler_->IsPageVisible() &&
      NautrixSchedulerEnvEnabled("NAUTRIX_HIGH_RES_TIMER");
''',
        path,
    )

    old_visible = '''  UMA_HISTOGRAM_BOOLEAN("RendererScheduler.IPC.FrameVisibility", frame_visible);
  frame_visible_ = frame_visible;
  UpdatePolicy();
}
'''
    new_visible = '''  UMA_HISTOGRAM_BOOLEAN("RendererScheduler.IPC.FrameVisibility", frame_visible);
  frame_visible_ = frame_visible;
#if BUILDFLAG(IS_WIN)
  if (frame_type_ == FrameType::kMainFrame && nautrix_low_latency_page_ &&
      NautrixSchedulerEnvEnabled("NAUTRIX_HIGH_RES_TIMER")) {
    if (frame_visible && !nautrix_high_resolution_timer_active_) {
      base::Time::EnableHighResolutionTimer(true);
      nautrix_high_resolution_timer_active_ =
          base::Time::ActivateHighResolutionTimer(true);
    } else if (!frame_visible && nautrix_high_resolution_timer_active_) {
      base::Time::ActivateHighResolutionTimer(false);
      nautrix_high_resolution_timer_active_ = false;
    }
  }
#endif
  UpdatePolicy();
}
'''
    text = replace_once(text, old_visible, new_visible, path)

    text = replace_once(
        text,
        '''  if (nautrix_low_latency_page_) {
    return TaskPriority::kHighPriority;
  }
''',
        '''  if (nautrix_low_latency_page_ &&
      (parent_page_scheduler_->IsPageVisible() ||
       (NautrixSchedulerEnvEnabled("NAUTRIX_BACKGROUND_CONNECTION_BYPASS") &&
        has_active_connection_))) {
    return TaskPriority::kHighPriority;
  }
''',
        path,
    )

    path.write_text(text, encoding="utf-8", newline="\n")


def patch_preconnect(source_root: Path) -> None:
    path = source_root / "chrome/browser/navigation_predictor/search_engine_preconnector.cc"
    text = path.read_text(encoding="utf-8")
    if PRECONNECT_MARKER in text:
        return
    if "// NAUTRIX_PRIORITY_PRECONNECT_BEGIN" not in text:
        raise RuntimeError(f"{path}: preconnect patch must be applied first")

    text = replace_once(
        text,
        "  // NAUTRIX_PRIORITY_PRECONNECT_BEGIN\n",
        "  // NAUTRIX_PRIORITY_PRECONNECT_BEGIN\n"
        "  // NAUTRIX_RESOURCE_EFFICIENCY_PRECONNECT\n",
        path,
    )

    text = replace_once(
        text,
        '''    if (nautrix_origins.has_value() && IsPreconnectEnabled()) {
      std::optional<net::ConnectionKeepAliveConfig> keepalive_config;
''',
        '''    if (nautrix_origins.has_value() && IsPreconnectEnabled()) {
      int nautrix_preconnect_max_origins = 4;
      int nautrix_keepalive_max_origins = 2;
      if (const auto value = nautrix_environment->GetVar(
              "NAUTRIX_PRECONNECT_MAX_ORIGINS")) {
        base::StringToInt(*value, &nautrix_preconnect_max_origins);
      }
      if (const auto value = nautrix_environment->GetVar(
              "NAUTRIX_KEEPALIVE_MAX_ORIGINS")) {
        base::StringToInt(*value, &nautrix_keepalive_max_origins);
      }
      nautrix_preconnect_max_origins =
          std::max(0, std::min(nautrix_preconnect_max_origins, 32));
      nautrix_keepalive_max_origins = std::max(
          0, std::min(nautrix_keepalive_max_origins,
                      nautrix_preconnect_max_origins));

      std::optional<net::ConnectionKeepAliveConfig> keepalive_config;
''',
        path,
    )

    text = replace_once(
        text,
        '''      for (const std::string& raw_url :
           base::SplitString(*nautrix_origins, ",", base::TRIM_WHITESPACE,
                             base::SPLIT_WANT_NONEMPTY)) {
''',
        '''      int nautrix_preconnect_count = 0;
      for (const std::string& raw_url :
           base::SplitString(*nautrix_origins, ",", base::TRIM_WHITESPACE,
                             base::SPLIT_WANT_NONEMPTY)) {
        if (nautrix_preconnect_count >= nautrix_preconnect_max_origins) break;
''',
        path,
    )

    text = replace_once(
        text,
        '''            network::GetNoOpNetworkRestrictionsId(),
            keepalive_config,
            mojo::PendingRemote<
                network::mojom::ConnectionChangeObserverClient>());
''',
        '''            network::GetNoOpNetworkRestrictionsId(),
            nautrix_preconnect_count < nautrix_keepalive_max_origins
                ? keepalive_config
                : std::nullopt,
            mojo::PendingRemote<
                network::mojom::ConnectionChangeObserverClient>());
        ++nautrix_preconnect_count;
''',
        path,
    )

    path.write_text(text, encoding="utf-8", newline="\n")


def apply(source_root: Path) -> None:
    source_root = source_root.resolve()
    patch_prefs(source_root)
    patch_scheduler(source_root)
    patch_preconnect(source_root)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_resource_efficiency.py <chromium-src>", file=sys.stderr)
        return 2
    try:
        apply(Path(sys.argv[1]))
    except Exception as exc:
        print(f"Nautrix resource-efficiency patch error: {exc}", file=sys.stderr)
        return 1
    print("Nautrix adaptive resource-efficiency patch applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
