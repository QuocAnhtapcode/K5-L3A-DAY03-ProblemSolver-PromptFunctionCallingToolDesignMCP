from __future__ import annotations

import copy
import csv
import importlib
import io
import json
from pathlib import Path

import pytest

from tools.extract_links.tool import extract_links
from tools.source_audit.tool import audit_sources


export_module = importlib.import_module("tools.export_digest.tool")


def test_extract_links_preserves_order_and_balanced_parentheses_without_fetching() -> None:
    text = "[Wiki](https://en.wikipedia.org/wiki/Function_(mathematics)). Then <https://example.org/a?x=1>. Again https://example.org/a?x=1."

    result = extract_links(text)

    assert [item["url"] for item in result["items"]] == [
        "https://en.wikipedia.org/wiki/Function_(mathematics)",
        "https://example.org/a?x=1",
    ]
    assert result["items"][0]["source"] == "en.wikipedia.org"
    assert result["unique_link_count"] == 2
    assert result["truncated"] is False


def test_extract_links_reports_limit_without_conflating_unique_count() -> None:
    result = extract_links("https://one.example/a https://two.example/b https://three.example/c", max_links=2)

    assert result["link_count"] == 2
    assert result["unique_link_count"] == 3
    assert result["truncated"] is True


def test_extract_links_rejects_malformed_ports_hosts_and_embedded_credentials() -> None:
    result = extract_links("https://a.example:99999/a https://bad..example/a https://name:secret@example.org/x https://valid.example/x")

    assert result["rejected_count"] == 3
    assert [item["url"] for item in result["items"]] == ["https://valid.example/x"]


@pytest.mark.parametrize("text,limit", [(None, 5), ([], 5), ("text", 0), ("text", True), ("text", "5"), ("text", 201)])
def test_extract_links_bad_model_arguments_return_error_dict(text, limit) -> None:
    result = extract_links(text, max_links=limit)

    assert result["tool"] == "extract_links"
    assert result["error"] in {"TypeError", "ValueError"}
    assert "items" not in result


def test_extract_links_empty_text_is_a_valid_empty_result() -> None:
    result = extract_links("")

    assert result["items"] == []
    assert result["link_count"] == result["candidates_seen"] == 0


def test_source_audit_counts_gaps_origins_and_duplicates_without_mutating_items() -> None:
    items = [
        {"title": "Official", "url": "https://docs.example.org/a", "metadata": {"language": "vi"}},
        {"url": "https://arxiv.org/abs/1706.03762"},
        {"url": "https://x.com/alice/status/1"},
        {"title": "Missing"},
        {"url": "javascript:alert(1)"},
        {"url": "https://docs.example.org/a#intro"},
    ]
    original = copy.deepcopy(items)

    result = audit_sources(items, official_domains=["example.org"])

    assert items == original
    assert result["domain_count"] == 3
    assert result["missing_url_count"] == result["invalid_url_count"] == result["duplicate_url_count"] == 1
    assert result["category_counts"] == {"declared_official": 2, "invalid_url": 1, "missing_url": 1, "preprint": 1, "social": 1}
    assert result["items"][0]["metadata"] == {"language": "vi"}
    assert "peer_review_not_established" in result["items"][1]["audit"]["issues"]
    assert "not fact checking" in result["caveat"]


def test_source_audit_domain_suffix_does_not_accept_impersonation() -> None:
    result = audit_sources([
        {"url": "https://docs.openai.com/research"},
        {"url": "https://openai.com.evil.example/research"},
    ], official_domains=["openai.com"])

    assert [item["audit"]["category"] for item in result["items"]] == ["declared_official", "other_web"]


def test_source_audit_social_or_preprint_is_not_promoted_to_verified_by_caller() -> None:
    result = audit_sources([
        {"url": "https://arxiv.org/abs/1706.03762"},
        {"url": "https://x.com/alice/status/1"},
    ], official_domains=["arxiv.org", "x.com"])

    assert result["category_counts"] == {"preprint": 1, "social": 1}
    assert "independently verified" in result["caveat"]


