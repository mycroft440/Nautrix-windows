# Security policy

## Current status

Nautrix Windows is pre-release software. No build is considered supported for
daily browsing until the full-build, runtime, signing and update gates in
`PLAN.md` are complete.

The only Chromium revision under active development is the revision pinned in
`chromium/VERSION`. Older local builds must be treated as unsupported as soon
as a newer Chromium Stable security release is available.

## Reporting a vulnerability

Do not publish exploitable details in a public issue. Use GitHub's private
vulnerability-reporting flow for this repository when it is available. If the
private form is unavailable, contact the repository owner through the GitHub
profile and request a private channel before sending technical details.

Include the affected Nautrix commit, Windows version, reproduction steps and
whether the issue also reproduces in the pinned unmodified Chromium build.

## Release requirements

A public browser release must not be produced unless it:

- is based on a currently supported Chromium Stable revision;
- passes the full Windows build and clean-user runtime suite;
- is signed with the production Authenticode identity;
- has a tested update and rollback path;
- contains the applicable Chromium and third-party license notices.
