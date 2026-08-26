#!/usr/bin/env python3
"""Fast validation for the Nautrix Chromium integration layer.

This runs in ordinary GitHub-hosted Windows CI. It intentionally does not fetch
or compile Chromium because a full Windows Chromium checkout/build requires
far more disk/RAM than a standard hosted runner.
"""

from __future__ import annotations

import importlib.util
import re
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def _load_apply_module():
    path = REPO / "tools/apply_nautrix.py"
    spec = importlib.util.spec_from_file_location("apply_nautrix", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load tools/apply_nautrix.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_version() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in (REPO / "chromium/VERSION").read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        key, sep, value = raw.partition("=")
        if not sep:
            raise AssertionError(f"Invalid VERSION line: {raw}")
        values[key] = value

    for required in ("CHANNEL", "VERSION", "REVISION", "MAIN_BRANCH_POSITION"):
        assert values.get(required), f"Missing {required} in chromium/VERSION"
    assert re.fullmatch(r"[0-9a-f]{40}", values["REVISION"]), "REVISION must be a 40-char git SHA"
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", values["VERSION"]), "Invalid Chromium version"
    return values


def _validate_gn_args() -> None:
    args = (REPO / "chromium/args/Release.gn").read_text(encoding="utf-8")
    assert 'target_cpu = "x64"' in args
    assert "is_debug = false" in args
    assert "is_chrome_branded = false" in args
    assert "is_chrome_branded = true" not in args


def _validate_no_embedded_engine() -> None:
    forbidden = ("Microsoft.Web.WebView2", "#include <WebView2.h>", "CreateCoreWebView2")
    for path in REPO.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in {".md", ".py", ".cmd", ".ps1", ".gn", ".yml", ".yaml", ".txt", ""}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.name == "validate_nautrix.py":
            continue
        for needle in forbidden:
            assert needle not in text, f"Embedded-engine dependency still present in {path}: {needle}"


def _validate_product_layer() -> None:
    module = _load_apply_module()

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        branding = root / "chrome/app/theme/chromium/BRANDING"
        modes = root / "chrome/install_static/chromium_install_modes.h"
        strings = root / "chrome/app/chromium_strings.grd"
        branding.parent.mkdir(parents=True)
        modes.parent.mkdir(parents=True)
        strings.parent.mkdir(parents=True, exist_ok=True)

        branding.write_text(
            "COMPANY_FULLNAME=The Chromium Authors\n"
            "COMPANY_SHORTNAME=The Chromium Authors\n"
            "PRODUCT_FULLNAME=Chromium\n"
            "PRODUCT_SHORTNAME=Chromium\n"
            "PRODUCT_INSTALLER_FULLNAME=Chromium Installer\n"
            "PRODUCT_INSTALLER_SHORTNAME=Chromium Installer\n"
            "COPYRIGHT=Copyright 2017 The Chromium Authors. All rights reserved.\n"
            "MAC_BUNDLE_ID=org.chromium.Chromium\n"
            "MAC_CREATOR_CODE=Cr24\n",
            encoding="utf-8",
        )

        modes.write_text(
            'inline constexpr wchar_t kProductPathName[] = L"Chromium";\n'
            '.base_app_name = L"Chromium",\n'
            '.base_app_id = L"Chromium",\n'
            '.browser_prog_id_prefix = L"ChromiumHTM",\n'
            'L"Chromium HTML Document",\n'
            '.direct_launch_url_scheme = "chromium",\n'
            '.pdf_prog_id_prefix = L"ChromiumPDF",\n'
            'L"Chromium PDF Document",\n',
            encoding="utf-8",
        )

        strings.write_text(
            '<grit><message desc="Chromium product" url="https://chromium.org">'
            'Welcome to Chromium</message></grit>\n',
            encoding="utf-8",
        )

        module.apply(root)
        module.apply(root)

        assert "PRODUCT_FULLNAME=Nautrix" in branding.read_text(encoding="utf-8")
        patched_modes = modes.read_text(encoding="utf-8")
        assert 'kProductPathName[] = L"Nautrix"' in patched_modes
        assert '.base_app_name = L"Nautrix"' in patched_modes
        assert '.direct_launch_url_scheme = "nautrix"' in patched_modes

        patched_strings = strings.read_text(encoding="utf-8")
        assert "Welcome to Nautrix" in patched_strings
        assert 'url="https://chromium.org"' in patched_strings, "Attributes/URLs must not be rewritten"


def main() -> int:
    values = _parse_version()
    _validate_gn_args()
    _validate_no_embedded_engine()
    _validate_product_layer()
    print(
        "Nautrix Chromium layer validated: "
        f"{values['CHANNEL']} {values['VERSION']} @ {values['REVISION']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
