from __future__ import annotations

import os

import streamlit as st

from chat import ARTIFACTS_DIR, ROOT, run_model_tool_loop, trim_history
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools


def show_message(message):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("tool_calls"):
            with st.expander("Tool đã gọi"):
                st.json(message["tool_calls"])


def main() -> None:
    st.set_page_config(page_title="Research Agent", page_icon="🔎")
    st.title("Research Agent")
    st.caption("Tìm nguồn trên web và X, đọc URL và tổng hợp kết quả.")

    load_lab_env(ROOT)
    has_openrouter_key = bool(os.getenv("OPENROUTER_API_KEY"))
    provider_name = st.sidebar.selectbox(
        "Provider", ["OpenRouter", "Ollama"], index=0 if has_openrouter_key else 1
    ).lower()
    provider = make_provider(provider_name)
    model = st.sidebar.text_input("Model", value=provider.default_model, key=f"model_{provider_name}")
    st.sidebar.caption("Bản demo chỉ bật các tool tra cứu và trình bày kết quả.")

    ready = provider_name == "ollama" or has_openrouter_key
    if not ready:
        st.info("Điền OPENROUTER_API_KEY vào starter_v0/.env để dùng OpenRouter.")

    history = st.session_state.setdefault("history", [])
    for message in history:
        show_message(message)

    user_text = st.chat_input("Ví dụ: Tìm tin về AI agents trong tuần qua", disabled=not ready)
    if not user_text or not user_text.strip():
        return

    user_message = {"role": "user", "content": user_text.strip()}
    show_message(user_message)
    messages = [
        {"role": "system", "content": (ARTIFACTS_DIR / "system_prompt.md").read_text(encoding="utf-8")},
        *({"role": message["role"], "content": message["content"]} for message in trim_history(history, 5)),
        user_message,
    ]
    declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")
    tools = to_openai_tools([tool for tool in declarations if tool["name"] != "send"])
    try:
        with st.spinner("Đang xử lý yêu cầu…"):
            result = run_model_tool_loop(
                provider=provider, messages=messages, tools=tools, model=model.strip() or None, max_tool_rounds=4
            )
    except Exception as exc:
        st.error(f"Không gọi được {provider_name} ({type(exc).__name__}). Kiểm tra kết nối và model đã chọn.")
        return

    assistant_message = {
        "role": "assistant",
        "content": result["assistant_text"] or "Model chưa trả về nội dung.",
        "tool_calls": [call for round_record in result["rounds"] for call in round_record["tool_calls"]],
    }
    history.extend([user_message, assistant_message])
    show_message(assistant_message)


if __name__ == "__main__":
    main()
