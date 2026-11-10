from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools._shared import ROOT, err
from tools.papers._http import arxiv_get


ARXIV_DIR = ROOT / "arxiv_papers"


def _arxiv_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("arxiv_url must be an arXiv ID or URL string")
    match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", value or "")
    if not match:
        raise ValueError("Invalid arXiv ID or URL")
    return match.group(1)


def _download_arxiv_pdf(arxiv_url: str) -> tuple[str, Path, str]:
    arxiv_id = _arxiv_id(arxiv_url)
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    ARXIV_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ARXIV_DIR / f"{arxiv_id}.pdf"
    response = arxiv_get(pdf_url, stream=True)
    pending_path = output_path.with_suffix(".pdf.part")
    try:
        response.raise_for_status()
        with pending_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
        with pending_path.open("rb") as file:
            if file.read(5) != b"%PDF-":
                raise ValueError("arXiv did not return a PDF document")
        pending_path.replace(output_path)
    finally:
        response.close()
        pending_path.unlink(missing_ok=True)
    return arxiv_id, output_path, pdf_url


def _extract_pdf_text(pdf_path: Path, max_pages: int) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf first: pip install pypdf") from exc

    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)
    pages_to_read = min(max(1, int(max_pages or 5)), page_count)
    parts: list[str] = []
    for page in reader.pages[:pages_to_read]:
        parts.append(page.extract_text() or "")
    return "\n\n".join(part for part in parts if part.strip()), page_count


def get_arxiv_paper_text(arxiv_url: str = "", max_pages: int = 5, max_chars: int = 8000) -> dict[str, Any]:
    try:
        arxiv_id, pdf_path, pdf_url = _download_arxiv_pdf(arxiv_url)
        text, page_count = _extract_pdf_text(pdf_path, max_pages=max_pages)
        max_chars = max(1000, min(int(max_chars or 8000), 20000))
        excerpt = text[:max_chars]
        txt_path = pdf_path.with_suffix(".txt")
        txt_path.write_text(excerpt, encoding="utf-8")
        return {
            "tool": "get_arxiv_paper_text",
            "arxiv_id": arxiv_id,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "pdf_url": pdf_url,
            "pdf_path": str(pdf_path),
            "txt_path": str(txt_path),
            "page_count": page_count,
            "pages_read": min(max(1, int(max_pages or 5)), page_count),
            "chars_returned": len(excerpt),
            "items": [{
                "title": f"arXiv paper {arxiv_id}",
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "source": "arxiv.org",
                "summary": excerpt,
            }],
        }
    except Exception as exc:
        return err("get_arxiv_paper_text", exc)

