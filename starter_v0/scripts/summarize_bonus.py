"""Build Vietnamese bonus evidence documents from existing files, without API calls.

This command never edits run JSON, prompts, declarations, REPORT.md, or the version
log. Re-run it after a pending experiment or the final pytest report completes.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import html
import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_TOOLS = {"clarify", "timeline", "social_search", "lookup", "fetch", "format", "send", "policy", "papers", "paper_text"}
MODEL_STAGES = (
    ("v6-qwen3b", "ollama", "qwen2.5:3b", "Baseline local", "v6-cloud"),
    ("v6-qwen7b", "ollama", "qwen2.5:7b", "Baseline local", "v6-cloud"),
    ("v4-local-qwen3b", "ollama", "qwen2.5:3b", "v4-local · rút prompt", "v4-local"),
    ("v4-local-qwen7b", "ollama", "qwen2.5:7b", "v4-local · rút prompt", "v4-local"),
    ("v5-local-qwen3b", "ollama", "qwen2.5:3b", "v5-local · giảm tool", "v5-local"),
    ("v5-local-qwen7b", "ollama", "qwen2.5:7b", "v5-local · giảm tool", "v5-local"),
    ("v6-cloud-reference", "openai", "gpt-4o-mini", "Cloud đối chứng", "v6-cloud"),
    ("v5-local-cloud-check", "openai", "gpt-4o-mini", "Kiểm tra ngược trên cloud", "v5-local"),
)
PATTERN_LABELS = {
    "unknown_tool_name": "Tên tool không được khai báo",
    "wrong_tool_name": "Gọi tên tool ngoài tập được mong đợi",
    "invalid_json_arguments": "Arguments JSON lỗi",
    "required_no_call": "Case cần tool nhưng không gọi",
    "missed_clarify": "Cần clarify nhưng không gọi clarify",
    "duplicate_calls": "Lặp đúng tool và cùng arguments",
    "unexpected_tool_on_no_tool": "Gọi tool ở case yêu cầu không dùng tool",
    "wrong_args_with_correct_routing": "Đúng routing nhưng sai args",
}


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def tool_names(path: Path) -> set[str]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return {item["name"] for item in data.get("tools", []) if isinstance(item, dict) and isinstance(item.get("name"), str)}
    except (OSError, ValueError, yaml.YAMLError):
        return set()


def registered_tools(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "TOOL_FUNCTIONS" for target in node.targets):
                if isinstance(node.value, ast.Dict):
                    return {key.value for key in node.value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
    except (OSError, SyntaxError):
        pass
    return set()


def failure_patterns(run: dict[str, Any], declared_names: set[str]) -> dict[str, Any]:
    """Count observed case-level patterns; dataset failure_type labels are not causes.

    Patterns overlap intentionally. Missing clarify can also be a required-no-call
    case. A duplicated call means identical name AND args, not two fetch calls for
    different URLs. Model/provider exceptions are excluded from these patterns.
    """
    examples: dict[str, list[str]] = {name: [] for name in PATTERN_LABELS}
    unknown_names: Counter[str] = Counter()
    tool_error_cases: list[str] = []
    tool_error_events = 0
    for case in run.get("results", []):
        result = case.get("result", {})
        if result.get("observed_mismatch") == "provider_error":
            continue
        case_id = str(case.get("id", ""))
        calls = result.get("actual_tool_calls") or []
        expected = case.get("expect", {})
        expected_names = {call.get("name") for call in expected.get("tool_calls", [])}
        actual_names = {call.get("name") for call in calls}
        invalid_json = any(isinstance(call.get("args"), dict) and "_invalid_json_arguments" in call["args"] for call in calls)
        canonical = [(call.get("name"), json.dumps(call.get("args", {}), ensure_ascii=False, sort_keys=True)) for call in calls]
        unknown = [call.get("name") for call in calls if call.get("name") not in declared_names]
        for name in unknown:
            unknown_names[str(name)] += 1
        flags = {
            "unknown_tool_name": bool(unknown),
            "wrong_tool_name": bool(calls) and bool(actual_names - expected_names),
            "invalid_json_arguments": invalid_json,
            "required_no_call": bool(expected.get("tool_calls")) and not expected.get("no_tool") and not calls,
            "missed_clarify": "clarify" in expected_names and "clarify" not in actual_names,
            "duplicate_calls": len(canonical) != len(set(canonical)),
            "unexpected_tool_on_no_tool": bool(expected.get("no_tool")) and bool(calls),
            "wrong_args_with_correct_routing": result.get("routing_correct") is True and result.get("args_correct") is False,
        }
        for name, present in flags.items():
            if present:
                examples[name].append(case_id)
        error_count = sum(
            1 for event in case.get("tool_results", [])
            if isinstance(event, dict) and isinstance(event.get("result", event), dict) and event.get("result", event).get("error")
        )
        if error_count:
            tool_error_cases.append(case_id)
            tool_error_events += error_count
    return {
        "case_counts": {name: len(ids) for name, ids in examples.items()},
        "examples": examples,
        "unknown_names": dict(unknown_names),
        "tool_error_cases": len(tool_error_cases),
        "tool_error_case_ids": tool_error_cases,
        "tool_error_events": tool_error_events,
        "counting_note": "Case-level observed patterns; counts overlap. Provider exceptions excluded. Tool errors do not change routing/argument score.",
    }


def junit_summary(path: Path) -> dict[str, Any]:
    try:
        root = ET.parse(path).getroot()
        suites = [suite for suite in root.iter("testsuite") if not suite.findall("testsuite")]
        totals = {key: sum(int(suite.get(key, "0")) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
        totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
        totals["seconds"] = round(sum(float(suite.get("time", "0")) for suite in suites), 3)
        totals["timestamp"] = suites[-1].get("timestamp") if suites else None
        return {"available": True, **totals}
    except (OSError, ET.ParseError, ValueError):
        return {"available": False}


def all_runs(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    result = []
    for path in (root / "runs").glob("*.json"):
        run = read_json(path)
        if run and isinstance(run.get("summary"), dict) and isinstance(run.get("results"), list):
            result.append((path, run))
    return sorted(result, key=lambda pair: (pair[1].get("generated_at", ""), pair[0].name))


def latest_run(runs: list[tuple[Path, dict[str, Any]]], version: str, provider: str, model: str, suite: str = "base") -> tuple[Path, dict[str, Any]] | None:
    matches = [pair for pair in runs if (pair[1].get("version"), pair[1].get("provider"), pair[1].get("model"), pair[1].get("suite")) == (version, provider, model, suite)]
    return matches[-1] if matches else None


def run_record(pair: tuple[Path, dict[str, Any]] | None, root: Path, *, snapshot: str | None = None) -> dict[str, Any]:
    if pair is None:
        return {"status": "pending", "note": "Chưa có run JSON hoàn tất; không gán điểm."}
    path, run = pair
    original_tools = Path(run.get("tools", ""))
    if not original_tools.is_absolute():
        original_tools = root / original_tools
    snapshot_dir = root / "artifacts" / "local_challenge" / snapshot if snapshot else None
    prompt_path = snapshot_dir / "system_prompt.md" if snapshot_dir else Path(run.get("system_prompt", ""))
    tools_path = snapshot_dir / "tools.yaml" if snapshot_dir else original_tools
    if not prompt_path.is_absolute():
        prompt_path = root / prompt_path
    names = tool_names(tools_path)
    return {
        "status": "completed", "run_file": relative(path, root), "version": run["version"],
        "provider": run["provider"], "model": run.get("model"), "suite": run["suite"],
        "generated_at": run.get("generated_at"), "artifact_version": run.get("artifact_version"),
        "prompt_hash": run.get("prompt_hash"), "tools_hash": run.get("tools_hash"),
        "snapshot_prompt": relative(prompt_path, root), "snapshot_tools": relative(tools_path, root),
        "snapshot_matches": digest(prompt_path) == run.get("prompt_hash") and digest(tools_path) == run.get("tools_hash"),
        "tool_count": len(names), "action_execution": run.get("action_execution", "not_recorded"),
        "summary": run["summary"], "observed_patterns": failure_patterns(run, names),
    }


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _score(row: dict[str, Any]) -> str:
    if row.get("status") != "completed":
        return "Chưa có run"
    data = row["summary"]
    return f"{data['passed_cases']}/{data['measured_cases']} ({_pct(data['case_accuracy'])})"


def build_summary(root: Path) -> dict[str, Any]:
    runs = all_runs(root)
    local_rows = []
    payloads = []
    for version, provider, model, stage, snapshot in MODEL_STAGES:
        pair = latest_run(runs, version, provider, model)
        row = run_record(pair, root, snapshot=snapshot)
        row.update({"expected_version": version, "expected_provider": provider, "expected_model": model, "stage": stage})
        local_rows.append(row)
        if pair:
            payloads.append(json.dumps(sorted([
                {"id": case["id"], "input": case.get("input"), "expect": case.get("expect"), "is_multiturn": case.get("is_multiturn")}
                for case in pair[1]["results"]
            ], key=lambda case: case["id"]), ensure_ascii=False, sort_keys=True))
    names = tool_names(root / "artifacts" / "tools.yaml")
    registered = registered_tools(root / "tools" / "__init__.py")
    students = sorted(names - ORIGINAL_TOOLS)
    docs = {}
    for name in students:
        folder = root / "tools" / name
        docs[name] = {"registered": name in registered, "implementation": (folder / "tool.py").is_file(), "documentation": (folder / "TOOL.md").is_file()}
    group = read_json(root / "data" / "eval_group.json") or {}
    cases = group.get("cases", [])
    tests = junit_summary(root / "artifacts" / "pytest-results.xml")
    confirmation = read_json(root / "artifacts" / "bonus-confirmation.json") or {}
    live_tools = read_json(root / "artifacts" / "bonus-live-tools.json") or {}
    deployment = read_json(root / "artifacts" / "deployment.json") or {}
    completed = [row for row in local_rows if row["status"] == "completed"]
    return {
        "generated_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(timespec="seconds"),
        "source_policy": "Only existing JSON/YAML/XML/code files were read; no run was changed and no API was called.",
        "inventory": {"tool_count": len(names), "tools": sorted(names), "student_tool_count": len(students), "student_tools": docs,
                      "ui_present": (root / "app.py").is_file(), "group_cases": len(cases),
                      "group_single_turn": sum("turns" not in case for case in cases), "group_multi_turn": sum("turns" in case for case in cases)},
        "tests": tests,
        "cloud_bonus": {suite: run_record(latest_run(runs, "v8-bonus", "openai", "gpt-4o-mini", suite), root) for suite in ("base", "group", "extension")},
        "local_challenge": {"runs": local_rows, "completed_runs": len(completed), "expected_runs": len(local_rows),
                            "same_base_case_payload": len(payloads) == len(local_rows) and len(set(payloads)) == 1,
                            "all_snapshots_match": len(completed) == len(local_rows) and all(row["snapshot_matches"] for row in completed),
                            "pattern_definitions": PATTERN_LABELS,
                            "pattern_note": "Đếm số case từ actual tool calls và flags chấm; các nhóm có thể giao nhau. Không dùng nhãn failure_type của dataset làm nguyên nhân.",
                            "runtime_note": "Local provider giới hạn max_tokens=512, timeout=120 giây, SDK retries=0. Context trong environment.json là quan sát /api/ps tại thời điểm snapshot, không phải num_ctx được đặt rõ trong từng request hoặc log context cho mọi case.",
                            "runtime_evidence_file": "artifacts/local_challenge/environment.json",
                            "runtime_evidence": read_json(root / "artifacts" / "local_challenge" / "environment.json")},
        "confirmation": {"evidence_file": "artifacts/bonus-confirmation.json", "summary": confirmation.get("summary", {}),
                         "model_invoked": confirmation.get("model_invoked"), "dialogue_source": confirmation.get("dialogue_source"),
                         "telegram_sent": confirmation.get("telegram_sent"), "telegram_network_requests": confirmation.get("telegram_network_requests"),
                         "transcript": confirmation.get("transcript"),
                         "note": "Hội thoại kiểm thử có OpenAI thật, lượt đồng ý được lập trình và executor mô phỏng. Không phải ủy quyền người dùng để gửi Telegram thật."},
        "extra_tools": {"evidence_file": "artifacts/bonus-live-tools.json", "summary": live_tools.get("summary", {}),
                        "events": [{key: event.get(key) for key in ("tool", "passed", "execution", "elapsed_seconds")} for event in live_tools.get("events", [])],
                        "note": "policy dùng handbook mẫu cục bộ; papers/paper_text gọi arXiv thật."},
        "demo": {"local_url": deployment.get("local_url", "http://127.0.0.1:8501"), "public_url": deployment.get("public_url"),
                 "recorded_active": deployment.get("active"), "note": "Đường dẫn theo deployment.json; script tổng hợp không tự kiểm tra uptime."},
        "limits": ["Accuracy chấm tool routing/arguments, không chấm đầy đủ chất lượng câu trả lời hoặc độ đúng của dữ liệu tool.",
                   "Provider errors bị loại khỏi mẫu số; luôn đọc số measured và provider_error_cases cùng accuracy.",
                   "Các case multi-turn eval gộp lịch sử vào một message, không thay thế hội thoại live nhiều vòng.",
                   "Model suy luận local; các tool web/arXiv vẫn gọi mạng và gửi truy vấn tới dịch vụ tương ứng.",
                   "source_audit kiểm tra metadata/loại nguồn, không xác minh sự kiện hay tính độc lập của nhiều nguồn.",
                   "X/Twitter có HTTPError trong các run đã ghi; PASS routing không chứng minh backend nguồn đó hoạt động.",
                   "Không có tin nhắn Telegram thật được gửi trong kiểm chứng bonus này."],
    }


def local_conclusions(summary: dict[str, Any]) -> list[str]:
    rows = {row["expected_version"]: row for row in summary["local_challenge"]["runs"]}
    notes = []
    for suffix, label in (("qwen3b", "Qwen 3B"), ("qwen7b", "Qwen 7B")):
        stages = [rows[f"v6-{suffix}"], rows[f"v4-local-{suffix}"], rows[f"v5-local-{suffix}"]]
        if all(row["status"] == "completed" for row in stages):
            values = [row["summary"]["case_accuracy"] for row in stages]
            notes.append(f"{label}: {_pct(values[0])} → {_pct(values[1])} → {_pct(values[2])}; rút prompt thay đổi {(values[1]-values[0])*100:+.0f} điểm phần trăm, giảm tập tool thay đổi {(values[2]-values[1])*100:+.0f} điểm phần trăm.")
    cloud, reverse = rows["v6-cloud-reference"], rows["v5-local-cloud-check"]
    if cloud["status"] == reverse["status"] == "completed":
        before, after = cloud["summary"]["case_accuracy"], reverse["summary"]["case_accuracy"]
        notes.append(f"Kiểm tra ngược trên cùng model cloud: {_pct(before)} → {_pct(after)} ({(after-before)*100:+.0f} điểm phần trăm). Không thể kết luận bản tối ưu local tốt hơn cho mọi model.")
    if notes:
        notes.append("Đây là một lần chạy mỗi cấu hình trên 20 case. Kết quả gợi ý giảm nhiễu từ số tool giúp model nhỏ gọi tool tốt hơn trong bộ này; chưa chứng minh quan hệ nhân quả tổng quát hoặc độ ổn định qua nhiều lần chạy.")
    return notes or ["Chưa đủ run hoàn tất để kết luận; không điền điểm hoặc suy đoán kết quả còn thiếu."]


def write_csv(summary: dict[str, Any], path: Path) -> None:
    fields = ["version", "provider", "model", "stage", "status", "passed_cases", "measured_cases", "total_cases", "provider_error_cases", "case_accuracy", "tool_routing_accuracy", "argument_accuracy", "multiturn_accuracy", "tool_count", "tool_error_cases", *PATTERN_LABELS, "snapshot_matches", "run_file"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in summary["local_challenge"]["runs"]:
            flat = {"version": row["expected_version"], "provider": row["expected_provider"], "model": row["expected_model"], "stage": row["stage"], "status": row["status"]}
            if row["status"] == "completed":
                flat.update({key: row["summary"].get(key) for key in fields if key in row["summary"]})
                flat.update({key: row.get(key) for key in ("tool_count", "snapshot_matches", "run_file")})
                flat["tool_error_cases"] = row["observed_patterns"]["tool_error_cases"]
                flat.update(row["observed_patterns"]["case_counts"])
            writer.writerow(flat)


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    inventory, tests = summary["inventory"], summary["tests"]
    lines = ["# Bonus — ProblemSolver Research Desk", "", f"Cập nhật: {summary['generated_at']}. Sinh lại từ log thật bằng `python scripts/summarize_bonus.py`; không chỉnh raw run.", "", "## Điều kiện bonus", "",
             f"- UI Streamlit: {'có' if inventory['ui_present'] else 'chưa có'}; {inventory['tool_count']} tool, trong đó **{inventory['student_tool_count']} tool nhóm tự thêm**: {', '.join('`'+name+'`' for name in inventory['student_tools'])}.",
             f"- Bộ nhóm: **{inventory['group_cases']} case**, gồm {inventory['group_single_turn']} single-turn + {inventory['group_multi_turn']} multi-turn."]
    if tests.get("available"):
        lines.append(f"- Unit test theo [JUnit XML](pytest-results.xml): **{tests['passed']} passed, {tests['failures']} failed, {tests['errors']} errors, {tests['skipped']} skipped**; timestamp {tests['timestamp']}.")
    else:
        lines.append("- Chưa có JUnit XML hợp lệ; không tự gán kết quả test.")
    confirmation = summary["confirmation"]
    live = summary["extra_tools"]
    lines.extend([f"- Xác nhận Telegram: {confirmation['summary'].get('passed', 0)}/{confirmation['summary'].get('total', 0)} kiểm tra đạt bằng OpenAI thật và executor dry-run. **Không gửi Telegram thật**; [bằng chứng](bonus-confirmation.json).",
                  f"- Policy + arXiv: {live['summary'].get('passed', 0)}/{live['summary'].get('total', 0)} smoke test đạt; policy cục bộ, hai tool arXiv gọi mạng thật; [bằng chứng](bonus-live-tools.json).", "", "## Cloud với bản bonus", "",
                  "| Bộ | Đạt / được đo | Tổng case | Lỗi provider | Run |", "|---|---:|---:|---:|---|"])
    for suite, row in summary["cloud_bonus"].items():
        if row["status"] == "completed":
            data = row["summary"]
            lines.append(f"| {suite} | {_score(row)} | {data['total_cases']} | {data['provider_error_cases']} | [{row['version']}](../{row['run_file']}) |")
        else:
            lines.append(f"| {suite} | Chưa có run | — | — | — |")
    lines.extend(["", "Extension chưa đạt toàn bộ: xem `failures` của từng case trong JSON. Điểm theo tập tool/args có thể khác đánh giá workflow nhiều vòng; không sửa base/extension để làm đẹp điểm.", "", "## Small Local Model Challenge", "",
                  "Baseline local giữ nguyên bản MVP v6 đã snapshot. Vòng v4 chỉ rút prompt; vòng v5 chỉ giảm tập tool xuống các tool cần cho base. Cloud reference dùng đúng snapshot của baseline local, cloud-check dùng bản v5-local.", "",
                  "| Version | Model | Tool | Đạt / được đo | Routing | Multi-turn | Lỗi provider | Snapshot khớp | Run |",
                  "|---|---|---:|---:|---:|---:|---:|---|---|"])
    for row in summary["local_challenge"]["runs"]:
        if row["status"] == "completed":
            data = row["summary"]
            lines.append(f"| {row['version']} | {row['model']} | {row['tool_count']} | {_score(row)} | {_pct(data.get('tool_routing_accuracy'))} | {_pct(data.get('multiturn_accuracy'))} | {data['provider_error_cases']} | {'Có' if row['snapshot_matches'] else 'Không'} | [JSON](../{row['run_file']}) |")
        else:
            lines.append(f"| {row['expected_version']} | {row['expected_model']} | — | Chưa có run | — | — | — | — | — |")
    lines.extend(["", "### Kết luận có bằng chứng", "", *["- " + note for note in local_conclusions(summary)], "",
                  f"- Payload base giống nhau ở toàn bộ 8 cấu hình: **{summary['local_challenge']['same_base_case_payload']}**. Snapshot prompt/tools khớp hash trong log: **{summary['local_challenge']['all_snapshots_match']}**.",
                  "- Hash chỉ nhận diện prompt/tools, không bao gồm code hoặc toàn bộ môi trường chạy.", "", "### Mẫu lỗi quan sát được", "",
                  "Các ô là số **case**, không phải số lần gọi. Nhóm có thể giao nhau; loại provider exception trước khi đếm. Không dùng nhãn `failure_type` gán sẵn làm nguyên nhân.", "",
                  "| Version | Tool lạ | Sai tên tool | JSON lỗi | Cần tool nhưng không gọi | Thiếu clarify | Gọi lặp y hệt | Tool ở no-tool | Đúng routing, sai args |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for row in summary["local_challenge"]["runs"]:
        if row["status"] == "completed":
            counts = row["observed_patterns"]["case_counts"]
            lines.append("| " + row["version"] + " | " + " | ".join(str(counts[key]) for key in PATTERN_LABELS) + " |")
    lines.extend(["", "Case ID ví dụ và số backend tool errors nằm trong [bonus-summary.json](bonus-summary.json). Bảng CSV để phân tích: [local_challenge.csv](../analysis/local_challenge.csv).", "", "### Điều kiện chạy được ghi nhận", ""])
    environment = summary["local_challenge"].get("runtime_evidence")
    if environment:
        lines.append(f"- [Snapshot môi trường](local_challenge/environment.json), thời điểm {environment.get('recorded_at', 'không rõ')}; Ollama {environment.get('ollama_version', {}).get('version', 'không rõ')}.")
        for model, data in environment.get("models", {}).items():
            details = data.get("details", {})
            lines.append(f"- `{model}`: {details.get('parameter_size', 'không rõ kích thước')}, {details.get('quantization_level', 'không rõ quantization')}; capabilities ghi nhận: {', '.join(data.get('capabilities', []))}.")
        settings = environment.get("request_settings", {})
        lines.append(f"- Provider local: `max_tokens={settings.get('max_tokens', 'không rõ')}`, timeout {settings.get('timeout', 'không rõ')} giây, retries {settings.get('max_retries', 'không rõ')}; giữ cùng giới hạn khi so sánh các stage.")
        for model in environment.get("loaded_models", {}).get("models", []):
            lines.append(f"- `/api/ps` quan sát `{model.get('name')}` có `context_length={model.get('context_length')}` tại snapshot. Đây là context được quan sát, **không phải `num_ctx` được đặt rõ trong từng request**, và không chứng minh context của mọi case đã được log riêng.")
    else:
        lines.append("Chưa có environment.json hợp lệ; không tự gán context hoặc cấu hình runtime.")
    lines.extend(["", "## Giới hạn cần giữ khi demo", "", *["- " + note for note in summary["limits"]], "", "## Chạy lại", "", "```text", "python scripts/run_local_challenge.py --stage baseline", "python scripts/run_local_challenge.py --stage v4-local", "python scripts/run_local_challenge.py --stage v5-local", "python scripts/run_local_challenge.py --stage cloud-reference", "python scripts/run_local_challenge.py --stage cloud-check", "python -m pytest --junitxml=artifacts/pytest-results.xml", "python scripts/summarize_bonus.py", "```", "", "Runner giữ log có sẵn nếu đúng model/hash và đủ 20 measured case; dùng `--force` khi chủ động chạy lại. Thực hiện từng stage, đọc log rồi mới quyết định vòng tiếp theo. Script tổng hợp chỉ đọc bằng chứng, không gọi API.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_poster(summary: dict[str, Any], path: Path) -> None:
    esc = html.escape
    inventory, tests = summary["inventory"], summary["tests"]
    cloud = summary["cloud_bonus"]
    local = {row["expected_version"]: row for row in summary["local_challenge"]["runs"]}
    def short_score(row: dict[str, Any]) -> str:
        return _pct(row["summary"]["case_accuracy"]) if row.get("status") == "completed" else "Chưa có run"
    def fraction(row: dict[str, Any]) -> str:
        return f"{row['summary']['passed_cases']}/{row['summary']['measured_cases']}" if row.get("status") == "completed" else "—"
    local_table = "".join(
        "<tr><th>" + label + "</th>" + "".join("<td>" + esc(short_score(local[name])) + "</td>" for name in (f"v6-{suffix}", f"v4-local-{suffix}", f"v5-local-{suffix}")) + "</tr>"
        for suffix, label in (("qwen3b", "Qwen 3B"), ("qwen7b", "Qwen 7B"))
    )
    student_cards = "".join(f'<div class="tool"><span class="tool-index">{index:02d}</span><div><strong>{name}</strong><p>{copy}</p></div></div>' for index, (name, copy) in enumerate([
        ("deduplicate", "Bỏ URL trùng và tham số theo dõi; giữ nguồn gốc."),
        ("extract_links", "Tách đường dẫn từ văn bản, giữ đúng thứ tự."),
        ("source_audit", "Soát URL và loại nguồn; không kết luận đúng sai."),
        ("export_digest", "Xuất bản tin Markdown, JSON hoặc CSV để tải về."),
    ], start=1))
    demo_url = summary["demo"].get("public_url") or summary["demo"].get("local_url") or ""
    safe_demo = demo_url if demo_url.startswith(("http://", "https://")) else ""
    confirmation, live = summary["confirmation"]["summary"], summary["extra_tools"]["summary"]
    tests_label = str(tests["passed"]) if tests.get("available") else "—"
    content = f'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ProblemSolver — Research Desk</title>
<style>
*{{box-sizing:border-box}}:root{{--ink:#183b32;--muted:#60756a;--green:#14795e;--lime:#dbefa0;--line:#d9e4d8}}body{{margin:0;background:#e7eee5;color:var(--ink);font-family:"Segoe UI",Arial,sans-serif;padding:28px}}main{{max-width:1160px;margin:auto;background:#fcfdf8;border:1px solid #d2dfd0;border-radius:26px;overflow:hidden;box-shadow:0 18px 60px #183b3215}}header{{display:flex;justify-content:space-between;align-items:center;padding:24px 34px 0}}.brand{{display:flex;gap:12px;align-items:center;font-weight:750;letter-spacing:-.4px}}.logo{{display:grid;place-items:center;width:42px;height:42px;background:var(--ink);border-radius:13px;color:var(--lime);font-size:16px}}.brand small{{display:block;letter-spacing:2px;font-size:9px;margin-top:3px;color:var(--muted)}}.tag{{border:1px solid var(--line);padding:8px 12px;border-radius:20px;font-size:10px;letter-spacing:1px}}.hero{{padding:25px 34px 24px;position:relative;background:radial-gradient(ellipse at 98% 10%,#dfedc9 0,transparent 45%)}}.eyebrow{{font-size:10px;letter-spacing:2px;color:var(--green);font-weight:750}}h1{{font-size:44px;letter-spacing:-1.7px;line-height:1.12;margin:12px 0 14px;font-weight:800}}.hero p{{font-size:14px;line-height:1.6;color:var(--muted);max-width:760px;margin:0}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:0 34px 24px}}.metric{{border:1px solid var(--line);border-radius:15px;padding:16px 18px;background:#f4f8ed}}.metric b{{display:block;font-size:30px;letter-spacing:-1px}}.metric span{{font-size:11px;color:var(--muted)}}.content{{display:grid;grid-template-columns:1fr 1fr;gap:28px;padding:0 34px 22px}}h2{{font-size:17px;letter-spacing:-.3px;margin:0 0 14px}}.tool{{display:flex;gap:12px;padding:9px 0;border-top:1px solid var(--line)}}.tool-index{{font-size:10px;color:var(--green);padding-top:3px;font-weight:700}}.tool strong{{font-size:12px}}.tool p{{margin:3px 0 0;font-size:11px;color:var(--muted);line-height:1.5}}.local{{background:var(--ink);color:#f4f8ed;padding:20px;border-radius:18px}}.local h2{{color:var(--lime)}}.local p{{font-size:11px;color:#c8dacd;line-height:1.6;margin:12px 0 0}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{padding:10px 5px;text-align:center;border-bottom:1px solid #ffffff25}}th:first-child{{text-align:left}}thead th{{font-size:9px;font-weight:500;color:#c3d7c5}}tbody td:last-child{{color:var(--lime);font-size:18px;font-weight:800}}.cloud-note{{border-top:1px solid #ffffff25;margin-top:13px;padding-top:12px;font-size:11px;line-height:1.7}}.evidence{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:0 34px 22px}}.evidence article{{border:1px solid var(--line);border-radius:13px;padding:14px}}.evidence h3{{margin:0 0 6px;font-size:12px}}.evidence p{{font-size:10px;line-height:1.6;color:var(--muted);margin:0}}.evidence b{{color:var(--green)}}.try{{margin:0 34px 20px;padding:15px 18px;border-radius:14px;background:#edf4e4;font-size:11px;line-height:1.8}}.try strong{{display:block;font-size:12px}}.try a{{color:var(--green);overflow-wrap:anywhere}}footer{{padding:16px 34px;border-top:1px solid var(--line);display:flex;gap:20px;justify-content:space-between;font-size:9px;line-height:1.6;color:var(--muted)}}footer a{{color:var(--green)}}.footnote{{max-width:740px}}@media(max-width:700px){{body{{padding:8px}}header,.hero{{padding-left:20px;padding-right:20px}}h1{{font-size:35px}}.metrics{{margin-left:20px;margin-right:20px;grid-template-columns:repeat(2,1fr)}}.content{{grid-template-columns:1fr;padding:0 20px 20px}}.evidence{{grid-template-columns:1fr;margin:0 20px 20px}}.try{{margin:0 20px 20px}}footer{{padding:15px 20px;display:block}}.tag{{display:none}}}}@page{{size:A4 landscape;margin:8mm}}@media print{{body{{padding:0;background:white}}main{{max-width:none;border-radius:0;box-shadow:none;border:0}}header{{padding-top:0}}.hero{{padding-top:14px;padding-bottom:15px}}h1{{font-size:32px;margin:8px 0}}.hero p{{font-size:11px}}.metrics{{margin-bottom:15px}}.metric{{padding:10px 14px}}.metric b{{font-size:24px}}.content{{gap:22px;padding-bottom:12px}}.tool{{padding:6px 0}}.local{{padding:15px}}.evidence{{margin-bottom:12px}}.evidence article{{padding:10px}}.try{{margin-bottom:12px;padding:10px 14px}}footer{{padding-top:9px;padding-bottom:0}}a{{text-decoration:none}}}}
</style></head><body><main>
<header><div class="brand"><span class="logo">PS</span><div>ProblemSolver<small>RESEARCH DESK · DAY 03</small></div></div><span class="tag">BONUS · BẰNG CHỨNG TỪ LOG THẬT</span></header>
<section class="hero"><div class="eyebrow">TỪ CÂU HỎI ĐẾN NGUỒN TIN</div><h1>Tìm đúng nguồn.<br>Giữ lại bằng chứng.</h1><p>Tra cứu web, đọc paper arXiv, soát nguồn và xuất bản tin trong một cuộc trò chuyện. Thiếu dữ liệu, trợ lý hỏi lại; các phiên bản được so sánh bằng kết quả chạy thật.</p></section>
<section class="metrics"><div class="metric"><b>{inventory['tool_count']}</b><span>công cụ trên bản cloud</span></div><div class="metric"><b>{inventory['student_tool_count']}</b><span>công cụ nhóm tự xây</span></div><div class="metric"><b>{tests_label}</b><span>unit test đạt theo JUnit</span></div><div class="metric"><b>{fraction(cloud['group'])}</b><span>case nhóm đạt · {inventory['group_single_turn']} đơn + {inventory['group_multi_turn']} nhiều lượt</span></div></section>
<section class="content"><div><h2>Bốn công cụ nhóm tự xây</h2>{student_cards}</div><div class="local"><h2>Model nhỏ: điều gì giúp gọi tool tốt hơn?</h2><table><thead><tr><th>Model</th><th>MVP gốc</th><th>Rút prompt</th><th>Giảm tool</th></tr></thead><tbody>{local_table}</tbody></table><p>Cùng bộ gốc 20 case; xem mẫu số và lỗi provider trong báo cáo. Mỗi vòng đổi một giả thuyết. Chưa suy rộng từ một lần chạy cho mọi tác vụ.</p><div class="cloud-note">Kiểm tra ngược trên cloud: <strong>{short_score(local['v6-cloud-reference'])} → {short_score(local['v5-local-cloud-check'])}</strong>.<br>Bản tối ưu cho model nhỏ không tự động tốt hơn cho cloud.</div></div></section>
<section class="evidence"><article><h3>Cloud · gpt-4o-mini</h3><p>Base <b>{fraction(cloud['base'])}</b> · Group <b>{fraction(cloud['group'])}</b> · Extension <b>{fraction(cloud['extension'])}</b>.<br>Chấm cách chọn công cụ và tham số.</p></article><article><h3>Policy và arXiv</h3><p><b>{live.get('passed', 0)}/{live.get('total', 0)} kiểm tra đạt</b>.<br>Policy cục bộ; tìm paper và đọc PDF có gọi arXiv thật.</p></article><article><h3>Xác nhận trước khi gửi</h3><p><b>{confirmation.get('passed', 0)}/{confirmation.get('total', 0)} kiểm tra đạt</b> với model thật.<br>Executor mô phỏng; không gửi Telegram thật.</p></article></section>
<section class="try"><strong>Thử ngay</strong>“Tách các URL trong đoạn văn này.” · “Soát loại nguồn của danh sách này.” · “Xuất các item thành CSV.”<br>Demo đã ghi: <a href="{esc(safe_demo, quote=True)}">{esc(safe_demo)}</a> · Link tunnel có thể thay đổi; ứng dụng phải đang chạy.</section>
<footer><div class="footnote">Suy luận local vẫn có thể dùng tool gọi Internet. source_audit chỉ kiểm tra metadata và loại nguồn, không xác minh sự thật. Điểm eval chưa đo đầy đủ chất lượng câu trả lời.<br>Hoàng Quốc Anh · Đỗ Thị Thanh Bình · Lê Gia Hưng · Hà Quang Vinh</div><div><a href="BONUS.md">Báo cáo bonus</a> · <a href="bonus-summary.json">Dữ liệu bằng chứng</a><br>{esc(summary['generated_at'])}</div></footer>
</main></body></html>'''
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    summary = build_summary(root)
    (artifacts / "bonus-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(summary, root / "analysis" / "local_challenge.csv")
    write_markdown(summary, artifacts / "BONUS.md")
    write_poster(summary, artifacts / "poster.html")
    print(f"Generated bonus evidence: {summary['local_challenge']['completed_runs']}/{summary['local_challenge']['expected_runs']} challenge runs; {summary['inventory']['student_tool_count']} student tools.")


if __name__ == "__main__":
    main()
