#!/usr/bin/env python3
"""Reliable Gitiles source retrieval for pinned Chromium validation."""

from __future__ import annotations

import base64
import binascii
import socket
import time
import urllib.error
import urllib.request

_TRANSIENT_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


def fetch_gitiles_text(
    revision: str,
    path: str,
    *,
    user_agent: str,
    timeout: float = 45.0,
    attempts: int = 4,
) -> str:
    """Fetch and decode one exact pinned Chromium source file.

    Only transport failures and transient HTTP statuses are retried. A stable
    HTTP error or an invalid Gitiles payload still fails immediately, so retry
    logic cannot turn a source mismatch into a passing validation.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    url = f"https://chromium.googlesource.com/chromium/src/+/{revision}/{path}?format=TEXT"
    last_error: BaseException | None = None

    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers={"User-Agent": user_agent})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                encoded = response.read()
            try:
                return base64.b64decode(encoded, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError) as exc:
                raise RuntimeError(f"Invalid Gitiles source response for {path}") from exc
        except urllib.error.HTTPError as exc:
            if exc.code not in _TRANSIENT_HTTP_STATUS:
                raise
            last_error = exc
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
            last_error = exc

        if attempt == attempts:
            break
        delay_seconds = min(2 ** (attempt - 1), 8)
        print(
            f"[Nautrix] Transient upstream fetch failure for {path} "
            f"(attempt {attempt}/{attempts}): {last_error}; retrying in {delay_seconds}s..."
        )
        time.sleep(delay_seconds)

    raise RuntimeError(
        f"Failed to fetch pinned Chromium source after {attempts} attempts: {path}"
    ) from last_error
