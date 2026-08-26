# Full build and runtime automation

Standard GitHub-hosted Windows runners are intentionally used only for lightweight source/patch/native-tool validation. A complete Chromium build requires substantially more storage and memory.

## Self-hosted runner label

Attach a capable Windows x64 runner with labels:

```text
self-hosted
Windows
X64
nautrix-chromium
```

Then run the `Full Chromium Build` workflow and select `baseline` or `pgo`.

The workflow builds Chromium, builds the native Nautrix launcher/settings tools, executes the non-interactive runtime smoke checks, packages the browser, and uploads the resulting artifact.

## Runtime regression

The `Runtime Regression` workflow accepts the absolute path of an already-built `chrome.exe` on that runner and runs smoke, navigation, and process-resource measurements.

Interactive tests such as entering Google account credentials remain manual by design; automation must not store or inject a user's account password.
