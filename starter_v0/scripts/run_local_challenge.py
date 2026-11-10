"""Reproduce the lab's local-model experiment with real calls and resumable logs.

All stages disable Telegram publication. Baseline freezes the original cloud
artifacts; v4 changes only the prompt; v5 changes only the available tool set.
Run each stage after inspecting the previous stage's evidence.
Run a given stage/model sequentially. Concurrent identical invocations are unsupported.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from versioning import build_artifact_version
from scripts.run_safe_eval import atomic_write_json, dataset_hash, read_run_json, run_file_pattern

SNAPSHOTS = ROOT / "artifacts" / "local_challenge"
MODELS = {"qwen2.5:3b": "qwen3b", "qwen2.5:7b": "qwen7b"}


def _dataset_matches(run: dict, dataset: dict) -> bool:
    """Validate exact eval inputs; legacy logs are checked without modifying them."""
    recorded_hash = run.get("eval_dataset_sha256")
    if recorded_hash is not None and recorded_hash != dataset_hash(dataset):
        return False
    for key, default in (("dataset_id", "eval_base"), ("dataset_role", ""), ("description", "")):
        if run.get(key, default) != dataset.get(key, default):
            return False
    expected = []
    for case in dataset.get("cases", []):
        if case.get("phase") != "B":
            continue
        expected.append({
            "id": case.get("id"), "phase": case.get("phase"),
            "case_suite": case.get("suite", "base"), "is_multiturn": "turns" in case,
            "input": case.get("input") or case.get("query") or case.get("turns"),
            "expect": case.get("expect"), "metadata": case.get("metadata", {}),
            "failure_type": case.get("failure_type"),
        })
    results = run.get("results")
    if not isinstance(results, list) or any(not isinstance(case, dict) or not isinstance(case.get("result"), dict) for case in results):
        return False
    actual = [{
        "id": case.get("id"), "phase": case.get("phase"),
        "case_suite": case.get("case_suite"), "is_multiturn": case.get("is_multiturn"),
        "input": case.get("input"), "expect": case.get("expect"),
        "metadata": case.get("metadata", {}),
        "failure_type": case.get("result", {}).get("case_failure_type"),
    } for case in results]
    return len(expected) == 20 and actual == expected


def _fully_measured(run: dict) -> bool:
    summary = run.get("summary", {})
    if not isinstance(summary, dict):
        return False
    return (summary.get("total_cases"), summary.get("measured_cases"), summary.get("provider_error_cases")) == (20, 20, 0)


def find_run(version: str, provider: str, model: str, prompt: Path, tools: Path) -> Path | None:
    expected = build_artifact_version(version, prompt, tools)
    dataset = json.loads((ROOT / "data" / "eval_base.json").read_text(encoding="utf-8"))
    for path in sorted((ROOT / "runs").glob(run_file_pattern(version, provider)), reverse=True):
        data = read_run_json(path)
        if data is None:
            continue
        if (data.get("version"), data.get("provider"), data.get("model"),
            data.get("prompt_hash"), data.get("tools_hash")) == (
                version, provider, model, expected.prompt_hash, expected.tools_hash):
            if (data.get("suite") == "base" and data.get("phase") == "B"
                and data.get("action_execution") == "dry_run_no_telegram"
                and _fully_measured(data) and _dataset_matches(data, dataset)):
                return path
    return None


def record_version(path: Path, changed: str, hypothesis: str, before: float | None) -> None:
    run = json.loads(path.read_text(encoding="utf-8"))
    if run.get("action_execution") != "dry_run_no_telegram":
        raise ValueError("Cannot label this run Telegram dry-run: its execution marker is missing.")
    log_path = ROOT / "artifacts" / "version_log.csv"
    with log_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    if not fields:
        raise ValueError("version_log.csv must have its expected CSV header")
    relative = path.relative_to(ROOT).as_posix()
    if any(row["run_file"] == relative for row in rows):
        return
    row = {key: run[key] for key in ["version", "artifact_version", "prompt_hash", "tools_hash"]}
    row.update({
        "author": "ProblemSolver", "changed_artifact": changed,
        "reason": f"{run['provider']}/{run['model']}; suite={run['suite']}; "
                  f"{run['summary']['measured_cases']}/{run['summary']['total_cases']} measured; "
                  f"{run['summary']['provider_error_cases']} provider errors; Telegram dry-run",
        "hypothesis": hypothesis, "metric_before": "" if before is None else before,
        "metric_after": run["summary"]["case_accuracy"], "run_file": relative,
    })
    with log_path.open("a", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=fields).writerow(row)


def execute(version: str, provider: str, model: str, prompt: Path, tools: Path,
            changed: str, hypothesis: str, before: float | None, force: bool) -> Path:
    path = None if force else find_run(version, provider, model, prompt, tools)
    if path is None:
        pattern = run_file_pattern(version, provider)
        old_files = set((ROOT / "runs").glob(pattern))
        command = [sys.executable, "-X", "utf8", "-u", "scripts/run_safe_eval.py",
                   "--provider", provider, "--model", model, "--version", version,
                   "--suite", "base", "--eval-cases", "data/eval_base.json",
                   "--system-prompt", str(prompt), "--tools", str(tools)]
        print(f"\n=== {version}: {provider}/{model} ===", flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
        created = set()
        for candidate in set((ROOT / "runs").glob(pattern)) - old_files:
            run = read_run_json(candidate)
            if run is not None and (run.get("version"), run.get("provider"), run.get("model"), run.get("suite")) == (
                version, provider, model, "base",
            ):
                created.add(candidate)
        if len(created) != 1:
            raise RuntimeError("Expected one new matching run. Concurrent identical stage/model invocations are unsupported.")
        path = created.pop()
    else:
        print(f"Resuming from existing evidence: {path.name}", flush=True)
    record_version(path, changed, hypothesis, before)
    if not _fully_measured(json.loads(path.read_text(encoding="utf-8"))):
        raise RuntimeError(f"Incomplete evaluation retained and logged at {path}; resolve provider errors before continuing.")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, epilog="Do not run identical stage/model invocations concurrently.")
    parser.add_argument("--stage", choices=["baseline", "v4-local", "v5-local", "cloud-reference", "cloud-check"], required=True)
    parser.add_argument("--models", nargs="+", choices=list(MODELS), default=list(MODELS))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    baseline_prompt = SNAPSHOTS / "v6-cloud" / "system_prompt.md"
    baseline_tools = SNAPSHOTS / "v6-cloud" / "tools.yaml"
    local_prompt = ROOT / "artifacts" / "system_prompt_local.md"
    local_tools = ROOT / "artifacts" / "tools_local.yaml"
    manifest = []
    if args.stage in {"cloud-reference", "cloud-check"}:
        reference = args.stage == "cloud-reference"
        previous = find_run("v6-cloud-reference", "openai", "gpt-4o-mini", baseline_prompt, baseline_tools)
        before = json.loads(previous.read_text(encoding="utf-8"))["summary"]["case_accuracy"] if previous and not reference else None
        path = execute("v6-cloud-reference" if reference else "v5-local-cloud-check", "openai", "gpt-4o-mini",
                       baseline_prompt if reference else local_prompt, baseline_tools if reference else local_tools,
                       "unchanged frozen MVP v6" if reference else "local prompt/tools on cloud",
                       "Cloud reference with the exact artifacts used for local baseline" if reference else
                       "Check reverse transfer of the local-optimized artifacts", before, args.force)
        manifest.append(path)
    else:
        for model in args.models:
            suffix = MODELS[model]
            if args.stage == "baseline":
                version, prompt, tools = f"v6-{suffix}", baseline_prompt, baseline_tools
                previous, changed = None, "unchanged frozen MVP v6 artifacts"
                hypothesis = "Measure cloud-to-local transfer without changing the best MVP artifacts"
            elif args.stage == "v4-local":
                version, prompt, tools = f"v4-local-{suffix}", local_prompt, baseline_tools
                previous = find_run(f"v6-{suffix}", "ollama", model, baseline_prompt, baseline_tools)
                changed = "artifacts/system_prompt_local.md only"
                hypothesis = "A shorter prioritized prompt reduces small-model instruction conflicts"
            else:
                version, prompt, tools = f"v5-local-{suffix}", local_prompt, local_tools
                previous = find_run(f"v4-local-{suffix}", "ollama", model, local_prompt, baseline_tools)
                changed = "artifacts/tools_local.yaml only"
                hypothesis = "Keeping only the five tools needed for base reduces routing distractions"
            before = json.loads(previous.read_text(encoding="utf-8"))["summary"]["case_accuracy"] if previous else None
            manifest.append(execute(version, "ollama", model, prompt, tools,
                                    changed, hypothesis, before, args.force))
    progress = SNAPSHOTS / f"{args.stage}.json"
    atomic_write_json(progress, {"stage": args.stage, "runs": [p.relative_to(ROOT).as_posix() for p in manifest],
                                "telegram_sent": False})


if __name__ == "__main__":
    main()
