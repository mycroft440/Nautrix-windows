# Full browser runtime checklist

Run this only against a complete Chromium-based Nautrix build.

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
