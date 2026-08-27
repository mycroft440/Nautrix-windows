# Full browser runtime checklist

Run this only against a complete Chromium-based Nautrix build.

## Native Windows installation
- run `NautrixSetup.exe` directly on a clean Windows user
- confirm the installed `chrome.exe`, `NautrixLauncher.exe`, `NautrixNetworkSettings.exe`, `config/dns.ini`, and `config/latency.ini` are present without post-install copying
- confirm Desktop/Start-menu Nautrix shortcuts target `NautrixLauncher.exe`
- confirm shortcut arguments retain `--browser=` and `--config-dir=` routing
- confirm installed `NautrixHTM*` shell-open commands route through `NautrixLauncher.exe`
- confirm HTTP/HTTPS/default-browser launches chosen through Windows reach the installed browser through the launcher
- confirm installer maintenance/uninstall remains functional
- uninstall Nautrix and confirm browser files, launcher/config payload, shortcuts, ProgIDs, and uninstall registration are removed without manual cleanup

## Core browser
- tabs and multiple windows
- address bar/search
- downloads
- history/bookmarks
- cookies/session persistence
- profiles/incognito
- password/autofill UI available in open Chromium
- permissions
- DevTools
- extensions / Chrome Web Store
- WebRTC/WebGL/WebGPU/PWA

## Google web authentication
- accounts.google.com sign-in
- Gmail and YouTube session
- Continue with Google on a third-party site
- 2FA
- WebAuthn/passkey
- restart browser and verify session persists

## Network
- Automatic DNS winner applies in Chromium NetLog
- Manual DNS applies
- System DNS bypasses Nautrix override
- DoH selected provider appears in NetLog
- priority-origin preconnect occurs without navigation
- QUIC/HTTP3 remains available
- IPv4/IPv6 behavior matches the current network

## Performance
Capture baseline and PGO separately on the same machine/network:
- cold process start
- warm process start
- navigation duration
- DNS
- TCP/QUIC connect
- TLS
- first byte
- CPU/RAM process tree
- startup trace / input-to-frame where applicable

Do not mark a gate complete based only on source/CI validation; record the actual runtime result.
