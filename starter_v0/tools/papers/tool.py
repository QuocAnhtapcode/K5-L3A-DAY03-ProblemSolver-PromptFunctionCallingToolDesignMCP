from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from tools._shared import err
from tools.papers._http import arxiv_get as _arxiv_get


ARXIV_API_URL = "https://export.arxiv.org/api/query"


def _arxiv_search_query(query: str) -> str:
    cleaned = " ".join((query or "").split())
    if ":" in cleaned:
        return cleaned
    terms = [term for term in re.findall(r"[A-Za-z0-9_\\-]+", cleaned) if len(term) > 1]
    return " AND ".join(f"all:{term}" for term in terms[:8]) or cleaned


def _arxiv_id(value: str) -> str:
    match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", value or "")
    return match.group(1) if match else ""


def _entry_text(entry: ET.Element, path: str, namespaces: dict[str, str]) -> str:
    node = entry.find(path, namespaces)
    return (node.text or "").strip() if node is not None and node.text else ""


def arxiv_search(query: str = "", max_results: int = 5, sort_by: str = "relevance") -> dict[str, Any]:
    try:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        max_results = max(1, min(int(max_results or 5), 10))
        sort_by = sort_by if sort_by in {"relevance", "lastUpdatedDate", "submittedDate"} else "relevance"
        params = {
            "search_query": _arxiv_search_query(query),
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": "descending",
        }
        response = _arxiv_get(ARXIV_API_URL, params=params)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        namespaces = {
            "atom": "http://www.w3.org/2005/Atom",
            "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        total_node = root.find(".//opensearch:totalResults", namespaces)
        entries: list[dict[str, Any]] = []
        for entry in root.findall(".//atom:entry", namespaces):
            abs_url = _entry_text(entry, "./atom:id", namespaces)
            arxiv_id = _arxiv_id(abs_url)
            links = [{"rel": link.get("rel"), "href": link.get("href"), "title": link.get("title")} for link in entry.findall("./atom:link", namespaces)]
            pdf_url = next((link["href"] for link in links if link.get("title") == "pdf"), f"https://arxiv.org/pdf/{arxiv_id}.pdf")
            primary = entry.find("./arxiv:primary_category", namespaces)
            summary = _entry_text(entry, "./atom:summary", namespaces).replace("\n", " ")
            entries.append({
                "arxiv_id": arxiv_id,
                "title": _entry_text(entry, "./atom:title", namespaces).replace("\n", " "),
                "summary": " ".join(summary.split()),
                "authors": [_entry_text(author, "./atom:name", namespaces) for author in entry.findall("./atom:author", namespaces)],
                "published": _entry_text(entry, "./atom:published", namespaces),
                "updated": _entry_text(entry, "./atom:updated", namespaces),
                "url": abs_url,
                "pdf_url": pdf_url,
                "source": "arxiv.org",
                "primary_category": primary.get("term") if primary is not None else None,
                "categories": [cat.get("term") for cat in entry.findall("./atom:category", namespaces)],
            })
        return {
            "tool": "arxiv_search",
            "query": query,
            "api_query": params["search_query"],
            "total_results": int(total_node.text) if total_node is not None and total_node.text else None,
            "items": entries,
            "rate_limit_note": "arXiv may return 429 if called too frequently; this tool waits at least 3 seconds between requests in-process.",
        }
    except Exception as exc:
        return err("arxiv_search", exc)

