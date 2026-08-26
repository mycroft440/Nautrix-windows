# Nautrix Windows

Nautrix Windows is a Windows-first web browser focused on responsiveness, low latency, and a lightweight native interface.

## Current foundation

- C++23
- Native Win32 user interface
- Microsoft WebView2 for web content
- CMake build
- Windows x64 Debug and Release builds in GitHub Actions
- Per-monitor DPI awareness
- Native address bar and navigation controls

The project intentionally keeps browser chrome in native Win32 code while using WebView2 only for web-content rendering.

## Requirements

- Windows 10/11 x64
- Visual Studio 2022 Build Tools or Visual Studio 2022 with Desktop development with C++
- CMake 3.25+
- Microsoft Edge WebView2 Evergreen Runtime
- PowerShell

## Build locally

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1
cmake -S . -B build -A x64
cmake --build build --config Release --parallel
```

The resulting executable is expected at:

```text
build/Release/Nautrix.exe
```

For a Debug build:

```powershell
cmake --build build --config Debug --parallel
```

## First implemented browser controls

- Back
- Forward
- Reload
- Address/search bar
- Go
- `Ctrl+L` focuses the address bar
- `Ctrl+R` reloads
- `F5` reloads

Text entered without a recognizable host is sent to Google Search. Normal hosts are opened over HTTPS by default.

## WebView2 SDK

The SDK is pinned by the build to `Microsoft.Web.WebView2 1.0.4129.50`. The bootstrap script downloads and extracts that exact SDK package so local and CI builds use the same headers and loader library.

The runtime itself is not bundled at this stage; Nautrix uses the installed Evergreen WebView2 Runtime.

## Development plan

See [`PLAN.md`](PLAN.md).
