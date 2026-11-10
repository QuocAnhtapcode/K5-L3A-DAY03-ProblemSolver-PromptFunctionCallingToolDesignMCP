from __future__ import annotations

from typing import Any
from urllib.parse import unquote_plus, urlsplit

from tools._shared import err


def _url_key(url: Any) -> tuple[str, str, str, tuple[str, ...]]:
    if not isinstance(url, str) or not url:
        raise ValueError("Each item must have a nonblank HTTP/HTTPS URL")
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url):
        raise ValueError("Each item must have a nonblank HTTP/HTTPS URL without whitespace or control characters")

    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Each item URL must have an HTTP/HTTPS scheme and hostname")
    parsed.port  # Accessing this property validates port syntax and range.
    userinfo, separator, authority = parsed.netloc.rpartition("@")
    if "\\" in url or authority.endswith(":"):
        raise ValueError("Each item URL must have a valid hostname and port")

    query_parts = []
    for part in parsed.query.split("&") if parsed.query else []:
        name = unquote_plus(part.partition("=")[0]).lower()
        if not name.startswith("utm_") and name not in {"fbclid", "gclid"}:
            query_parts.append(part)

    netloc = userinfo + separator + authority.lower()
    return parsed.scheme.lower(), netloc, parsed.path, tuple(query_parts)


def deduplicate_sources(items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    try:
        if not isinstance(items, list):
            raise TypeError("items must be a list of source dictionaries")

        unique_items = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                raise TypeError("Each item must be a source dictionary")
            key = _url_key(item.get("url"))
            if key not in seen:
                seen.add(key)
                unique_items.append(item.copy())

        return {
            "tool": "deduplicate",
            "items": unique_items,
            "input_count": len(items),
            "item_count": len(unique_items),
            "removed_count": len(items) - len(unique_items),
        }
    except Exception as exc:
        return err("deduplicate", exc)
