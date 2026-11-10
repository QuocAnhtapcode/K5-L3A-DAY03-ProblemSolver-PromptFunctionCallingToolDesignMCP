from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

from chat import execute_tool_call, now_iso, run_model_tool_loop, safe_slug, trim_history, write_transcript
from providers import make_provider
from providers.base import ToolCall
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ROOT = Path(__file__).parent
TRANSCRIPTS_DIR = ROOT / "transcripts"
MODEL = "gpt-4o-mini"
VERSION = "v8-bonus"
LOCAL_MODELS = ("qwen2.5:3b", "qwen2.5:7b")
EXPORTS_DIR = ROOT / "exported_digests"


def available_local_models() -> list[str]:
    """Read Ollama's local inventory without downloading or loading a model."""
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    try:
        response = requests.get(f"{base}/api/tags", timeout=2)
        response.raise_for_status()
        names = {
            entry["name"] for entry in response.json().get("models", [])
            if isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry["name"].strip()
        }
        return sorted(names)
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        return []


def artifact_paths(provider: str) -> tuple[Path, Path]:
    artifacts = ROOT / "artifacts"
    local_prompt = artifacts / "system_prompt_local.md"
    local_tools = artifacts / "tools_local.yaml"
    if provider == "ollama" and local_prompt.is_file() and local_tools.is_file():
        return local_prompt, local_tools
    return artifacts / "system_prompt.md", artifacts / "tools.yaml"


def session_tool_names(transcript: dict[str, Any]) -> set[str]:
    return {tool["name"] for tool in load_tool_declarations(Path(transcript["tools"]))}


def session_artifacts_current(transcript: dict[str, Any]) -> bool:
    current = build_artifact_version(
        transcript["version"], Path(transcript["system_prompt"]), Path(transcript["tools"]),
    )
    return current.prompt_hash == transcript.get("prompt_hash") and current.tools_hash == transcript.get("tools_hash")


def group_case_counts() -> dict[str, int]:
    try:
        dataset = json.loads((ROOT / "data" / "eval_group.json").read_text(encoding="utf-8"))
        cases = [case for case in dataset["cases"] if case.get("phase") == "B"]
        multi = sum("turns" in case for case in cases)
        return {"total": len(cases), "single": len(cases) - multi, "multi": multi}
    except (OSError, KeyError, ValueError, TypeError):
        return {"total": 0, "single": 0, "multi": 0}


def redact(value: Any) -> Any:
    """Keep configured credentials out of the web UI and downloadable transcripts."""
    if isinstance(value, str):
        for name, secret in os.environ.items():
            if name.endswith(("_KEY", "_TOKEN")) and len(secret) >= 8:
                value = value.replace(secret, "[redacted]")
        return value
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def new_session(
    provider: str = "openai", model: str | None = None, *,
    system_prompt_path: Path | None = None, tools_path: Path | None = None,
) -> dict[str, Any]:
    if provider not in {"openai", "ollama"}:
        raise ValueError("Chọn OpenAI hoặc Ollama.")
    selected_model = model.strip() if isinstance(model, str) else (LOCAL_MODELS[0] if provider == "ollama" else MODEL)
    if not selected_model:
        raise ValueError("Tên model không được để trống.")
    default_prompt, default_tools = artifact_paths(provider)
    prompt_path = (system_prompt_path or default_prompt).resolve()
    tools_path = (tools_path or default_tools).resolve()
    version = build_artifact_version(VERSION, prompt_path, tools_path)
    return {
        "transcript_id": f"web_{VERSION}_{provider}_{safe_slug(selected_model)}_{datetime.now():%Y%m%dT%H%M%S%f}_{uuid4().hex[:8]}",
        **artifact_version_dict(version),
        "provider": provider,
        "model": selected_model,
        "source": "streamlit_web_demo",
        "publishing_mode": "draft_only",
        "system_prompt": str(prompt_path),
        "tools": str(tools_path),
        "history_window": 5,
        "max_tool_rounds": 4,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }


def export_download(result: dict[str, Any]) -> dict[str, Any] | None:
    """Only expose supported files written under this application's export folder."""
    path_value = result.get("path")
    if not isinstance(path_value, str):
        return None
    try:
        target = Path(path_value).resolve(strict=True)
        root = EXPORTS_DIR.resolve()
        if not target.is_relative_to(root) or not target.is_file():
            return None
        mime_types = {".md": "text/markdown", ".json": "application/json", ".csv": "text/csv"}
        if target.suffix.lower() not in mime_types or target.stat().st_size > 10 * 1024 * 1024:
            return None
        data = redact(target.read_bytes().decode("utf-8")).encode("utf-8")
        return {"data": data, "file_name": target.name, "mime": mime_types[target.suffix.lower()]}
    except (OSError, ValueError, RuntimeError):
        return None


