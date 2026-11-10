from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlsplit

from tools._shared import err


def _url_key(value: Any) -> tuple[Any, ...]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Each item must provide a non-empty HTTP(S) URL")

    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname
    if scheme not in {"http", "https"} or not hostname:
        raise ValueError("Each item URL must be absolute and use http or https")

    # Accessing .port also validates malformed or out-of-range ports.
    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80

    query = tuple(
        (name, content)
        for name, content in parse_qsl(parsed.query, keep_blank_values=True)
        if not name.lower().startswith("utm_")
        and name.lower() not in {"fbclid", "gclid"}
    )
    return (
        scheme,
        hostname.lower(),
        port,
        parsed.username,
        parsed.password,
        parsed.path or "/",
        query,
    )


def deduplicate_items(items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Keep the first item per normalized URL without modifying source items."""
    try:
        if not isinstance(items, list):
            raise TypeError("items must be a list of objects")

        seen: set[tuple[Any, ...]] = set()
        unique: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise TypeError(f"items[{index}] must be an object")
            key = _url_key(item.get("url"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(dict(item))

        return {
            "tool": "deduplicate",
            "items": unique,
            "input_count": len(items),
            "output_count": len(unique),
            "duplicates_removed": len(items) - len(unique),
        }
    except Exception as exc:
        return err("deduplicate", exc)
