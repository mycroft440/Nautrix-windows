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
- [ ] Validate CI build successfully
- [ ] Validate executable artifact launches on Windows

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

## Next objective

Get the first Windows x64 Debug and Release builds green in GitHub Actions, fix all compiler/linker issues found by CI, and review the executable foundation before starting tabs.
