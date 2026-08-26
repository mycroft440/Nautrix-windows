# Nautrix Windows — Development Plan

## Objective

Build a functional Windows-first browser focused on responsiveness, low latency, and a lightweight native interface.

## Current architecture

- C++23
- Win32 native UI
- Microsoft WebView2 (Evergreen Runtime)
- CMake
- GitHub Actions for Windows x64

## Requirements

### Foundation

- [x] Repository initialized
- [x] C++23/CMake project foundation
- [x] Native Win32 main window
- [x] WebView2 integration
- [x] Address bar
- [x] Back / Forward / Reload / Go
- [x] URL input and text search
- [x] Basic keyboard shortcuts
- [x] Per-monitor DPI awareness
- [x] Dedicated WebView2 user-data directory
- [x] Debug and Release CI plan
- [x] Validate CI build successfully
- [ ] Validate executable artifact launches interactively on Windows

### Browser functionality

- [ ] Tabs
- [ ] New-window handling through tabs
- [ ] Downloads
- [ ] History
- [ ] Favorites
- [ ] Session restore
- [ ] Private mode
- [ ] Site permissions
- [ ] Settings
- [ ] Default-browser registration
- [ ] Installer

### Performance

- [ ] Startup timing instrumentation
- [ ] Tab-switch latency instrumentation
- [ ] Navigation timing instrumentation
- [ ] Background work isolation
- [ ] Tab suspension/discard policy
- [ ] Profile CPU/RAM use
- [ ] Profile cold/warm startup

### Automatic DNS optimizer

- [ ] Detect active network changes
- [ ] Benchmark multiple DNS resolvers
- [ ] Measure real DNS resolution latency, not ICMP ping only
- [ ] Track median, p95, jitter, timeout rate, and failure rate
- [ ] Support DNS-over-HTTPS where technically appropriate
- [ ] Avoid changing global Windows DNS without explicit user action
- [ ] Select resolver only after sufficient samples
- [ ] Add hysteresis to prevent frequent DNS switching
- [ ] Re-test after network/VPN/interface changes

## Completed objective

The first Windows x64 Debug and Release builds compile successfully in GitHub Actions and produce `Nautrix.exe` artifacts.

## Next objective

Validate the executable interactively on Windows, then implement the first real tab model so new-window requests open as tabs instead of replacing the current page.
