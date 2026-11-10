"""Offline regressions for the existing arXiv bonus tools."""
from __future__ import annotations

from pathlib import Path

import pytest
import requests

from tools.papers import _http
from tools.papers import tool as papers
from tools.paper_text import tool as paper_text


ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
 xmlns:arxiv="http://arxiv.org/schemas/atom">
 <opensearch:totalResults>1</opensearch:totalResults>
 <entry><id>http://arxiv.org/abs/1706.03762v7</id>
 <title>Attention Is All You Need</title><summary>First line\nsecond line.</summary>
 <author><name>A. Researcher</name></author>
 <published>2017-06-12</published><updated>2023-08-02</updated>
 <link title="pdf" href="https://arxiv.org/pdf/1706.03762v7"/>
 <arxiv:primary_category term="cs.CL"/><category term="cs.CL"/>
 </entry></feed>"""


class Response:
    def __init__(self, *, status=200, text=ATOM, chunks=None, headers=None):
        self.status_code = status
        self.text = text
        self.chunks = chunks if chunks is not None else [b"%PDF-1.7\nmock content"]
        self.headers = headers or {}
        self.closed = False

    def close(self):
        self.closed = True

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        for chunk in self.chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


@pytest.fixture
def clock(monkeypatch):
    state = {"now": 100.0, "sleeps": []}

    def sleep(seconds):
        state["sleeps"].append(seconds)
        state["now"] += seconds

    monkeypatch.setattr(_http, "_last_request_at", None)
    monkeypatch.setattr(_http.time, "monotonic", lambda: state["now"])
    monkeypatch.setattr(_http.time, "sleep", sleep)
    return state


@pytest.mark.parametrize("query", ["", "   ", None, ["AI"]])
def test_papers_rejects_empty_or_non_string_query_without_network(query, fake_http):
    calls = fake_http(Response())

    result = papers.arxiv_search(query=query)

    assert result["error"] == "ValueError"
    assert calls == []


def test_papers_maps_atom_fields_and_sends_query_params(fake_http, clock):
    response = Response()
    calls = fake_http(response)

    result = papers.arxiv_search("AI agent evaluation", max_results=1)

    assert calls[0]["url"] == papers.ARXIV_API_URL
    assert calls[0]["params"] == {
        "search_query": "all:AI AND all:agent AND all:evaluation",
        "max_results": 1, "sortBy": "relevance", "sortOrder": "descending",
    }
    assert result["total_results"] == 1
    assert result["items"][0]["arxiv_id"] == "1706.03762v7"
    assert result["items"][0]["authors"] == ["A. Researcher"]
    assert result["items"][0]["summary"] == "First line second line."
    assert result["items"][0]["primary_category"] == "cs.CL"


def test_discovery_and_pdf_share_one_request_interval(monkeypatch, tmp_path, clock):
    started = []

    def get(url, **kwargs):
        started.append((url, clock["now"]))
        return Response()

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(paper_text, "ARXIV_DIR", tmp_path)
    monkeypatch.setattr(paper_text, "_extract_pdf_text", lambda path, max_pages: ("actual excerpt", 15))

    assert "error" not in papers.arxiv_search("attention", max_results=1)
    assert "error" not in paper_text.get_arxiv_paper_text("1706.03762", max_pages=1)

    assert len(started) == 2
    assert started[1][1] - started[0][1] >= 3.0
    assert clock["sleeps"] == [3.0]


def test_pdf_retries_429_then_saves_valid_pdf_and_excerpt(monkeypatch, tmp_path, clock):
    limited = Response(status=429, headers={"Retry-After": "4"})
    okay = Response()
    responses = iter([limited, okay])
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return next(responses)

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(paper_text, "ARXIV_DIR", tmp_path)
    monkeypatch.setattr(paper_text, "_extract_pdf_text", lambda path, max_pages: ("excerpt " * 300, 15))

    result = paper_text.get_arxiv_paper_text("https://arxiv.org/abs/1706.03762", max_pages=1, max_chars=1000)

    assert len(calls) == 2
    assert calls[0][0] == "https://arxiv.org/pdf/1706.03762.pdf"
    assert calls[0][1]["stream"] is True
    assert limited.closed and okay.closed
    assert clock["sleeps"] == [4.0]
    assert result["pages_read"] == 1
    assert result["chars_returned"] == 1000
    assert Path(result["pdf_path"]).read_bytes().startswith(b"%PDF-")
    assert Path(result["txt_path"]).read_text(encoding="utf-8") == ("excerpt " * 300)[:1000]
    assert not list(tmp_path.glob("*.part"))


def test_pdf_exhausted_rate_limit_is_an_error_not_a_saved_pdf(monkeypatch, tmp_path, clock):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return Response(status=429)

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(paper_text, "ARXIV_DIR", tmp_path)

    result = paper_text.get_arxiv_paper_text("1706.03762")

    assert result["error"] == "HTTPError"
    assert len(calls) == 3
    assert list(tmp_path.iterdir()) == []


def test_pdf_rejects_html_and_removes_partial_download(monkeypatch, tmp_path, fake_http, clock):
    response = Response(chunks=[b"<html>service unavailable</html>"])
    fake_http(response)
    monkeypatch.setattr(paper_text, "ARXIV_DIR", tmp_path)

    result = paper_text.get_arxiv_paper_text("1706.03762")

    assert result["error"] == "ValueError"
    assert response.closed
    assert list(tmp_path.iterdir()) == []


def test_interrupted_pdf_keeps_previous_file_and_cleans_partial(monkeypatch, tmp_path, fake_http, clock):
    original = tmp_path / "1706.03762.pdf"
    original.write_bytes(b"%PDF-original")
    fake_http(Response(chunks=[b"%PDF-partial", requests.ConnectionError("interrupted")]))
    monkeypatch.setattr(paper_text, "ARXIV_DIR", tmp_path)

    result = paper_text.get_arxiv_paper_text("1706.03762")

    assert result["error"] == "ConnectionError"
    assert original.read_bytes() == b"%PDF-original"
    assert list(tmp_path.glob("*.part")) == []


@pytest.mark.parametrize("value", ["not an arxiv id", "", None, 1706])
def test_pdf_bad_id_does_not_call_network(value, fake_http):
    calls = fake_http(Response())

    result = paper_text.get_arxiv_paper_text(value)

    assert result["error"] == "ValueError"
    assert calls == []
