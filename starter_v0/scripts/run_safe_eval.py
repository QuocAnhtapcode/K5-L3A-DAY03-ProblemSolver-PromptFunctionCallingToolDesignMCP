"""Run the real evaluator while keeping publishing actions in explicit dry-run mode.

Retrieval tools still run against their real backends. This wrapper never sends a
Telegram message, including when a model incorrectly claims confirmation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run_eval
from tools import TOOL_FUNCTIONS


def dataset_hash(dataset: dict[str, Any]) -> str:
    """Hash dataset content independently of JSON whitespace or key ordering."""
    canonical = json.dumps(dataset, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_run_json(path: Path) -> dict[str, Any] | None:
    """Ignore a concurrently written/incomplete candidate, never rewrite it."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def run_file_pattern(version: str, provider: str, suite: str = "base", phase: str = "B") -> str:
    values = [version, phase, suite, provider]
    return "_".join(run_eval.safe_slug(value) for value in values) + "_*.json"


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    pending = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        pending.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def dry_run_send(text: str = "", confirmed: bool = False) -> dict:
    if confirmed is not True:
        return {"tool": "send_telegram", "status": "needs_confirmation"}
    return {
        "tool": "send_telegram", "status": "dry_run", "sent": False,
        "message": "Publication disabled for bonus evaluation; no Telegram request was made.",
        "text": text,
    }


def main() -> None:
    TOOL_FUNCTIONS["send"] = dry_run_send
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        run_eval.main()
        return
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--version", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--phase", default="B")
    parser.add_argument("--suite", default="base")
    parser.add_argument("--runs-dir", type=Path, default=ROOT / "runs")
    parser.add_argument("--eval-cases", type=Path, default=ROOT / "data" / "eval_base.json")
    options, _ = parser.parse_known_args()
    fingerprint = dataset_hash(json.loads(options.eval_cases.read_text(encoding="utf-8")))
    directory = options.runs_dir.resolve()
    pattern = run_file_pattern(options.version, options.provider, options.suite, options.phase)
    before = set(directory.glob(pattern))
    # run_eval receives the original CLI, including all arguments unknown here.
    run_eval.main()
    matches = []
    for path in set(directory.glob(pattern)) - before:
        data = read_run_json(path)
        if data is None or (data.get("version"), data.get("provider"), data.get("suite"), data.get("phase")) != (
            options.version, options.provider, options.suite, options.phase,
        ):
            continue
        if options.model is not None and data.get("model") != options.model:
            continue
        matches.append((path, data))
    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one new run for this invocation. Concurrent invocations with "
            "the same version/provider/suite are unsupported; use distinct versions."
        )
    path, data = matches[0]
    data["action_execution"] = "dry_run_no_telegram"
    data["eval_dataset_sha256"] = fingerprint
    atomic_write_json(path, data)


if __name__ == "__main__":
    main()
