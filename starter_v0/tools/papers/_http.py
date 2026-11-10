"""One in-process arXiv request budget shared by discovery and PDF reading."""
from __future__ import annotations

import os
import threading
import time
from typing import Any

import requests

from tools._shared import TIMEOUT


MIN_INTERVAL_SECONDS = 3.0
MAX_ATTEMPTS = 3
_lock = threading.Lock()
_last_request_at: float | None = None


def _wait_for_slot() -> None:
    global _last_request_at
    with _lock:
        now = time.monotonic()
        if _last_request_at is not None:
            wait = MIN_INTERVAL_SECONDS - (now - _last_request_at)
            if wait > 0:
                time.sleep(wait)
        _last_request_at = time.monotonic()


def arxiv_get(url: str, *, params: dict[str, Any] | None = None, stream: bool = False) -> requests.Response:
    """Try up to three times on HTTP 429, spacing requests across both tools."""
    user_agent = os.getenv(
        "ARXIV_USER_AGENT",
        "AI20k-Day03-Research-Agent/1.0 (educational lab; contact: local)",
    )
    for attempt in range(MAX_ATTEMPTS):
        _wait_for_slot()
        response = requests.get(
            url, params=params, headers={"User-Agent": user_agent},
            timeout=TIMEOUT, stream=stream,
        )
        if response.status_code != 429 or attempt == MAX_ATTEMPTS - 1:
            return response
        response.close()
        retry_after = response.headers.get("Retry-After", "")
        try:
            delay = max(MIN_INTERVAL_SECONDS, min(float(retry_after), 30.0))
        except (TypeError, ValueError):
            delay = MIN_INTERVAL_SECONDS * (attempt + 1)
        time.sleep(delay)
    raise AssertionError("unreachable")
