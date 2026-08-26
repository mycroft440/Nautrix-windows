#!/usr/bin/env python3
"""Enable Chromium's default PGO profile checkout in an existing .gclient."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: enable_pgo_checkout.py <path-to-.gclient>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    if '"checkout_pgo_profiles"' in text or "'checkout_pgo_profiles'" in text:
        print("[Nautrix] checkout_pgo_profiles already enabled.")
        return 0
    pattern = re.compile(r'(["\']custom_vars["\']\s*:\s*)\{')
    match = pattern.search(text)
    if not match:
        print("[Nautrix] custom_vars was not found in .gclient", file=sys.stderr)
        return 1
    replacement = match.group(1) + '{\n      "checkout_pgo_profiles": True,'
    text = text[:match.start()] + replacement + text[match.end():]
    path.write_text(text, encoding="utf-8", newline="\n")
    print("[Nautrix] Enabled checkout_pgo_profiles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