def assistant_display_text(turn: dict[str, Any], *, has_export_download: bool = False) -> str:
    """Keep server-local file references out of the public assistant message."""
    text = turn.get("assistant_text") or "Chưa có câu trả lời. Bạn thử diễn đạt lại yêu cầu nhé."
    exports = [event for event in turn.get("tool_events", []) if event.get("tool") == "export_digest"]
    if not exports:
        return text
    local_reference = bool(re.search(r"file://|(?:^|[\s`(\[])[A-Za-z]:[\\/]|\]\(\s*<?/", text, re.IGNORECASE))
    for event in exports:
        path = event.get("result", {}).get("path")
        if isinstance(path, str) and path:
            local_reference = local_reference or path in text or path.replace("\\", "/") in text
    if not local_reference:
        return text
    if has_export_download:
        return "Đã tạo tệp bản tin. Bạn có thể tải về bằng nút bên dưới."
    return "Tệp hiện chưa sẵn sàng để tải. Bạn thử yêu cầu xuất lại bản tin nhé."


def web_tool_executor(call: ToolCall) -> dict[str, Any]:
    # A shared public demo can prepare a draft but never publish to the owner's channel.
    if call.name == "send":
        draft = call.args.get("text")
        return {
            "tool": call.name,
            "args": redact(call.args),
            "result": {
                "tool": "send_telegram",
                "status": "draft_only",
                "draft": draft if isinstance(draft, str) else "",
                "awaiting_user": True,
                "question": "Bản demo web chỉ chuẩn bị bản nháp Telegram để bạn xem lại; nội dung chưa được gửi.",
            },
        }
    return redact(execute_tool_call(call))


def run_turn(transcript: dict[str, Any], user_text: str, *, provider: Any | None = None) -> dict[str, Any]:
    prompt = user_text.strip()
    if not prompt:
        raise ValueError("Vui lòng nhập câu hỏi.")
    history = []
    for previous in transcript["turns"]:
        if previous["status"] in {"answered", "waiting_for_user"}:
            history.extend([
                {"role": "user", "content": previous["user"]},
                {"role": "assistant", "content": previous["assistant_text"]},
            ])
    system_prompt = Path(transcript["system_prompt"]).read_text(encoding="utf-8")
    tools = to_openai_tools(load_tool_declarations(Path(transcript["tools"])))
    turn = {
        "turn_index": len(transcript["turns"]) + 1,
        "started_at": now_iso(),
        "user": prompt,
        "status": "started",
        "assistant_text": "",
        "rounds": [],
        "tool_events": [],
    }
    try:
        turn.update(run_model_tool_loop(
            provider=provider if provider is not None else make_provider(transcript["provider"]),
            messages=[
                {"role": "system", "content": system_prompt},
                *trim_history(history, transcript["history_window"]),
                {"role": "user", "content": prompt},
            ],
            tools=tools,
            model=transcript["model"],
            max_tool_rounds=transcript["max_tool_rounds"],
            tool_executor=web_tool_executor,
        ))
    except Exception as exc:
        turn.update({
            "status": "provider_error",
            "assistant_text": "Kết nối đang gián đoạn. Bạn thử lại sau một chút nhé.",
            "error": f"{type(exc).__name__}: {exc}",
        })
    turn["ended_at"] = now_iso()
    turn = redact(turn)
    transcript["turns"].append(turn)
    write_transcript(TRANSCRIPTS_DIR / f"{transcript['transcript_id']}.transcript.json", transcript)
    return turn


def run_summaries(*, transcript: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    summaries: list[tuple[str, dict[str, Any]]] = []
    for path in sorted((ROOT / "runs").glob("*.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
            if transcript is not None and any(
                run.get(key) != transcript.get(key)
                for key in ("provider", "model", "prompt_hash", "tools_hash")
            ):
                continue
            summary = run["summary"]
            summaries.append((run.get("generated_at", path.name), {
                "Phiên bản": run["version"],
                "Nguồn model": "Ollama" if run.get("provider") == "ollama" else run.get("provider", "").title(),
                "Model": run.get("model", ""),
                "Bộ đánh giá": run["suite"],
                "Case đạt / được đo": f"{summary['passed_cases']}/{summary['measured_cases']}",
                "Tỷ lệ": f"{summary['case_accuracy']:.0%}",
                "Lỗi kết nối model": summary["provider_error_cases"],
            }))
        except (OSError, KeyError, ValueError):
            continue
    return [row for _, row in sorted(summaries, key=lambda item: item[0])]
