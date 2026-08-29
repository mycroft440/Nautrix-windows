# Third-party notices and binary distribution gate

Nautrix Windows is a downstream Chromium-based project. Chromium is licensed
under the BSD 3-Clause license and contains third-party components distributed
under their own licenses. The authoritative notices for a produced browser are
the license and credits files generated from the exact pinned Chromium source
and exposed by that build through `chrome://credits`.

Source:

- https://chromium.googlesource.com/chromium/src/
- https://www.chromium.org/

The Nautrix source license does not replace any license, attribution, patent or
redistribution obligation attached to Chromium, FFmpeg, codecs, Widevine or
other packaged components. Before publishing a binary, the release job must
archive the generated third-party notices beside the installer and verify that
`chrome://credits` is available in the installed browser.

Proprietary codecs and Widevine must not be enabled or redistributed until the
project has documented the applicable rights and a runtime test has confirmed
the intended behavior.
