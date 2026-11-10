# ProblemSolver Research Desk

UI Streamlit dùng cùng prompt, tool registry và vòng lặp chat của lab. Key nằm trong `.env` phía máy chủ; không nhập key lên UI và không commit `.env`.

Bản bonus hỗ trợ **OpenAI hoặc Ollama**. Trong thanh bên, chọn “Chạy trợ lý bằng”, sau đó chọn model local nếu dùng Ollama. Model chạy trên máy chủ đang mở ứng dụng; đổi model bắt đầu một cuộc trò chuyện mới. Mỗi transcript lưu đúng provider, model và hash của prompt/tool được dùng.

## Chạy và chia sẻ

Trong terminal VS Code dùng Anaconda, tại `starter_v0`:

```text
python -m pip install -r requirements.txt
python scripts/start_demo.py
```

Script khởi chạy UI, tải binary Cloudflare chính thức nếu máy Windows chưa có và in link `trycloudflare.com`. Link hiện tại nằm trong `artifacts/deployment.json`. Giữ tiến trình chạy; Ctrl+C dừng các tiến trình do script tạo. Link tạm đổi khi khởi động lại.

Chỉ chạy local:

```text
python scripts/start_demo.py --local-only
```

Mặc định mở `http://127.0.0.1:8501`. Nếu cổng đang dùng, thêm `--port 8502`. Cũng có thể chạy trực tiếp bằng `python -m streamlit run app.py`.

## Thử nhanh

1. Bấm “Tin AI tuần này” hoặc nhập yêu cầu research có chủ đề rõ.
2. Yêu cầu tóm tắt “bài này”, rồi cung cấp URL khi được hỏi.
3. Bấm “Lọc bài trùng”, mở phần nguồn để xem số bài giữ lại.
4. Thử “Tách đường dẫn”, “Soát nguồn tham khảo” hoặc “Xuất tệp CSV”. Ba công cụ bổ sung cùng `deduplicate` tạo thành 4 công cụ do nhóm tự viết.
5. Sau khi xuất bản tin, bấm “Tải bản tin đã xuất” ngay dưới câu trả lời. Các tệp Markdown/JSON/CSV được lưu trong `exported_digests/`; UI chỉ cho tải tệp trong thư mục này. Đường dẫn tệp trên máy chủ không được hiển thị như link tải công khai.
6. Tải lịch sử thành JSON; mỗi phiên có transcript riêng.

Gợi ý và danh sách công cụ tự thay đổi theo bộ tool đang dùng. Soát nguồn chỉ kiểm tra URL, loại nguồn và độ đa dạng tên miền; nó chưa xác minh sự kiện hoặc kết luận rằng nguồn đáng tin tuyệt đối.

Web demo chỉ tạo bản nháp Telegram, không đăng thật. X/Twitter hiện trả HTTPError trong các run đã ghi dù model có thể chọn đúng tool.

## Dùng Ollama trên máy

Máy hiện có `qwen2.5:3b` và `qwen2.5:7b`. Mở Ollama trước khi chọn chế độ local trên UI. Ứng dụng đọc danh sách model đã cài, không tự tải model mới. Nếu không đọc được danh sách, kiểm tra Ollama đang chạy rồi thử lại.

Khi có đủ `artifacts/system_prompt_local.md` và `artifacts/tools_local.yaml`, chế độ Ollama tự dùng bản tối ưu local này. OpenAI vẫn dùng `artifacts/system_prompt.md` và `artifacts/tools.yaml`. Transcript ghi rõ đường dẫn và hash thực tế. Nếu chưa có bản local, Ollama dùng chung bộ chính.

Model local không cần OpenAI API key. Các công cụ lấy dữ liệu web vẫn gọi dịch vụ bên ngoài theo cấu hình `.env`; “model local” không có nghĩa mọi công cụ đều hoạt động offline.

## Chat CLI và kiểm tra

```text
python -X utf8 chat.py --provider openai --model gpt-4o-mini --version v8-bonus
python -X utf8 chat.py --provider ollama --model qwen2.5:3b --version v8-bonus --system-prompt artifacts/system_prompt_local.md --tools artifacts/tools_local.yaml
python -m pytest
```

Bằng chứng ở `transcripts/`, `artifacts/REPORT.md`, `artifacts/version_log.csv` và `artifacts/pytest-results.xml`.
