from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

import demo_runtime
from providers.base import ModelResponse, ToolCall


ROOT = Path(__file__).resolve().parents[1]


class SequenceProvider:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.messages = []
        self.options = []

    def complete(self, messages, tools=None, **kwargs):
        self.messages.append(list(messages))
        self.options.append(kwargs)
        return next(self.responses)


def test_web_demo_blocks_publication_even_when_model_sets_confirmed_true(monkeypatch) -> None:
    def unexpected_dispatch(call):
        raise AssertionError("Public demo must not dispatch Telegram publication")

    monkeypatch.setattr(demo_runtime, "execute_tool_call", unexpected_dispatch)
    event = demo_runtime.web_tool_executor(ToolCall("send", {"text": "Draft", "confirmed": True}))

    assert event["result"]["status"] == "draft_only"
    assert event["result"]["awaiting_user"] is True
    assert event["result"]["draft"] == "Draft"


def test_web_turn_persists_real_tool_events_and_keeps_context(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(demo_runtime, "TRANSCRIPTS_DIR", tmp_path)
    provider = SequenceProvider([
        ModelResponse(tool_calls=[ToolCall("clarify", {"question": "Bạn gửi URL nhé.", "response_type": "text"})]),
        ModelResponse(text="Mình đã nhận thông tin bổ sung."),
    ])
    session = demo_runtime.new_session()

    first = demo_runtime.run_turn(session, "Đọc bài này.", provider=provider)
    second = demo_runtime.run_turn(session, "Đây là thông tin bổ sung.", provider=provider)

    assert first["status"] == "waiting_for_user"
    assert first["tool_events"][0]["tool"] == "clarify"
    assert second["status"] == "answered"
    assert {"role": "assistant", "content": "Bạn gửi URL nhé."} in provider.messages[1]
    saved = json.loads((tmp_path / f"{session['transcript_id']}.transcript.json").read_text(encoding="utf-8"))
    assert len(saved["turns"]) == 2
    assert saved["source"] == "streamlit_web_demo"


def test_web_redacts_configured_secrets_in_nested_data(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-value-123")

    result = demo_runtime.redact({"events": [{"message": "Failure: test-secret-value-123"}]})

    assert result == {"events": [{"message": "Failure: [redacted]"}]}


def test_web_provider_failure_is_saved_as_failure_not_success(monkeypatch, tmp_path) -> None:
    class FailingProvider:
        def complete(self, *args, **kwargs):
            raise ConnectionError("offline test")

    monkeypatch.setattr(demo_runtime, "TRANSCRIPTS_DIR", tmp_path)
    session = demo_runtime.new_session()

    turn = demo_runtime.run_turn(session, "Tìm tin AI.", provider=FailingProvider())

    assert turn["status"] == "provider_error"
    assert "ConnectionError" in turn["error"]
    assert turn["tool_events"] == []


def test_streamlit_chat_saves_a_session_without_network(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-only")
    monkeypatch.setattr(demo_runtime, "TRANSCRIPTS_DIR", tmp_path)
    monkeypatch.setattr(demo_runtime, "make_provider", lambda name: SequenceProvider([ModelResponse(text="Mình hỗ trợ research có nguồn.")]))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()
    assert len(app.exception) == 0

    app.chat_input[0].set_value("Bạn làm được gì?").run()

    assert len(app.exception) == 0
    assert len(app.chat_message) == 2
    assert len(app.session_state["demo_transcript"]["turns"]) == 1
    assert len(list(tmp_path.glob("*.transcript.json"))) == 1


def test_ollama_session_uses_local_artifacts_and_selected_model(monkeypatch, tmp_path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "system_prompt_local.md").write_text("Local research instructions.", encoding="utf-8")
    (artifacts / "tools_local.yaml").write_text("tools: []\n", encoding="utf-8")
    monkeypatch.setattr(demo_runtime, "ROOT", tmp_path)
    monkeypatch.setattr(demo_runtime, "TRANSCRIPTS_DIR", tmp_path / "transcripts")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = SequenceProvider([ModelResponse(text="Câu trả lời từ model trên máy.")])
    selected = []
    monkeypatch.setattr(demo_runtime, "make_provider", lambda name: selected.append(name) or provider)

    session = demo_runtime.new_session("ollama", "qwen2.5:7b")
    turn = demo_runtime.run_turn(session, "Bạn làm được gì?")

    assert selected == ["ollama"]
    assert session["provider"] == "ollama"
    assert session["model"] == "qwen2.5:7b"
    assert Path(session["system_prompt"]).name == "system_prompt_local.md"
    assert Path(session["tools"]).name == "tools_local.yaml"
    assert provider.messages[0][0]["content"] == "Local research instructions."
    assert provider.options[0]["model"] == "qwen2.5:7b"
    assert turn["status"] == "answered"
    saved = json.loads(next((tmp_path / "transcripts").glob("*.json")).read_text(encoding="utf-8"))
    assert saved["model"] == "qwen2.5:7b"
    assert saved["provider"] == "ollama"


def test_openai_session_passes_its_requested_model_to_provider(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(demo_runtime, "TRANSCRIPTS_DIR", tmp_path)
    provider = SequenceProvider([ModelResponse(text="Research assistant.")])
    session = demo_runtime.new_session("openai", "test-openai-model")

    demo_runtime.run_turn(session, "Bạn làm được gì?", provider=provider)

    assert session["model"] == "test-openai-model"
    assert provider.options[0]["model"] == "test-openai-model"
    assert "test-openai-model" in session["transcript_id"]


def test_streamlit_switch_to_ollama_starts_a_separate_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-only")
    monkeypatch.setattr(demo_runtime, "TRANSCRIPTS_DIR", tmp_path)
    monkeypatch.setattr(demo_runtime, "available_local_models", lambda: ["qwen2.5:3b", "qwen2.5:7b"])
    monkeypatch.setattr(demo_runtime, "make_provider", lambda name: SequenceProvider([ModelResponse(text="Model local sẵn sàng.")]))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()
    old_id = app.session_state["demo_transcript"]["transcript_id"]

    app.selectbox[0].set_value("Ollama trên máy").run()
    assert len(app.exception) == 0
    assert app.session_state["demo_transcript"]["provider"] == "ollama"
    assert app.session_state["demo_transcript"]["transcript_id"] != old_id
    app.selectbox[1].set_value("qwen2.5:7b").run()
    app.chat_input[0].set_value("Bạn làm được gì?").run()

    assert len(app.exception) == 0
    assert app.session_state["demo_transcript"]["model"] == "qwen2.5:7b"
    assert len(app.chat_message) == 2


def test_export_download_accepts_only_supported_files_inside_export_folder(monkeypatch, tmp_path) -> None:
    exports = tmp_path / "exported_digests"
    exports.mkdir()
    exported = exports / "research.csv"
    exported.write_text("title,url\nPython,https://python.org/\n", encoding="utf-8")
    monkeypatch.setattr(demo_runtime, "EXPORTS_DIR", exports)

    download = demo_runtime.export_download({"path": str(exported)})

    assert download["file_name"] == "research.csv"
    assert download["mime"] == "text/csv"
    assert download["data"] == exported.read_bytes()


def test_export_download_rejects_traversal_and_arbitrary_server_files(monkeypatch, tmp_path) -> None:
    exports = tmp_path / "exported_digests"
    exports.mkdir()
    private = tmp_path / "private.json"
    private.write_text('{"private":true}', encoding="utf-8")
    unsupported = exports / "program.py"
    unsupported.write_text("print('example')", encoding="utf-8")
    monkeypatch.setattr(demo_runtime, "EXPORTS_DIR", exports)

    assert demo_runtime.export_download({"path": str(exports / ".." / "private.json")}) is None
    assert demo_runtime.export_download({"path": str(unsupported)}) is None
    assert demo_runtime.export_download({"path": str(exports / "missing.csv")}) is None


def test_export_download_redacts_configured_credentials(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(demo_runtime, "EXPORTS_DIR", tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-export-123")
    exported = tmp_path / "research.md"
    exported.write_text("Source error: test-secret-export-123", encoding="utf-8")

    download = demo_runtime.export_download({"path": str(exported)})

    assert download["data"] == b"Source error: [redacted]"


def test_session_detects_artifact_changes_before_reusing_recorded_hashes(tmp_path) -> None:
    prompt = tmp_path / "prompt.md"
    tools = tmp_path / "tools.yaml"
    prompt.write_text("First instructions.", encoding="utf-8")
    tools.write_text("tools: []\n", encoding="utf-8")
    session = demo_runtime.new_session(system_prompt_path=prompt, tools_path=tools)
    assert demo_runtime.session_artifacts_current(session) is True

    prompt.write_text("Changed instructions.", encoding="utf-8")

    assert demo_runtime.session_artifacts_current(session) is False


def test_local_model_inventory_uses_ollama_tags_without_loading_a_model(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    from conftest import FakeResponse

    requests = fake_http(FakeResponse({"models": [{"name": "qwen2.5:7b"}, {"name": "qwen2.5:3b"}, {"name": "qwen2.5:7b"}]}))

    assert demo_runtime.available_local_models() == ["qwen2.5:3b", "qwen2.5:7b"]
    assert requests[0]["url"] == "http://127.0.0.1:11434/api/tags"


def test_repeated_csv_preset_creates_distinct_downloadable_exports(monkeypatch, tmp_path) -> None:
    from tools.export_digest import tool as export_tool

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-only")
    monkeypatch.setattr(demo_runtime, "TRANSCRIPTS_DIR", tmp_path / "transcripts")
    monkeypatch.setattr(demo_runtime, "EXPORTS_DIR", tmp_path / "exports")
    monkeypatch.setattr(export_tool, "EXPORT_DIR", tmp_path / "exports")
    providers = []

    def make_export_provider(name):
        provider = SequenceProvider([
            ModelResponse(tool_calls=[ToolCall("export_digest", {
                "items": [{"title": "Python", "url": "https://python.org/"}], "format": "csv",
            })]),
            ModelResponse(text="Tải [bản tin CSV](file:///D:/private/research.csv) vừa tạo."),
        ])
        providers.append(provider)
        return provider

    monkeypatch.setattr(demo_runtime, "make_provider", make_export_provider)
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=10).run()
    for _ in range(2):
        next(button for button in app.button if button.label == "Xuất tệp CSV").click().run()

    assert len(app.exception) == 0
    assert len(list((tmp_path / "exports").glob("*.csv"))) == 2
    turns = app.session_state["demo_transcript"]["turns"]
    assert len(turns) == 2
    paths = [turn["tool_events"][0]["result"]["path"] for turn in turns]
    assert len(set(paths)) == 2
    assert all(demo_runtime.export_download({"path": path}) for path in paths)
    assert all("research-demo" not in provider.messages[0][-1]["content"] for provider in providers)
    assert all("file://" in turn["assistant_text"] for turn in turns)
    assert not any("file://" in markdown.value for markdown in app.markdown)
    assert sum(button.label == "Tải bản tin đã xuất" for button in app.get("download_button")) == 2
    assert all(not expander.get("download_button") for expander in app.expander)


def test_sidebar_metrics_match_session_artifacts_while_history_keeps_other_runs(monkeypatch, tmp_path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(demo_runtime, "ROOT", tmp_path)
    identity = {"provider": "openai", "model": "gpt-4o-mini", "prompt_hash": "main-prompt", "tools_hash": "main-tools"}
    variants = [
        ("v8-bonus", {}, "2026-11-10T14:00:00", 19),
        ("v5-local-cloud-check", {"prompt_hash": "local-prompt", "tools_hash": "local-tools"}, "2026-11-10T15:00:00", 18),
        ("other-tools-same-prompt", {"tools_hash": "other-tools"}, "2026-11-10T16:00:00", 17),
    ]
    for version, differences, generated_at, passed in variants:
        run = {
            **identity, **differences, "version": version, "suite": "base", "generated_at": generated_at,
            "summary": {"passed_cases": passed, "measured_cases": 20, "case_accuracy": passed / 20, "provider_error_cases": 0},
        }
        (runs / f"{version}.json").write_text(json.dumps(run), encoding="utf-8")

    matching = demo_runtime.run_summaries(transcript=identity)
    historical = demo_runtime.run_summaries()

    assert len(matching) == 1
    assert matching[0]["Phiên bản"] == "v8-bonus"
    assert matching[0]["Case đạt / được đo"] == "19/20"
    assert len(historical) == 3
    assert "v5-local-cloud-check" in {row["Phiên bản"] for row in historical}
