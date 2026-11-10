"""Offline regressions for honest, resumable, publication-free eval bookkeeping."""
from __future__ import annotations

from copy import deepcopy
import csv
from dataclasses import asdict
import json
from pathlib import Path
import sys

import pytest

from scripts import run_local_challenge as local
from scripts import run_safe_eval as safe
from versioning import build_artifact_version


SOURCE_ROOT = Path(__file__).resolve().parents[1]
FIELDS = "version,author,changed_artifact,artifact_version,prompt_hash,tools_hash,reason,hypothesis,metric_before,metric_after,run_file"


@pytest.fixture
def experiment(monkeypatch, tmp_path):
    (tmp_path / "runs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "artifacts").mkdir()
    dataset = json.loads((SOURCE_ROOT / "data" / "eval_base.json").read_text(encoding="utf-8"))
    (tmp_path / "data" / "eval_base.json").write_text(json.dumps(dataset), encoding="utf-8")
    prompt = tmp_path / "artifacts" / "prompt.md"
    tools = tmp_path / "artifacts" / "tools.yaml"
    prompt.write_text("Research instructions.", encoding="utf-8")
    tools.write_text("tools: []\n", encoding="utf-8")
    (tmp_path / "artifacts" / "version_log.csv").write_text(FIELDS + "\n", encoding="utf-8")
    monkeypatch.setattr(local, "ROOT", tmp_path)
    monkeypatch.setattr(safe, "ROOT", tmp_path)

    def make_run(provider="ollama", model="qwen2.5:3b", suite="base", suffix="20260101T000000000000"):
        data = {
            **asdict(build_artifact_version("v-test", prompt, tools)),
            "provider": provider, "model": model, "suite": suite, "phase": "B",
            "dataset_id": dataset["dataset_id"], "dataset_role": dataset["dataset_role"],
            "description": dataset["description"], "eval_cases": "data/eval_base.json",
            "action_execution": "dry_run_no_telegram",
            "summary": {"total_cases": 20, "measured_cases": 20, "provider_error_cases": 0, "case_accuracy": 0.5},
            "results": [{
                "id": case["id"], "phase": case["phase"], "case_suite": case.get("suite", "base"),
                "is_multiturn": "turns" in case, "metadata": case.get("metadata", {}),
                "input": case.get("query") or case.get("turns"), "expect": case["expect"],
                "result": {"case_failure_type": case["failure_type"]},
            } for case in dataset["cases"]],
        }
        filename = f"v-test_B_{suite}_{provider}_{suffix}.json"
        return tmp_path / "runs" / filename, data

    return tmp_path, dataset, prompt, tools, make_run


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_safe_wrapper_handles_equal_options_and_custom_directory_without_touching_history(experiment, monkeypatch):
    root, dataset, prompt, tools, make_run = experiment
    output = root / "custom-runs"
    output.mkdir()
    historical, original = make_run()
    write(historical, original)
    original_bytes = historical.read_bytes()
    expected_path = output / "v-test_B_group_openai_20260101T000000000001.json"

    def fake_eval():
        assert safe.TOOL_FUNCTIONS["send"](text="Never sent", confirmed=True)["sent"] is False
        _, data = make_run(provider="openai", model="gpt-4o-mini", suite="group")
        data.pop("action_execution")
        write(expected_path, data)
        (output / "unrelated-incomplete.json").write_text("{", encoding="utf-8")

    monkeypatch.setitem(safe.TOOL_FUNCTIONS, "send", lambda **kwargs: pytest.fail("Real publication was reached"))
    monkeypatch.setattr(safe.run_eval, "main", fake_eval)
    monkeypatch.setattr(sys, "argv", [
        "run_safe_eval.py", "--version=v-test", "--provider=openai", "--model=gpt-4o-mini",
        "--suite=group", f"--runs-dir={output}", f"--eval-cases={root / 'data' / 'eval_base.json'}",
        f"--system-prompt={prompt}",
    ])

    safe.main()

    saved = json.loads(expected_path.read_text(encoding="utf-8"))
    assert saved["action_execution"] == "dry_run_no_telegram"
    assert saved["eval_dataset_sha256"] == safe.dataset_hash(dataset)
    assert historical.read_bytes() == original_bytes
    assert not list(output.glob("*.tmp"))


def test_safe_wrapper_never_annotates_another_suite_or_provider(experiment, monkeypatch):
    root, _, _, _, make_run = experiment
    expected, own = make_run(provider="openai", model="gpt-4o-mini")
    foreign = expected.with_name("v-test_B_base_openai_foreign.json")
    original = deepcopy(own)
    original["suite"] = "group"
    original.pop("action_execution")
    own.pop("action_execution")

    def fake_eval():
        write(expected, own)
        write(foreign, original)
        (root / "runs" / "some-other-version_B_base_openai_partial.json").write_text("{", encoding="utf-8")

    monkeypatch.setitem(safe.TOOL_FUNCTIONS, "send", lambda **kwargs: None)
    monkeypatch.setattr(safe.run_eval, "main", fake_eval)
    monkeypatch.setattr(sys, "argv", ["run_safe_eval.py", "--version", "v-test", "--provider", "openai"])

    safe.main()

    assert "action_execution" not in json.loads(foreign.read_text(encoding="utf-8"))
    assert json.loads(expected.read_text(encoding="utf-8"))["action_execution"] == "dry_run_no_telegram"


def test_safe_wrapper_rejects_ambiguous_same_invocation_outputs(experiment, monkeypatch):
    root, _, _, _, make_run = experiment
    first, data = make_run(provider="openai", model="gpt-4o-mini")
    data.pop("action_execution")
    second = first.with_name("v-test_B_base_openai_other.json")

    def fake_eval():
        write(first, data)
        write(second, data)

    monkeypatch.setitem(safe.TOOL_FUNCTIONS, "send", lambda **kwargs: None)
    monkeypatch.setattr(safe.run_eval, "main", fake_eval)
    monkeypatch.setattr(sys, "argv", ["run_safe_eval.py", "--version=v-test", "--provider=openai"])

    with pytest.raises(RuntimeError, match="Concurrent invocations"):
        safe.main()

    assert "action_execution" not in json.loads(first.read_text(encoding="utf-8"))
    assert "action_execution" not in json.loads(second.read_text(encoding="utf-8"))


def test_resume_accepts_legacy_safe_evidence_and_skips_incomplete_candidates(experiment):
    root, _, prompt, tools, make_run = experiment
    path, data = make_run()
    write(path, data)
    (root / "runs" / "v-test_B_base_ollama_999-incomplete.json").write_text("{", encoding="utf-8")
    (root / "runs" / "unrelated.json").write_text("{", encoding="utf-8")
    before = path.read_bytes()

    assert local.find_run("v-test", "ollama", "qwen2.5:3b", prompt, tools) == path
    assert path.read_bytes() == before


@pytest.mark.parametrize("mutation", ["suite", "phase", "dry_run", "dataset_hash", "dataset_input", "dataset_expect", "provider_errors", "malformed_results"])
def test_resume_rejects_wrong_dataset_unsafe_or_partial_evidence(mutation, experiment):
    _, _, prompt, tools, make_run = experiment
    path, data = make_run()
    if mutation == "suite":
        data["suite"] = "group"
    elif mutation == "phase":
        data["phase"] = "A"
    elif mutation == "dry_run":
        data.pop("action_execution")
    elif mutation == "dataset_hash":
        data["eval_dataset_sha256"] = "wrong-dataset"
    elif mutation == "dataset_input":
        data["results"][0]["input"] = "A different eval question"
    elif mutation == "dataset_expect":
        data["results"][0]["expect"] = {"no_tool": True}
    elif mutation == "provider_errors":
        data["summary"].update(measured_cases=19, provider_error_cases=1)
    else:
        data["results"] = None
    write(path, data)

    assert local.find_run("v-test", "ollama", "qwen2.5:3b", prompt, tools) is None


def test_resume_accepts_canonical_dataset_hash_without_whitespace_dependency(experiment):
    _, dataset, prompt, tools, make_run = experiment
    path, data = make_run()
    reordered = json.loads(json.dumps(dataset, sort_keys=True, indent=4))
    data["eval_dataset_sha256"] = safe.dataset_hash(reordered)
    write(path, data)

    assert local.find_run("v-test", "ollama", "qwen2.5:3b", prompt, tools) == path


def test_version_log_is_idempotent_and_cannot_claim_dry_run_without_marker(experiment):
    root, _, _, _, make_run = experiment
    path, data = make_run()
    write(path, data)

    local.record_version(path, "prompt", "One hypothesis", 0.25)
    local.record_version(path, "prompt", "One hypothesis", 0.25)

    with (root / "artifacts" / "version_log.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["metric_before"] == "0.25"
    assert rows[0]["metric_after"] == "0.5"
    assert "20/20 measured" in rows[0]["reason"]
    data.pop("action_execution")
    write(path, data)
    with pytest.raises(ValueError, match="execution marker"):
        local.record_version(path, "prompt", "Another hypothesis", None)


def test_partial_eval_is_retained_and_logged_but_stage_does_not_report_completion(experiment, monkeypatch):
    root, _, prompt, tools, make_run = experiment
    path, data = make_run()
    data["summary"].update(measured_cases=19, provider_error_cases=1)

    def fake_subprocess(*args, **kwargs):
        write(path, data)
        # A different stage may still be writing its own JSON.
        (root / "runs" / "other_B_base_ollama_incomplete.json").write_text("{", encoding="utf-8")

    monkeypatch.setattr(local.subprocess, "run", fake_subprocess)

    with pytest.raises(RuntimeError, match="Incomplete evaluation retained and logged"):
        local.execute("v-test", "ollama", "qwen2.5:3b", prompt, tools,
                      "prompt", "One hypothesis", 0.25, True)

    assert path.is_file()
    with (root / "artifacts" / "version_log.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1 and "19/20 measured" in rows[0]["reason"]
    assert "1 provider errors" in rows[0]["reason"]
