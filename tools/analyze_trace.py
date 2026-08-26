#!/usr/bin/env python3
"""Summarize Chromium startup/latency trace events relevant to Nautrix."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

TOKENS = ("latency", "input", "navigation", "loading", "network", "startup", "frame", "commit", "paint")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    data = json.loads(args.trace.read_text(encoding="utf-8"))
    events = data.get("traceEvents", data if isinstance(data, list) else [])
    stats: dict[str, list[float]] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)

    for event in events:
        name = str(event.get("name", ""))
        category = str(event.get("cat", ""))
        haystack = (name + " " + category).lower()
        if not any(token in haystack for token in TOKENS):
            continue
        key = f"{category}:{name}"
        counts[key] += 1
        duration = event.get("dur")
        if isinstance(duration, (int, float)) and duration >= 0:
            stats[key].append(float(duration) / 1000.0)  # trace duration is us -> ms

    output = args.output or args.trace.with_suffix(".summary.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["event", "count", "duration_samples", "avg_ms", "max_ms"])
        for key in sorted(counts):
            values = stats.get(key, [])
            writer.writerow([
                key,
                counts[key],
                len(values),
                f"{sum(values) / len(values):.3f}" if values else "",
                f"{max(values):.3f}" if values else "",
            ])
    print(f"[Nautrix] Trace summary: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
