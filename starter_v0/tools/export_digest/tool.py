from __future__ import annotations

import csv
import io
import ipaddress
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from tools._shared import err


EXPORT_DIR = Path(__file__).resolve().parents[2] / "exported_digests"
_FORMATS = {
    "markdown": (".md", "text/markdown"),
    "json": (".json", "application/json"),
    "csv": (".csv", "text/csv"),
}
_FIELDS = ("title", "url", "source", "summary", "section")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


def _output_name(filename: str, extension: str) -> str:
    if not isinstance(filename, str):
        raise TypeError("filename must be a string")
    if not filename:
        return f"research-digest-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}{extension}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}(?:\.[A-Za-z]+)?", filename):
        raise ValueError("filename must be a plain ASCII basename without paths (maximum 80 stem characters)")
    path = Path(filename)
    if path.stem.lower() in _RESERVED:
        raise ValueError("filename is a reserved device name")
    if path.suffix and path.suffix.lower() != extension:
        raise ValueError(f"filename extension must be {extension} for the selected format")
    return filename if path.suffix else filename + extension


def _safe_csv(value: str) -> str:
    # Spreadsheet apps may execute cells starting with these characters as formulas.
    dangerous = value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))
    return "'" + value if dangerous else value


def _markdown_text(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", value).replace("\n", " ").replace("\r", " ")


def _render(items: list[dict[str, Any]], selected_format: str) -> bytes:
    if selected_format == "json":
        return (json.dumps(items, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if selected_format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=_FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow({key: _safe_csv(item.get(key) or "") for key in _FIELDS})
        # BOM helps Excel display Vietnamese text correctly.
        return stream.getvalue().encode("utf-8-sig")
    lines = ["# Research digest", ""]
    for index, item in enumerate(items, start=1):
        title = _markdown_text(item.get("title") or f"Item {index}")
        lines.append(f"## {index}. {title}")
        if item.get("summary"):
            lines.extend(["", _markdown_text(item["summary"])])
        if item.get("url"):
            lines.extend(["", f"Source: <{item['url']}>"])
        elif item.get("source"):
            lines.extend(["", f"Source: {_markdown_text(item['source'])} (URL not supplied)"])
        lines.append("")
    return ("\n".join(lines) + "\n").encode("utf-8")


def export_digest(items: list[dict[str, Any]] | None = None, format: str = "markdown", filename: str = "") -> dict[str, Any]:
    """Write supplied research items to a new file in a fixed local export folder."""
    created: Path | None = None
    try:
        if not isinstance(items, list):
            raise TypeError("items must be a list of objects")
        if not isinstance(format, str) or format not in _FORMATS:
            raise ValueError("format must be markdown, json, or csv")
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise TypeError(f"items[{index}] must be an object")
            for key in _FIELDS:
                if item.get(key) is not None and not isinstance(item[key], str):
                    raise TypeError(f"items[{index}].{key} must be a string")
            if item.get("url"):
                url = item["url"]
                parsed = urlsplit(url)
                if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or any(char.isspace() or char in "<>\x00" for char in url):
                    raise ValueError(f"items[{index}].url must be an absolute HTTP(S) URL")
                if parsed.username is not None or parsed.password is not None:
                    raise ValueError(f"items[{index}].url must not contain credentials")
                _ = parsed.port
                host = parsed.hostname.encode("idna").decode("ascii").rstrip(".")
                try:
                    ipaddress.ip_address(host)
                except ValueError:
                    if len(host) > 253 or not all(_HOST_LABEL.fullmatch(label) for label in host.split(".")):
                        raise ValueError(f"items[{index}].url hostname is invalid")

        extension, mime_type = _FORMATS[format]
        name = _output_name(filename, extension)
        payload = _render(items, format)
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        root = EXPORT_DIR.resolve()
        target = (root / name).resolve()
        if target.parent != root:
            raise ValueError("Export must remain inside exported_digests")
        # Never overwrite an existing export. Build bytes first so serialization
        # errors cannot leave an incomplete file behind.
        with target.open("xb") as stream:
            created = target
            stream.write(payload)
        return {
            "tool": "export_digest",
            "path": str(target),
            "filename": name,
            "format": format,
            "mime_type": mime_type,
            "item_count": len(items),
            "bytes_written": len(payload),
        }
    except Exception as exc:
        if created is not None:
            try:
                created.unlink(missing_ok=True)
            except OSError:
                pass
        return err("export_digest", exc)
