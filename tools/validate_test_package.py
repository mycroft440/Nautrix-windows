#!/usr/bin/env python3
"""Exercise test-package integrity checks without requiring a Chromium build."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "tools" / "package_test_installer.ps1"
VERIFY = REPO / "tools" / "verify_test_package.ps1"
PWSH = shutil.which("pwsh")


def run(args: list[str], cwd: Path, succeeds: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if (result.returncode == 0) != succeeds:
        raise AssertionError(
            f"Unexpected exit code {result.returncode} for: {args}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def package(chromium: Path, launcher: Path, output: str | Path, cwd: Path, succeeds: bool = True) -> None:
    assert PWSH, "PowerShell 7 is required for test-package validation"
    run(
        [
            PWSH,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PACKAGE),
            "-Variant",
            "baseline",
            "-ChromiumOutput",
            str(chromium),
            "-LauncherOutput",
            str(launcher),
            "-OutputDir",
            str(output),
        ],
        cwd,
        succeeds,
    )


def verify(package_dir: Path, succeeds: bool = True) -> None:
    assert PWSH, "PowerShell 7 is required for test-package validation"
    run(
        [PWSH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(VERIFY), "-PackageDir", str(package_dir)],
        package_dir.parent,
        succeeds,
    )


def test_manifest_coverage(package_dir: Path) -> None:
    manifest = json.loads((package_dir / "MANIFEST.json").read_text(encoding="utf-8-sig"))
    payload = {entry["path"] for entry in manifest["files"]}
    actual = {
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file()
    }
    assert payload | {"MANIFEST.json", "SHA256SUMS.txt"} == actual

    hashes = {
        line.split(" *", 1)[1]
        for line in (package_dir / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()
    }
    assert hashes == payload | {"MANIFEST.json"}


def mutate_and_reject(source: Path, destination: Path, mutation) -> None:
    shutil.copytree(source, destination)
    mutation(destination)
    verify(destination, succeeds=False)


def main() -> int:
    assert PWSH, "PowerShell 7 is required for test-package validation"
    with tempfile.TemporaryDirectory(prefix="nautrix package validation ") as temporary:
        root = Path(temporary)
        chromium = root / "Chromium Output"
        launcher = root / "Launcher Output"
        chromium.mkdir()
        launcher.mkdir()
        (chromium / "mini_installer.exe").write_bytes(b"test setup")
        (chromium / "chrome.exe").write_bytes(b"test browser")
        (launcher / "NautrixLauncher.exe").write_bytes(b"test launcher")
        (launcher / "NautrixNetworkSettings.exe").write_bytes(b"test settings")

        relative_package = Path("relative package with spaces")
        package(chromium, launcher, relative_package, root)
        relative_package = root / relative_package
        verify(relative_package)
        test_manifest_coverage(relative_package)
        package(chromium, launcher, Path("relative package with spaces"), root, succeeds=False)

        absolute_package = root / "absolute package with spaces"
        package(chromium, launcher, absolute_package, root)
        verify(absolute_package)
        test_manifest_coverage(absolute_package)

        mutate_and_reject(relative_package, root / "unexpected file", lambda directory: (directory / "unexpected.exe").write_bytes(b"extra"))

        def duplicate_manifest(directory: Path) -> None:
            path = directory / "MANIFEST.json"
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            data["files"].append(data["files"][0].copy())
            path.write_text(json.dumps(data), encoding="utf-8")

        mutate_and_reject(relative_package, root / "duplicate manifest", duplicate_manifest)

        def traversal_manifest(directory: Path) -> None:
            path = directory / "MANIFEST.json"
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            data["files"][0]["path"] = "../outside.exe"
            path.write_text(json.dumps(data), encoding="utf-8")

        mutate_and_reject(relative_package, root / "traversal manifest", traversal_manifest)

        def absolute_manifest(directory: Path) -> None:
            path = directory / "MANIFEST.json"
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            data["files"][0]["path"] = "C:/outside.exe"
            path.write_text(json.dumps(data), encoding="utf-8")

        mutate_and_reject(relative_package, root / "absolute manifest", absolute_manifest)

        mutate_and_reject(relative_package, root / "missing file", lambda directory: (directory / "NautrixSetup.exe").unlink())

        def duplicate_checksum(directory: Path) -> None:
            path = directory / "SHA256SUMS.txt"
            lines = path.read_text(encoding="ascii").splitlines()
            path.write_text("\n".join(lines + [lines[0]]) + "\n", encoding="ascii")

        mutate_and_reject(relative_package, root / "duplicate checksum", duplicate_checksum)

        def traversal_checksum(directory: Path) -> None:
            path = directory / "SHA256SUMS.txt"
            lines = path.read_text(encoding="ascii").splitlines()
            lines[0] = lines[0].split(" *", 1)[0] + " *../outside.exe"
            path.write_text("\n".join(lines) + "\n", encoding="ascii")

        mutate_and_reject(relative_package, root / "traversal checksum", traversal_checksum)

    print("Nautrix test-package path and manifest validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
