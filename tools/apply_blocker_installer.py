#!/usr/bin/env python3
"""Add the packaged Nautrix declarative blocker to Chromium's mini installer."""

from __future__ import annotations

import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, path: Path) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"{path}: expected installer anchor not found")
    return text.replace(old, new, 1)


def apply(source_root: Path) -> None:
    release = source_root / "chrome/installer/mini_installer/chrome.release"
    build = source_root / "chrome/installer/mini_installer/BUILD.gn"
    for path in (release, build):
        if not path.is_file():
            raise RuntimeError(f"missing Chromium installer input: {path}")

    release_text = release.read_text(encoding="utf-8")
    release_anchor = "config\\latency.ini: %(ChromeDir)s\\config\\\n"
    release_addition = (
        release_anchor
        + "extensions\\nautrix-blocker\\manifest.json: %(ChromeDir)s\\extensions\\nautrix-blocker\\\n"
        + "extensions\\nautrix-blocker\\rules.json: %(ChromeDir)s\\extensions\\nautrix-blocker\\\n"
    )
    release_text = replace_once(
        release_text, release_anchor, release_addition, release
    )
    release.write_text(release_text, encoding="utf-8", newline="\n")

    build_text = build.read_text(encoding="utf-8")
    build_anchor = '    "$root_out_dir/config/latency.ini",\n'
    build_addition = (
        build_anchor
        + '    "$root_out_dir/extensions/nautrix-blocker/manifest.json",\n'
        + '    "$root_out_dir/extensions/nautrix-blocker/rules.json",\n'
    )
    build_text = replace_once(build_text, build_anchor, build_addition, build)
    build.write_text(build_text, encoding="utf-8", newline="\n")

    (source_root / ".nautrix-blocker-installer-layer").write_text(
        "Nautrix declarative blocker installer payload applied.\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_blocker_installer.py <chromium-src>", file=sys.stderr)
        return 2
    try:
        apply(Path(sys.argv[1]).resolve())
    except Exception as exc:
        print(f"Nautrix blocker installer patch error: {exc}", file=sys.stderr)
        return 1
    print("Nautrix blocker installer patch applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
