#!/usr/bin/env python3
"""Integrate Nautrix launcher/config into Chromium's native Windows installer."""

from __future__ import annotations

import sys
from pathlib import Path


def _replace_required(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"{label}: expected upstream pattern not found")


def _insert_once(text: str, anchor: str, addition: str, marker: str, label: str) -> str:
    if marker in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"{label}: insertion anchor not found")
    return text.replace(anchor, addition + anchor, 1)


def _patch_shell_util(source_root: Path) -> None:
    path = source_root / "chrome/installer/util/shell_util.cc"
    text = path.read_text(encoding="utf-8")

    helper = r'''// NAUTRIX_INSTALLER_INTEGRATION_BEGIN
constexpr base::FilePath::CharType kNautrixLauncherExe[] =
    FILE_PATH_LITERAL("NautrixLauncher.exe");
constexpr base::FilePath::CharType kNautrixConfigDir[] =
    FILE_PATH_LITERAL("config");

base::CommandLine GetNautrixLauncherCommandLine(
    const base::FilePath& chrome_exe) {
  base::CommandLine command(chrome_exe.DirName().Append(kNautrixLauncherExe));
  command.AppendSwitchPath("browser", chrome_exe);
  command.AppendSwitchPath("config-dir",
                           chrome_exe.DirName().Append(kNautrixConfigDir));
  return command;
}

bool IsNautrixBrowserShortcutTarget(const base::FilePath& target) {
  return target.BaseName().value() == chrome::kBrowserProcessExecutableName;
}
// NAUTRIX_INSTALLER_INTEGRATION_END

'''
    text = _insert_once(
        text,
        'const wchar_t kReinstallCommand[] = L"ReinstallCommand";\n',
        helper,
        "// NAUTRIX_INSTALLER_INTEGRATION_BEGIN",
        str(path),
    )

    start_menu_old = '''  entries->push_back(std::make_unique<RegistryEntry>(
      start_menu_entry + ShellUtil::kRegShellOpen, quoted_exe_path));
'''
    start_menu_new = '''  entries->push_back(std::make_unique<RegistryEntry>(
      start_menu_entry + ShellUtil::kRegShellOpen,
      GetNautrixLauncherCommandLine(chrome_exe).GetCommandLineString()));
'''
    text = _replace_required(text, start_menu_old, start_menu_new, str(path))

    shortcut_old = '''  base_operation = TranslateShortcutOperation(operation);
  base_properties = TranslateShortcutProperties(properties);
  shortcut_path = *chosen_path;
'''
    shortcut_new = '''  base_operation = TranslateShortcutOperation(operation);
  base_properties = TranslateShortcutProperties(properties);
  if (properties.has_target() &&
      IsNautrixBrowserShortcutTarget(properties.target)) {
    const base::CommandLine launcher =
        GetNautrixLauncherCommandLine(properties.target);
    base_properties.set_target(launcher.GetProgram());
    base_properties.set_working_dir(properties.target.DirName());
    std::wstring arguments = launcher.GetArgumentsString();
    if (properties.has_arguments() && !properties.arguments.empty()) {
      if (!arguments.empty()) {
        arguments.push_back(L' ');
      }
      arguments.append(properties.arguments);
    }
    base_properties.set_arguments(arguments);
  }
  shortcut_path = *chosen_path;
'''
    text = _replace_required(text, shortcut_old, shortcut_new, str(path))

    shell_open_old = '''std::wstring ShellUtil::GetChromeShellOpenCmd(
    const base::FilePath& chrome_exe) {
  return base::CommandLine(chrome_exe).GetCommandLineStringForShell();
}
'''
    shell_open_new = '''std::wstring ShellUtil::GetChromeShellOpenCmd(
    const base::FilePath& chrome_exe) {
  return GetNautrixLauncherCommandLine(chrome_exe)
      .GetCommandLineStringForShell();
}
'''
    text = _replace_required(text, shell_open_old, shell_open_new, str(path))
    path.write_text(text, encoding="utf-8", newline="\n")


def _patch_release_manifest(source_root: Path) -> None:
    path = source_root / "chrome/installer/mini_installer/chrome.release"
    text = path.read_text(encoding="utf-8")
    if "NautrixLauncher.exe: %(ChromeDir)s\\" in text:
        return
    anchor = "chrome.exe: %(ChromeDir)s\\\n"
    addition = (
        "NautrixLauncher.exe: %(ChromeDir)s\\\n"
        "NautrixNetworkSettings.exe: %(ChromeDir)s\\\n"
        "config\\dns.ini: %(ChromeDir)s\\config\\\n"
        "config\\latency.ini: %(ChromeDir)s\\config\\\n"
    )
    if anchor not in text:
        raise RuntimeError(f"{path}: Chrome application manifest anchor not found")
    text = text.replace(anchor, anchor + addition, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def _patch_mini_installer_build(source_root: Path) -> None:
    path = source_root / "chrome/installer/mini_installer/BUILD.gn"
    text = path.read_text(encoding="utf-8")
    marker = '"$root_out_dir/NautrixLauncher.exe",'
    if marker in text:
        return
    anchor = '    "$root_out_dir/chrome.exe",\n'
    addition = (
        '    "$root_out_dir/NautrixLauncher.exe",\n'
        '    "$root_out_dir/NautrixNetworkSettings.exe",\n'
        '    "$root_out_dir/config/dns.ini",\n'
        '    "$root_out_dir/config/latency.ini",\n'
    )
    if anchor not in text:
        raise RuntimeError(f"{path}: mini-installer input anchor not found")
    text = text.replace(anchor, anchor + addition, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def apply(source_root: Path) -> None:
    source_root = source_root.resolve()
    required = [
        source_root / "chrome/installer/util/shell_util.cc",
        source_root / "chrome/installer/mini_installer/chrome.release",
        source_root / "chrome/installer/mini_installer/BUILD.gn",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Not a complete Chromium installer checkout; missing:\n  "
            + "\n  ".join(missing)
        )

    _patch_shell_util(source_root)
    _patch_release_manifest(source_root)
    _patch_mini_installer_build(source_root)

    (source_root / ".nautrix-installer-layer").write_text(
        "Nautrix native Windows installer integration applied.\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_installer_integration.py <chromium-src>", file=sys.stderr)
        return 2
    try:
        apply(Path(sys.argv[1]))
    except Exception as exc:
        print(f"Nautrix installer integration error: {exc}", file=sys.stderr)
        return 1
    print("Nautrix native Windows installer integration applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