@pytest.mark.parametrize("items,domains", [(None, []), (["text"], []), ([], "openai.com"), ([], ["https://openai.com"]), ([], [None]), ([], ["a..example"])])
def test_source_audit_bad_model_arguments_return_error_dict(items, domains) -> None:
    result = audit_sources(items, official_domains=domains)

    assert result["tool"] == "source_audit"
    assert result["error"] in {"TypeError", "ValueError"}


def test_source_audit_marks_non_string_url_invalid_and_accepts_empty_list() -> None:
    result = audit_sources([{"url": 123}, {"url": "https://example.org:99999/a"}])

    assert result["invalid_url_count"] == 2
    assert audit_sources([])["domain_count"] == 0


@pytest.fixture
def export_dir(monkeypatch, tmp_path):
    target = tmp_path / "exported_digests"
    monkeypatch.setattr(export_module, "EXPORT_DIR", target)
    return target


@pytest.mark.parametrize("file_format,extension,mime", [("markdown", ".md", "text/markdown"), ("json", ".json", "application/json"), ("csv", ".csv", "text/csv")])
def test_export_digest_writes_readable_requested_format_inside_export_dir(export_dir, file_format, extension, mime) -> None:
    items = [{"title": "Tin AI tiếng Việt", "url": "https://example.org/ai", "source": "example.org", "summary": "Bằng chứng có nguồn."}]

    result = export_module.export_digest(items, format=file_format, filename="weekly-ai")

    path = Path(result["path"])
    assert path.parent == export_dir.resolve()
    assert path.name == "weekly-ai" + extension
    assert result["mime_type"] == mime
    assert result["bytes_written"] == path.stat().st_size
    assert result["item_count"] == 1
    if file_format == "json":
        assert json.loads(path.read_text(encoding="utf-8")) == items
    elif file_format == "csv":
        assert list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))[0]["title"] == "Tin AI tiếng Việt"
    else:
        assert "Source: <https://example.org/ai>" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("filename", ["../outside", "..\\outside", "/outside", "C:\\outside", "CON", "NUL.json", "report.txt", "bad name", "a" * 81])
def test_export_digest_rejects_unsafe_names_before_writing(export_dir, filename) -> None:
    result = export_module.export_digest([{"title": "A"}], format="json", filename=filename)

    assert result["error"] == "ValueError"
    assert "path" not in result
    assert not export_dir.exists()


def test_export_digest_never_overwrites_an_existing_export(export_dir) -> None:
    first = export_module.export_digest([{"title": "First"}], format="json", filename="same")
    original = Path(first["path"]).read_bytes()

    second = export_module.export_digest([{"title": "Second"}], format="json", filename="same")

    assert second["error"] == "FileExistsError"
    assert Path(first["path"]).read_bytes() == original


def test_export_digest_csv_escapes_formula_cells(export_dir) -> None:
    result = export_module.export_digest([{"title": '=HYPERLINK("https://example.org")', "summary": "  +cmd"}], format="csv")

    rows = list(csv.DictReader(io.StringIO(Path(result["path"]).read_text(encoding="utf-8-sig"))))

    assert rows[0]["title"].startswith("'=")
    assert rows[0]["summary"].startswith("'  +")


def test_export_digest_filesystem_failure_returns_error_not_success(monkeypatch, export_dir) -> None:
    def denied(*args, **kwargs):
        raise PermissionError("read-only test folder")

    monkeypatch.setattr(Path, "mkdir", denied)

    result = export_module.export_digest([{"title": "A"}])

    assert result["error"] == "PermissionError"
    assert "path" not in result


@pytest.mark.parametrize("items,file_format", [(None, "json"), (["bad"], "json"), ([{"title": 4}], "json"), ([{"url": "file:///secret"}], "json"), ([], "pdf"), ([{"metadata": object()}], "json")])
def test_export_digest_bad_input_or_serialization_returns_error_without_partial_file(export_dir, items, file_format) -> None:
    result = export_module.export_digest(items, format=file_format)

    assert "error" in result
    assert "path" not in result
    assert not export_dir.exists()


def test_export_digest_empty_data_can_be_downloaded_as_json(export_dir) -> None:
    result = export_module.export_digest([], format="json")

    assert result["item_count"] == 0
    assert json.loads(Path(result["path"]).read_text(encoding="utf-8")) == []
