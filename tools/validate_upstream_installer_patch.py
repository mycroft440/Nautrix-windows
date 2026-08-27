#!/usr/bin/env python3
"""Validate Nautrix native installer/shell integration on pinned Chromium."""

from __future__ import annotations

import base64
import importlib.util
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _load_module():
    path = REPO / "tools/apply_installer_integration.py"
    spec = importlib.util.spec_from_file_location("apply_installer_integration", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pinned_revision() -> str:
    for raw in (REPO / "chromium/VERSION").read_text(encoding="utf-8").splitlines():
        key, sep, value = raw.strip().partition("=")
        if sep and key == "REVISION":
            if len(value) != 40:
                raise RuntimeError("Invalid Chromium REVISION")
            return value
    raise RuntimeError("REVISION not found in chromium/VERSION")


def _fetch_source(revision: str, path: str) -> str:
    url = f"https://chromium.googlesource.com/chromium/src/+/{revision}/{path}?format=TEXT"
    request = urllib.request.Request(
        url, headers={"User-Agent": "Nautrix-installer-patch-validator/1.0"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        encoded = response.read()
    return base64.b64decode(encoded, validate=True).decode("utf-8")


def _validate_repo_build_staging() -> None:
    stage = (REPO / "tools/stage_installer_payload.cmd").read_text(encoding="utf-8")
    for token in (
        "NautrixLauncher.exe",
        "NautrixNetworkSettings.exe",
        "config\\dns.ini",
        "config\\latency.ini",
    ):
        assert token in stage, f"Installer staging is missing {token}"

    for relative in ("tools/build_chromium.cmd", "tools/build_chromium_pgo.cmd"):
        build = (REPO / relative).read_text(encoding="utf-8")
        assert "stage_installer_payload.cmd" in build, f"{relative} does not stage installer payload"
        assert "chrome mini_installer" in build, f"{relative} does not build the native installer"

    bootstrap = (REPO / "tools/bootstrap_chromium.cmd").read_text(encoding="utf-8")
    assert "apply_installer_integration.py" in bootstrap


def main() -> int:
    revision = _pinned_revision()
    paths = (
        "chrome/installer/util/shell_util.cc",
        "chrome/installer/mini_installer/chrome.release",
        "chrome/installer/mini_installer/BUILD.gn",
    )
    sources = {path: _fetch_source(revision, path) for path in paths}

    command_line = _fetch_source(revision, "base/command_line.cc")
    assert "GetCommandLineStringForShell" in command_line
    assert "GetArgs().empty()" in command_line
    assert "kSingleArgument" in command_line

    module = _load_module()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for relative, source in sources.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8", newline="\n")

        module.apply(root)
        module.apply(root)

        shell = (root / "chrome/installer/util/shell_util.cc").read_text(encoding="utf-8")
        assert shell.count("// NAUTRIX_INSTALLER_INTEGRATION_BEGIN") == 1
        assert 'FILE_PATH_LITERAL("NautrixLauncher.exe")' in shell
        assert 'AppendSwitchPath("browser", chrome_exe)' in shell
        assert 'AppendSwitchPath("config-dir"' in shell
        assert "GetNautrixLauncherCommandLine(chrome_exe)" in shell
        assert ".GetCommandLineStringForShell()" in shell
        assert "expected_shell_program" in shell
        assert "ProgramCompare(expected_shell_program)" in shell
        assert "base_properties.set_target(launcher.GetProgram())" in shell
        assert "arguments.append(properties.arguments)" in shell
        assert "quoted_exe_path + L\" --\"" in shell, "Installer maintenance commands must stay on chrome.exe"

        release = (root / "chrome/installer/mini_installer/chrome.release").read_text(encoding="utf-8")
        for token in (
            "NautrixLauncher.exe: %(ChromeDir)s\\",
            "NautrixNetworkSettings.exe: %(ChromeDir)s\\",
            "config\\dns.ini: %(ChromeDir)s\\config\\",
            "config\\latency.ini: %(ChromeDir)s\\config\\",
        ):
            assert release.count(token) == 1, f"Native installer release manifest missing {token}"

        build = (root / "chrome/installer/mini_installer/BUILD.gn").read_text(encoding="utf-8")
        for token in (
            '"$root_out_dir/NautrixLauncher.exe",',
            '"$root_out_dir/NautrixNetworkSettings.exe",',
            '"$root_out_dir/config/dns.ini",',
            '"$root_out_dir/config/latency.ini",',
        ):
            assert build.count(token) == 1, f"mini_installer inputs missing {token}"

    _validate_repo_build_staging()
    print(f"Nautrix native installer integration matches pinned Chromium revision {revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
