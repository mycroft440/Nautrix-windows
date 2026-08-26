# Building Nautrix from Chromium on Windows

## Requirements

The upstream Chromium Windows build currently requires:

- Windows 10 or newer, x86-64.
- Visual Studio 2026 (18.0 or newer) with **Desktop development with C++**.
- MFC/ATL support components.
- NTFS storage.
- At least 100 GB free disk space for the checkout/build.
- More than 16 GB RAM is strongly recommended.

The Nautrix scripts use Chromium's official `depot_tools`, `gclient`, GN and
`autoninja` flow.

## Checkout

From a normal `cmd.exe`:

```bat
tools\bootstrap_chromium.cmd
```

This clones `depot_tools`, obtains Chromium, synchronizes the exact revision
pinned in `chromium/VERSION`, and applies Nautrix product branding/integration.

The source tree is stored in:

```text
.chromium-work\src
```

It is intentionally ignored by Git.

## Build

```bat
tools\build_chromium.cmd
```

The production baseline uses:

```text
.chromium-work\src\out\Nautrix
```

After a successful build:

```bat
tools\run_nautrix.cmd
```

To open Google's account page specifically for interactive compatibility
testing:

```bat
tools\test_google_login.cmd
```

## Why hosted CI does not compile Chromium

A standard GitHub-hosted Windows runner does not provide the storage footprint
needed for a complete Chromium checkout/build. The repository CI therefore
validates the pinned version, GN configuration and the Nautrix downstream patch
layer. A full binary build should run on a capable Windows workstation or a
self-hosted runner with the required disk/RAM.

## Important distinction

Nautrix is built with open Chromium branding mode (`is_chrome_branded=false`).
The downstream patch changes Nautrix's own product identity; it does not attempt
to impersonate Google Chrome or enable private Google Chrome services.
