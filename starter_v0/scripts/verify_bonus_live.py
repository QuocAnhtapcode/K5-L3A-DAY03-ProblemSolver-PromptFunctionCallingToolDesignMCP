"""Run real bonus tools without a model and save clearly labelled smoke evidence."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from env_loader import load_lab_env
from tools import TOOL_FUNCTIONS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "bonus-live-tools.json")
    args = parser.parse_args()
    load_lab_env(ROOT)
    cases = [
        ("policy", {"query": "viral tweet source citation", "policy_area": "source_citation", "top_k": 3}),
        ("papers", {"query": "AI agent evaluation", "max_results": 1}),
        ("paper_text", {"arxiv_url": "1706.03762", "max_pages": 1, "max_chars": 4000}),
    ]
    events = []
    for name, arguments in cases:
        started = time.monotonic()
        result = TOOL_FUNCTIONS[name](**arguments)
        if name == "policy":
            passed = "error" not in result and bool(result.get("results"))
        elif name == "papers":
            passed = "error" not in result and bool(result.get("items"))
        else:
            passed = (
                "error" not in result and result.get("chars_returned", 0) > 0
                and result.get("pages_read") == 1
                and Path(result.get("pdf_path", "")).is_file()
                and Path(result.get("txt_path", "")).is_file()
            )
        events.append({
            "tool": name, "args": arguments, "passed": passed,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "execution": "local_knowledge" if name == "policy" else "live_network",
            "result": result,
        })
        print(f"{name}: {'PASS' if passed else 'FAIL'}", flush=True)
    evidence = {
        "verified_at": datetime.now(timezone(timedelta(hours=7))).isoformat(timespec="seconds"),
        "timezone": "Asia/Bangkok",
        "evidence_type": "direct_tool_smoke_test",
        "model_invoked": False,
        "telegram_sent": False,
        "source_note": "Company policy is the lab's sample local handbook, not an organizational policy.",
        "summary": {"passed": sum(event["passed"] for event in events), "total": len(events)},
        "events": events,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Evidence: {args.output}")
    return 0 if all(event["passed"] for event in events) else 1


if __name__ == "__main__":
    raise SystemExit(main())
