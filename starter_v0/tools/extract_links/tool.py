from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlsplit

from tools._shared import err


_CANDIDATE = re.compile(r"https?://[^\s<>\"\x00-\x1f]+", re.IGNORECASE)
_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


def _trim_url(candidate: str) -> str:
    # Keep balanced parentheses in URLs such as Wikipedia article paths.
    value = candidate.rstrip(".,;:!?，。；：！？'\u2019\u201d")
    for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
        while value.endswith(closing) and value.count(closing) > value.count(opening):
            value = value[:-1]
    return value.rstrip(".,;:!?，。；：！？")


def _valid_url(value: str) -> tuple[bool, str]:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme.lower() not in {"http", "https"} or not host:
            return False, ""
        if parsed.username is not None or parsed.password is not None:
            return False, ""
        # Reading .port rejects non-numeric and out-of-range ports.
        _ = parsed.port
        try:
            ipaddress.ip_address(host)
        except ValueError:
            encoded = host.encode("idna").decode("ascii").rstrip(".")
            if len(encoded) > 253 or not all(_LABEL.fullmatch(label) for label in encoded.split(".")):
                return False, ""
        return True, host.lower()
    except (UnicodeError, ValueError):
        return False, ""


def extract_links(text: str = "", max_links: int = 50) -> dict[str, Any]:
    """Extract distinct HTTP(S) links from supplied text without accessing them."""
    try:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if type(max_links) is not int or not 1 <= max_links <= 200:
            raise ValueError("max_links must be an integer between 1 and 200")

        seen: set[str] = set()
        items: list[dict[str, str]] = []
        candidates_seen = 0
        rejected_count = 0
        unique_count = 0
        for match in _CANDIDATE.finditer(text):
            candidates_seen += 1
            url = _trim_url(match.group())
            valid, host = _valid_url(url)
            if not valid:
                rejected_count += 1
                continue
            if url in seen:
                continue
            seen.add(url)
            unique_count += 1
            if len(items) < max_links:
                items.append({"url": url, "title": url, "source": host})

        return {
            "tool": "extract_links",
            "items": items,
            "link_count": len(items),
            "unique_link_count": unique_count,
            "candidates_seen": candidates_seen,
            "rejected_count": rejected_count,
            "truncated": unique_count > len(items),
        }
    except Exception as exc:
        return err("extract_links", exc)
