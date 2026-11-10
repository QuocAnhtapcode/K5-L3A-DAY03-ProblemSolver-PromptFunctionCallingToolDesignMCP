from __future__ import annotations

import ipaddress
import re
from collections import Counter
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from tools._shared import err


_SOCIAL_DOMAINS = {"x.com", "twitter.com", "facebook.com", "reddit.com", "tiktok.com", "linkedin.com"}
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)
_CAVEAT = (
    "This is an offline audit of supplied URLs and metadata, not fact checking. "
    "Domain categories are origin hints; arXiv is a preprint repository. "
    "Declared official domains are supplied by the caller and are not independently verified. "
    "Different domains do not necessarily represent independent sources."
)


def _matches_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _domain(value: str) -> tuple[str, str]:
    if any(char.isspace() for char in value) or any(char in value for char in "<>\x00"):
        raise ValueError("URL contains whitespace or invalid characters")
    parsed = urlsplit(value)
    host = parsed.hostname
    if parsed.scheme.lower() not in {"http", "https"} or not host:
        raise ValueError("URL must be absolute and use http or https")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are not accepted")
    _ = parsed.port
    try:
        host = host.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError as exc:
        raise ValueError("URL hostname is invalid") from exc
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if len(host) > 253 or not all(_HOST_LABEL.fullmatch(label) for label in host.split(".")):
            raise ValueError("URL hostname is invalid")
    # Ignore fragments while retaining query/path distinctions for this audit.
    key = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))
    return host, key


def audit_sources(items: list[dict[str, Any]] | None = None, official_domains: list[str] | None = None) -> dict[str, Any]:
    """Describe citation gaps and source origins without claiming verification."""
    try:
        if not isinstance(items, list):
            raise TypeError("items must be a list of objects")
        if official_domains is None:
            official_domains = []
        if not isinstance(official_domains, list):
            raise TypeError("official_domains must be a list of hostnames")
        official: set[str] = set()
        for value in official_domains:
            if not isinstance(value, str) or not value.strip() or any(char in value for char in "/:@?# "):
                raise ValueError("official_domains must contain hostnames only, without scheme or path")
            host, _ = _domain("https://" + value.strip().lower())
            official.add(host)

        audited: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        domains: set[str] = set()
        categories: Counter[str] = Counter()
        missing = invalid = duplicates = 0
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise TypeError(f"items[{index}] must be an object")
            url = item.get("url")
            issues: list[str] = []
            host = ""
            category = "missing_url"
            if url is None or (isinstance(url, str) and not url.strip()):
                missing += 1
                issues.append("missing_url")
            elif not isinstance(url, str):
                invalid += 1
                category = "invalid_url"
                issues.append("invalid_url")
            else:
                try:
                    host, key = _domain(url.strip())
                except (UnicodeError, ValueError):
                    invalid += 1
                    category = "invalid_url"
                    issues.append("invalid_url")
                else:
                    domains.add(host)
                    if key in seen_urls:
                        duplicates += 1
                        issues.append("duplicate_url")
                    seen_urls.add(key)
                    if _matches_domain(host, "arxiv.org"):
                        category = "preprint"
                        issues.append("peer_review_not_established")
                    elif any(_matches_domain(host, domain) for domain in _SOCIAL_DOMAINS):
                        category = "social"
                        issues.append("social_signal_requires_corroboration")
                    elif any(_matches_domain(host, domain) for domain in official):
                        category = "declared_official"
                    else:
                        category = "other_web"
            categories[category] += 1
            audited.append({**item, "audit": {"domain": host, "category": category, "issues": issues}})

        return {
            "tool": "source_audit",
            "items": audited,
            "item_count": len(audited),
            "domain_count": len(domains),
            "domains": sorted(domains),
            "missing_url_count": missing,
            "invalid_url_count": invalid,
            "duplicate_url_count": duplicates,
            "category_counts": dict(sorted(categories.items())),
            "caveat": _CAVEAT,
        }
    except Exception as exc:
        return err("source_audit", exc)
