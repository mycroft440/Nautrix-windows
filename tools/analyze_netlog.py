#!/usr/bin/env python3
"""Summarize Chromium NetLog durations without depending on numeric event IDs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

INTEREST = (
    "HOST_RESOLVER",
    "CONNECT_JOB",
    "SSL_CONNECT",
    "QUIC",
    "HTTP_STREAM",
    "URL_REQUEST",
)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    values = sorted(values)
    index = min(len(values) - 1, max(0, math.ceil(len(values) * q) - 1))
    return values[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("netlog", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    data = json.loads(args.netlog.read_text(encoding="utf-8"))
    constants = data.get("constants", {})
    raw_types = constants.get("logEventTypes", {})
    type_names = {int(value): name for name, value in raw_types.items()}
    raw_phases = constants.get("logEventPhase", {})
    phase_names = {int(value): name for name, value in raw_phases.items()}

    starts: dict[tuple[int, int], float] = {}
    durations: dict[str, list[float]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)

    for event in data.get("events", []):
        event_type = int(event.get("type", -1))
        name = type_names.get(event_type, str(event_type))
        if not any(token in name for token in INTEREST):
            continue
        counts[name] += 1
        source = event.get("source", {})
        source_id = int(source.get("id", -1))
        phase = phase_names.get(int(event.get("phase", -1)), "")
        try:
            timestamp = float(event.get("time", 0.0))
        except (TypeError, ValueError):
            continue
        key = (source_id, event_type)
        if phase == "PHASE_BEGIN":
            starts[key] = timestamp
        elif phase == "PHASE_END" and key in starts:
            duration = timestamp - starts.pop(key)
            if duration >= 0:
                durations[name].append(duration)

    output = args.output or args.netlog.with_suffix(".summary.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["event", "count", "timed_samples", "median_ms", "p95_ms", "max_ms"])
        for name in sorted(counts):
            values = sorted(durations.get(name, []))
            median = math.nan
            if values:
                middle = len(values) // 2
                median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2
            writer.writerow([
                name,
                counts[name],
                len(values),
                f"{median:.3f}" if values else "",
                f"{percentile(values, .95):.3f}" if values else "",
                f"{max(values):.3f}" if values else "",
            ])

    print(f"[Nautrix] NetLog summary: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
