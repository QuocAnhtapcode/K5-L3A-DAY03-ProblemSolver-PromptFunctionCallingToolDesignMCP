---
name: papers
track: bonus
kind: live_api
provider: arXiv API
requires_env: []
inputs: [query, max_results, sort_by]
outputs: [items, total_results]
side_effect: false
---
# papers

Searches arXiv via the official Atom API. Shares a minimum 3-second interval
with `paper_text` for requests in the same process and retries HTTP 429 up to
three total attempts. `ARXIV_USER_AGENT` is optional; an educational default is
provided. Query must be a non-empty string. No API key is needed.
