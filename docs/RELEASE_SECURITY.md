# Nautrix release and security gates

## Version intake

The scheduled Chromium Stable watcher compares `chromium/VERSION` with the
official Windows Stable version-history service and opens or updates one GitHub
issue when the pin is behind. A platform-specific fourth version component that
is newer than the service response is accepted. The alert is not an automatic source upgrade: every new
revision must still pass the exact-anchor patch validators and the complete
Windows build.

## Signing

Development and test packages may remain unsigned only when they are clearly
labeled as such. A public release requires Authenticode signatures on the
installer, browser executable and Nautrix native helpers. The signing key must
be supplied by a protected release environment; it must never be committed or
stored in a general-purpose self-hosted runner workspace.

## Updates and rollback

The current open-Chromium installer has no production update channel. Until a
signed updater exists, Nautrix is not ready for public daily use. The eventual
updater must provide:

- a signed update manifest transported over HTTPS;
- cryptographic verification before installation;
- atomic replacement with browser restart coordination;
- protection against version downgrade outside an explicit rollback window;
- rollback to the last known-good signed build;
- staged rollout and the ability to stop a bad release;
- cleanup of obsolete versions without deleting the user profile.

## Release evidence

Each release must retain the source commit, Chromium revision, build logs,
checksums, signatures, third-party notices and clean-machine install/runtime/
uninstall results. A GitHub Actions success that only validates patch anchors is
not release evidence for the complete browser.
