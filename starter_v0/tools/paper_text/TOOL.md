---
name: paper_text
track: bonus
kind: live_api
provider: arXiv + pypdf
requires_env: []
inputs: [arxiv_url, max_pages, max_chars]
outputs: [items, pdf_path, txt_path, page_count]
side_effect: local_file_write
---
# paper_text

Downloads an arXiv PDF and extracts text locally with `pypdf`. Output is saved
under `starter_v0/arxiv_papers/`.

Shares a minimum 3-second in-process interval with `papers`. Retries HTTP 429
up to three total attempts, validates the PDF signature, and publishes the local
PDF only after the download finishes. Partial files are removed on error.
`ARXIV_USER_AGENT` is optional; no API key is needed.
