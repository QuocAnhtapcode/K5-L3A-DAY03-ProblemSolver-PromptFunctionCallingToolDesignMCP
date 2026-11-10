from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

import demo_runtime


ROOT = Path(__file__).parent
st.set_page_config(page_title="ProblemSolver · Research Desk", page_icon="🔎", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root {--ink:#17352e;--accent:#087f68;--muted:#64766f;}
html, body, [class*="css"], .stApp {font-family:'DM Sans','Segoe UI',sans-serif;}
.stApp {background:linear-gradient(140deg,#f7faf6 0%,#fbfcf8 60%,#eff7ef 100%);color:var(--ink);}
.stApp p, .stApp label, .stApp li {color:#294c3c;}
[data-testid="stHeader"], [data-testid="stToolbar"] {display:none;}
.block-container {max-width:1160px;padding-top:2.2rem;padding-bottom:3rem;}
h1,h2,h3 {font-family:'Manrope','Segoe UI',sans-serif;color:var(--ink);}
[data-testid="stSidebar"] {background:#edf4ee;border-right:1px solid #dbe7dd;}
[data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] label {color:#587063 !important;}
[data-testid="stCaptionContainer"] p {color:#64776b !important;}
[data-baseweb="tab"] {color:#426451 !important;}
[data-baseweb="tab-highlight"] {background:#087f68 !important;}
.brand {display:flex;align-items:center;gap:12px;margin-bottom:2rem;}
.brand-icon {background:#173e33;color:#e2f19d;border-radius:13px;padding:9px 13px;font-size:23px;}
.brand-name {font-family:'Manrope',sans-serif;font-weight:800;font-size:20px;letter-spacing:-.6px;}
.brand-sub {font-size:11px;letter-spacing:2px;color:#698276;margin-top:2px;}
.hero {padding:2rem 2.2rem;border:1px solid #d9e6d7;border-radius:24px;background:linear-gradient(115deg,#e5efdc,#f1f7e7);margin-bottom:1.5rem;}
.eyebrow {color:#54714c;letter-spacing:2px;font-size:11px;font-weight:700;text-transform:uppercase;}
.hero h1 {font-size:43px;line-height:1.17;letter-spacing:-1.7px;margin:.6rem 0 .85rem;font-weight:800;}
.hero p {font-size:16px;line-height:1.7;color:#58705e;max-width:760px;margin:0;}
.hero-pill {display:inline-block;font-size:11px;background:#fff9;border:1px solid #ccdbc3;border-radius:24px;padding:5px 10px;margin-top:1.2rem;color:#456047;}
.note {font-size:13px;color:#64776b;line-height:1.6;}
.tool-card {padding:18px;border:1px solid #dce7da;border-radius:16px;background:#fff;min-height:126px;margin-bottom:12px;}
.tool-title {font-weight:700;color:#244c3c;font-size:16px;margin-bottom:7px;}
.tool-copy {color:#6b7c70;font-size:13px;line-height:1.6;}
.stButton>button, .stDownloadButton>button {border:1px solid #d3e1d0;border-radius:13px;color:#274e3c;background:#fff;min-height:44px;}
.stButton>button:hover, .stDownloadButton>button:hover {border-color:#087f68;color:#087f68;background:#f1f8ed;}
[data-testid="stChatMessage"] {background:#ffffffb8;border:1px solid #e0e9db;border-radius:17px;padding:1.1rem;margin-bottom:.75rem;}
[data-testid="stChatInput"] {border-radius:15px;border:1px solid #cdddc7;}
[data-testid="stChatInput"], [data-testid="stChatInput"] textarea, [data-testid="stChatInput"] [data-baseweb="base-input"] {background:#fff !important;color:#17352e !important;}
[data-testid="stChatInput"] textarea::placeholder {color:#788d7e;opacity:1;}
[data-testid="stChatInput"] button {color:#087f68 !important;}
.footer {border-top:1px solid #dce5d7;margin-top:2rem;padding-top:1rem;color:#819080;font-size:11px;letter-spacing:.3px;}
#MainMenu, footer {visibility:hidden;}
</style>
""", unsafe_allow_html=True)

FRIENDLY_TOOLS = {
    "clarify": "Hỏi lại thông tin", "timeline": "Bài đăng theo tài khoản",
    "social_search": "Thảo luận trên X", "lookup": "Tìm kiếm web", "fetch": "Đọc đường dẫn",
    "format": "Trình bày bản tin", "send": "Bản nháp Telegram", "policy": "Chính sách nội bộ",
    "papers": "Tìm paper arXiv", "paper_text": "Đọc paper", "deduplicate": "Lọc bài trùng",
    "extract_links": "Tách đường dẫn", "source_audit": "Soát nguồn tham khảo", "export_digest": "Xuất bản tin thành tệp",
}
EXAMPLES = [
    ("Tin AI tuần này", "Tìm 2 tin về AI trong tuần này, tóm tắt ngắn bằng tiếng Việt và kèm nguồn.", "lookup"),
    ("Đọc một đường dẫn", "Đọc và tóm tắt ngắn trang này: https://www.python.org/about/", "fetch"),
    ("Lọc bài trùng", 'Lọc URL trùng và giữ bản đầu tiên: [{"title":"AI","url":"https://example.org/ai?utm_source=mail"},{"title":"AI bản sao","url":"https://example.org/ai#intro"},{"title":"Robotics","url":"https://example.org/robotics"}].', "deduplicate"),
    ("Kiểm tra nguồn tin", "Theo chính sách nội bộ, một tweet viral đã đủ để xác nhận một sự kiện chưa?", "policy"),
    ("Tách đường dẫn", "Tách các URL có trong đoạn sau, giữ thứ tự: Đọc [Python](https://www.python.org/about/) và tham khảo https://arxiv.org/abs/1706.03762.", "extract_links"),
    ("Soát nguồn tham khảo", 'Soát nguồn của các item đã có này: [{"title":"Tài liệu Python","url":"https://docs.python.org/3/"},{"title":"Paper Attention","url":"https://arxiv.org/abs/1706.03762"},{"title":"Bài đăng","url":"https://x.com/example/status/123"}]. Đây là kiểm tra loại nguồn, không phải xác minh sự kiện.', "source_audit"),
    ("Xuất tệp CSV", 'Xuất các item sau thành tệp CSV để tải về, để hệ thống tự tạo tên tệp mới: [{"title":"Python","url":"https://www.python.org/","summary":"Ngôn ngữ lập trình Python."},{"title":"arXiv","url":"https://arxiv.org/","summary":"Kho preprint nghiên cứu."}].', "export_digest"),
    ("Tìm paper AI agents", "Tìm 2 paper arXiv về AI agent evaluation, trả tiêu đề và đường dẫn.", "papers"),
]


@st.cache_data(ttl=30, show_spinner=False)
def local_model_options() -> list[str]:
    return demo_runtime.available_local_models()


with st.sidebar:
    st.markdown("### Research Desk")
    st.caption("WORKSPACE · PROBLEMSOLVER")
    st.markdown("Tìm nguồn, đọc nội dung và gom thông tin thành câu trả lời có căn cứ.")
    st.divider()
    provider_label = st.selectbox("Chạy trợ lý bằng", ["OpenAI", "Ollama trên máy"], key="provider_choice")
    selected_provider = "ollama" if provider_label == "Ollama trên máy" else "openai"
    if selected_provider == "ollama":
        installed_models = local_model_options()
        selected_model = st.selectbox("Model trên máy", installed_models or list(demo_runtime.LOCAL_MODELS), key="local_model_choice")
        if not installed_models:
            st.caption("Chưa đọc được danh sách model. Hãy mở Ollama trên máy chạy ứng dụng rồi thử lại.")
        st.caption("Model chạy trên máy chủ của ứng dụng. Các công cụ web vẫn cần kết nối Internet.")
    else:
        selected_model = demo_runtime.MODEL
        st.caption(f"Model: {selected_model}")
    st.caption("Đổi model sẽ bắt đầu một cuộc trò chuyện mới.")

    current = st.session_state.get("demo_transcript")
    selected_prompt, selected_tools = demo_runtime.artifact_paths(selected_provider)
    if (
        current is None or current.get("version") != demo_runtime.VERSION
        or current.get("provider") != selected_provider or current.get("model") != selected_model
        or current.get("system_prompt") != str(selected_prompt.resolve())
        or current.get("tools") != str(selected_tools.resolve())
        or not demo_runtime.session_artifacts_current(current)
    ):
        st.session_state.demo_transcript = demo_runtime.new_session(selected_provider, selected_model)
    transcript = st.session_state.demo_transcript
    active_tool_names = demo_runtime.session_tool_names(transcript)

    st.divider()
    st.markdown("**Kết quả đánh giá đã ghi**")
    model_runs = demo_runtime.run_summaries(transcript=transcript)
    for suite, label in (("base", "Bộ gốc"), ("group", "Bộ nhóm")):
        candidates = [row for row in model_runs if row["Bộ đánh giá"] == suite]
        if candidates:
            latest = candidates[-1]
            st.metric(f"{label} · {latest['Phiên bản']}", latest["Case đạt / được đo"])
    if not model_runs:
        st.caption("Chưa có kết quả đánh giá cho cấu hình trợ lý đang dùng.")
    st.caption("Điểm đo chọn công cụ và tham số; chưa phải thước đo chất lượng mọi câu trả lời.")
    st.divider()
    if st.button("Bắt đầu cuộc trò chuyện mới", use_container_width=True):
        st.session_state.demo_transcript = demo_runtime.new_session(selected_provider, selected_model)
        st.rerun()
    if transcript["turns"]:
        st.download_button(
            "Tải lịch sử trò chuyện",
            json.dumps(transcript, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"{transcript['transcript_id']}.transcript.json",
            mime="application/json", use_container_width=True,
        )
    st.caption(f"{provider_label} · {selected_model} · {demo_runtime.VERSION}")
    st.caption("Telegram trong bản demo chỉ tạo bản nháp, không xuất bản.")

st.markdown('<div class="brand"><div class="brand-icon">↗</div><div><div class="brand-name">ProblemSolver</div><div class="brand-sub">RESEARCH DESK</div></div></div>', unsafe_allow_html=True)
st.markdown(f"""
<section class="hero">
  <div class="eyebrow">Từ câu hỏi đến nguồn tin</div>
  <h1>Tìm đúng nguồn.<br>Hiểu rõ vấn đề.</h1>
  <p>Tra cứu web, đọc bài viết, soát nguồn và xuất bản tin trong một cuộc trò chuyện.
  Thiếu dữ liệu, trợ lý sẽ hỏi lại để bạn bổ sung.</p>
  <span class="hero-pill">{len(active_tool_names)} công cụ đang dùng · Có nguồn tham khảo · Lưu được lịch sử</span>
</section>
""", unsafe_allow_html=True)

chat_tab, tools_tab, evidence_tab = st.tabs(["Trò chuyện", "Công cụ", "Bằng chứng đánh giá"])

with chat_tab:
    st.markdown("### Bạn đang muốn tìm hiểu điều gì?")
    st.caption("Chọn một gợi ý hoặc nhập yêu cầu của bạn. Có thể hỏi tiếp và sửa lại yêu cầu ở lượt sau.")
    selected = None
    enabled_examples = [example for example in EXAMPLES if example[2] in active_tool_names]
    for start in range(0, len(enabled_examples), 4):
        for column, (label, question, _) in zip(st.columns(4), enabled_examples[start:start + 4]):
            if column.button(label, use_container_width=True):
                selected = question

    for turn in transcript["turns"]:
        with st.chat_message("user"):
            st.markdown(turn["user"])
        with st.chat_message("assistant"):
            events = turn.get("tool_events", [])
            export_downloads = []
            for event_index, event in enumerate(events):
                if event.get("tool") == "export_digest" and not event.get("result", {}).get("error"):
                    download = demo_runtime.export_download(event.get("result", {}))
                    if download:
                        export_downloads.append((event_index, download))
            st.markdown(demo_runtime.assistant_display_text(turn, has_export_download=bool(export_downloads)))
            for event_index, download in export_downloads:
                st.download_button(
                    "Tải bản tin đã xuất", **download,
                    key=f"export_{turn['turn_index']}_{event_index}",
                )
            if turn["status"] == "max_tool_rounds":
                st.info("Đã đến giới hạn xử lý của một lượt. Bạn có thể hỏi tiếp với yêu cầu cụ thể hơn.")
            if events:
                with st.expander("Nguồn và các bước đã thực hiện"):
                    for event_index, event in enumerate(events):
                        name = event.get("tool", "")
                        result = event.get("result", {})
                        st.markdown(f"**{FRIENDLY_TOOLS.get(name, name)}**")
                        if result.get("error"):
                            st.caption("Nguồn này chưa trả được dữ liệu trong lượt vừa rồi.")
                        for item in result.get("items", [])[:5]:
                            url = item.get("url", "")
                            if isinstance(url, str) and url.startswith(("http://", "https://")):
                                st.markdown(f"- [{item.get('title') or item.get('source') or url}]({url})")
                        for item in result.get("results", [])[:5]:
                            st.caption(f"{item.get('title', '')} · {item.get('section', '')}")
                        if result.get("status") == "draft_only" and result.get("draft"):
                            st.text_area("Bản nháp Telegram · chưa gửi", result["draft"], height=160, key=f"draft_{turn['turn_index']}_{event_index}")
                        if name == "deduplicate" and "duplicates_removed" in result:
                            st.caption(f"Đã bỏ {result['duplicates_removed']} bài trùng; giữ {result['output_count']} bài.")
                        if name == "extract_links" and "link_count" in result:
                            st.caption(f"Đã tách {result['link_count']} đường dẫn từ văn bản.")
                        if name == "source_audit" and "domain_count" in result:
                            st.caption(f"Có {result['domain_count']} tên miền; {result.get('missing_url_count', 0)} item thiếu URL.")
                            st.caption(result.get("caveat", "Phân loại nguồn chỉ là gợi ý, chưa xác minh nội dung."))

    ready = selected_provider == "ollama" or bool(os.getenv("OPENAI_API_KEY"))
    if not ready:
        st.warning("Chưa có kết nối model. Người quản trị cần kiểm tra cấu hình API trên máy chủ.")
    prompt = st.chat_input("Ví dụ: Tìm 2 tin AI trong tuần này và kèm nguồn…", max_chars=6000, disabled=not ready)
    if (prompt or selected) and ready:
        with st.spinner("Đang chọn nguồn và xử lý yêu cầu…"):
            demo_runtime.run_turn(transcript, prompt or selected)
        st.rerun()

with tools_tab:
    st.markdown("### Mỗi nhu cầu, một công cụ phù hợp")
    capabilities = [
        ("Tìm kiếm web", "Tìm thông tin và tin tức theo chủ đề, khoảng thời gian.", {"lookup"}),
        ("Đọc đường dẫn", "Đọc trang cụ thể và tóm tắt nội dung đã lấy được.", {"fetch"}),
        ("Lọc bài trùng · nhóm thêm", "Bỏ URL trùng, bỏ dấu theo dõi và giữ bản xuất hiện đầu tiên.", {"deduplicate"}),
        ("Tách đường dẫn · nhóm thêm", "Lấy các URL từ văn bản hoặc Markdown, giữ thứ tự xuất hiện.", {"extract_links"}),
        ("Soát nguồn tham khảo · nhóm thêm", "Kiểm tra URL thiếu, tên miền và loại nguồn. Kết quả chưa xác minh sự kiện.", {"source_audit"}),
        ("Xuất bản tin · nhóm thêm", "Tạo tệp Markdown, JSON hoặc CSV để tải về từ các item đã có.", {"export_digest"}),
        ("Bài đăng theo tài khoản X", "Lấy bài gần đây của một tài khoản. Dịch vụ X hiện trả lỗi HTTP trong các run đã ghi.", {"timeline"}),
        ("Thảo luận theo chủ đề trên X", "Tìm bài đăng mới nhất hoặc phổ biến theo từ khóa. Nguồn X hiện chưa trả được dữ liệu live.", {"social_search"}),
        ("Tìm paper arXiv", "Tìm paper và preprint nghiên cứu theo chủ đề.", {"papers"}),
        ("Đọc paper arXiv", "Tải PDF và trích văn bản theo giới hạn trang và độ dài.", {"paper_text"}),
        ("Chính sách nội bộ", "Tra quy định về nguồn tin, bảo mật và xuất bản từ bộ tài liệu mẫu của lab.", {"policy"}),
        ("Trình bày bản tin", "Gom các item đã có thành bản ngắn, nhóm mục hoặc thread.", {"format"}),
        ("Hỏi lại thông tin", "Hỏi dữ liệu còn thiếu hoặc xin xác nhận trước một hành động.", {"clarify"}),
        ("Bản nháp Telegram", "Chuẩn bị nội dung để xem lại. Giao diện demo không đăng lên Telegram.", {"send"}),
    ]
    capabilities = [card for card in capabilities if card[2] & active_tool_names]
    for index in range(0, len(capabilities), 2):
        for column, (title, description, _) in zip(st.columns(2), capabilities[index:index + 2]):
            with column:
                st.markdown(f'<div class="tool-card"><div class="tool-title">{title}</div><div class="tool-copy">{description}</div></div>', unsafe_allow_html=True)

with evidence_tab:
    st.markdown("### Kết quả từ những lần chạy thật")
    st.dataframe(demo_runtime.run_summaries(), hide_index=True, use_container_width=True)
    st.info("Đọc tỷ lệ cùng số case được đo và số lỗi kết nối model. Các phiên bản có thể dùng bộ test khác nhau; cần đối chiếu từng run khi so sánh.")
    group_cases = demo_runtime.group_case_counts()
    st.markdown(f"Bộ nhóm hiện có **{group_cases['total']} case: {group_cases['single']} case đơn lượt và {group_cases['multi']} case nhiều lượt**, kiểm tra chọn công cụ, tham số và ranh giới hành động.")
    st.caption("Multi-turn eval dùng lịch sử được cung cấp làm ngữ cảnh; cuộc trò chuyện trên giao diện và chat.py mới chạy nhiều lượt thực tế.")

st.markdown('<div class="footer">PROBLEMSOLVER · DAY 03 LAB · RESEARCH AGENT TOOL EVAL</div>', unsafe_allow_html=True)
