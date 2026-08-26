#!/usr/bin/env python3
"""Apply the Nautrix product layer to a pinned Chromium source checkout.

This deliberately changes only product/Windows integration strings that are
safe to carry as a downstream patch layer. It does not enable private Google
Chrome services, Chrome Sync, or Google Chrome branding.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _replace_required(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        return text.replace(old, new)
    if new in text:
        return text
    raise RuntimeError(f"{label}: expected upstream pattern not found: {old!r}")


def _patch_branding(source_root: Path) -> None:
    path = source_root / "chrome/app/theme/chromium/BRANDING"
    text = path.read_text(encoding="utf-8")
    replacements = {
        "COMPANY_FULLNAME": "Nautrix",
        "COMPANY_SHORTNAME": "Nautrix",
        "PRODUCT_FULLNAME": "Nautrix",
        "PRODUCT_SHORTNAME": "Nautrix",
        "PRODUCT_INSTALLER_FULLNAME": "Nautrix Installer",
        "PRODUCT_INSTALLER_SHORTNAME": "Nautrix Installer",
        "COPYRIGHT": "Copyright 2026 Nautrix contributors.",
        "MAC_BUNDLE_ID": "app.nautrix.browser",
    }

    for key, value in replacements.items():
        pattern = re.compile(rf"(?m)^{re.escape(key)}=.*$")
        if not pattern.search(text):
            raise RuntimeError(f"{path}: missing branding key {key}")
        text = pattern.sub(f"{key}={value}", text)

    path.write_text(text, encoding="utf-8", newline="\n")


def _patch_windows_install_identity(source_root: Path) -> None:
    path = source_root / "chrome/install_static/chromium_install_modes.h"
    text = path.read_text(encoding="utf-8")

    replacements = [
        ('inline constexpr wchar_t kProductPathName[] = L"Chromium";',
         'inline constexpr wchar_t kProductPathName[] = L"Nautrix";'),
        ('.base_app_name = L"Chromium",',
         '.base_app_name = L"Nautrix",'),
        ('.base_app_id = L"Chromium",',
         '.base_app_id = L"Nautrix",'),
        ('.browser_prog_id_prefix = L"ChromiumHTM",',
         '.browser_prog_id_prefix = L"NautrixHTM",'),
        ('L"Chromium HTML Document",',
         'L"Nautrix HTML Document",'),
        ('.direct_launch_url_scheme = "chromium",',
         '.direct_launch_url_scheme = "nautrix",'),
        ('.pdf_prog_id_prefix = L"ChromiumPDF",',
         '.pdf_prog_id_prefix = L"NautrixPDF",'),
        ('L"Chromium PDF Document",',
         'L"Nautrix PDF Document",'),
    ]

    for old, new in replacements:
        # direct_launch_url_scheme did not exist in older Chromium revisions.
        if old.startswith('.direct_launch_url_scheme') and old not in text and new not in text:
            continue
        text = _replace_required(text, old, new, str(path))

    path.write_text(text, encoding="utf-8", newline="\n")


def _patch_visible_product_strings(source_root: Path) -> None:
    path = source_root / "chrome/app/chromium_strings.grd"
    text = path.read_text(encoding="utf-8")

    # Change only text nodes between XML tags. Attributes/URLs remain untouched.
    # This avoids rewriting chromium.org links or GRIT metadata while replacing
    # visible product-name strings such as "Welcome to Chromium".
    def repl(match: re.Match[str]) -> str:
        visible = match.group(1)
        visible = visible.replace("Chromium", "Nautrix")
        return ">" + visible + "<"

    patched = re.sub(r">([^<>]*)<", repl, text)
    path.write_text(patched, encoding="utf-8", newline="\n")


def apply(source_root: Path) -> None:
    source_root = source_root.resolve()
    required = [
        source_root / "chrome/app/theme/chromium/BRANDING",
        source_root / "chrome/install_static/chromium_install_modes.h",
        source_root / "chrome/app/chromium_strings.grd",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Not a complete Chromium source checkout; missing:\n  " +
            "\n  ".join(missing)
        )

    _patch_branding(source_root)
    _patch_windows_install_identity(source_root)
    _patch_visible_product_strings(source_root)

    marker = source_root / ".nautrix-product-layer"
    marker.write_text(
        "Nautrix downstream product layer applied.\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_nautrix.py <chromium-src>", file=sys.stderr)
        return 2
    try:
        apply(Path(sys.argv[1]))
    except Exception as exc:
        print(f"Nautrix product-layer error: {exc}", file=sys.stderr)
        return 1

    print("Nautrix product layer applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
