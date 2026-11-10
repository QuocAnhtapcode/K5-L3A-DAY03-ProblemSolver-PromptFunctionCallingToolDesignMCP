# Bonus — ProblemSolver Research Desk

Cập nhật: 2026-11-10T20:08:07+07:00. Sinh lại từ log thật bằng `python scripts/summarize_bonus.py`; không chỉnh raw run.

## Điều kiện bonus

- UI Streamlit: có; 14 tool, trong đó **4 tool nhóm tự thêm**: `deduplicate`, `export_digest`, `extract_links`, `source_audit`.
- Bộ nhóm: **16 case**, gồm 8 single-turn + 8 multi-turn.
- Unit test theo [JUnit XML](pytest-results.xml): **229 passed, 0 failed, 0 errors, 0 skipped**; timestamp 2026-11-10T17:53:28.484110+07:00.
- Xác nhận Telegram: 4/4 kiểm tra đạt bằng OpenAI thật và executor dry-run. **Không gửi Telegram thật**; [bằng chứng](bonus-confirmation.json).
- Policy + arXiv: 3/3 smoke test đạt; policy cục bộ, hai tool arXiv gọi mạng thật; [bằng chứng](bonus-live-tools.json).

## Cloud với bản bonus

| Bộ | Đạt / được đo | Tổng case | Lỗi provider | Run |
|---|---:|---:|---:|---|
| base | 19/20 (95%) | 20 | 0 | [v8-bonus](../runs/v8-bonus_B_base_openai_20261110T170920329810.json) |
| group | 16/16 (100%) | 16 | 0 | [v8-bonus](../runs/v8-bonus_B_group_openai_20261110T170816913898.json) |
| extension | 8/10 (80%) | 10 | 0 | [v8-bonus](../runs/v8-bonus_B_extension_openai_20261110T170913555070.json) |

Extension chưa đạt toàn bộ: xem `failures` của từng case trong JSON. Điểm theo tập tool/args có thể khác đánh giá workflow nhiều vòng; không sửa base/extension để làm đẹp điểm.

## Small Local Model Challenge

Baseline local giữ nguyên bản MVP v6 đã snapshot. Vòng v4 chỉ rút prompt; vòng v5 chỉ giảm tập tool xuống các tool cần cho base. Cloud reference dùng đúng snapshot của baseline local, cloud-check dùng bản v5-local.

| Version | Model | Tool | Đạt / được đo | Routing | Multi-turn | Lỗi provider | Snapshot khớp | Run |
|---|---|---:|---:|---:|---:|---:|---|---|
| v6-qwen3b | qwen2.5:3b | 11 | 3/20 (15%) | 15% | 17% | 0 | Có | [JSON](../runs/v6-qwen3b_B_base_ollama_20261110T165759259540.json) |
| v6-qwen7b | qwen2.5:7b | 11 | 4/20 (20%) | 20% | 17% | 0 | Có | [JSON](../runs/v6-qwen7b_B_base_ollama_20261110T165946557678.json) |
| v4-local-qwen3b | qwen2.5:3b | 11 | 5/20 (25%) | 50% | 17% | 0 | Có | [JSON](../runs/v4-local-qwen3b_B_base_ollama_20261110T170830351928.json) |
| v4-local-qwen7b | qwen2.5:7b | 11 | 5/20 (25%) | 50% | 17% | 0 | Có | [JSON](../runs/v4-local-qwen7b_B_base_ollama_20261110T171019920061.json) |
| v5-local-qwen3b | qwen2.5:3b | 5 | 14/20 (70%) | 75% | 67% | 0 | Có | [JSON](../runs/v5-local-qwen3b_B_base_ollama_20261110T171218451428.json) |
| v5-local-qwen7b | qwen2.5:7b | 5 | 15/20 (75%) | 80% | 67% | 0 | Có | [JSON](../runs/v5-local-qwen7b_B_base_ollama_20261110T171353375157.json) |
| v6-cloud-reference | gpt-4o-mini | 11 | 19/20 (95%) | 100% | 100% | 0 | Có | [JSON](../runs/v6-cloud-reference_B_base_openai_20261110T171144446413.json) |
| v5-local-cloud-check | gpt-4o-mini | 5 | 18/20 (90%) | 95% | 100% | 0 | Có | [JSON](../runs/v5-local-cloud-check_B_base_openai_20261110T171224367249.json) |

### Kết luận có bằng chứng

- Qwen 3B: 15% → 25% → 70%; rút prompt thay đổi +10 điểm phần trăm, giảm tập tool thay đổi +45 điểm phần trăm.
- Qwen 7B: 20% → 25% → 75%; rút prompt thay đổi +5 điểm phần trăm, giảm tập tool thay đổi +50 điểm phần trăm.
- Kiểm tra ngược trên cùng model cloud: 95% → 90% (-5 điểm phần trăm). Không thể kết luận bản tối ưu local tốt hơn cho mọi model.
- Đây là một lần chạy mỗi cấu hình trên 20 case. Kết quả gợi ý giảm nhiễu từ số tool giúp model nhỏ gọi tool tốt hơn trong bộ này; chưa chứng minh quan hệ nhân quả tổng quát hoặc độ ổn định qua nhiều lần chạy.

- Payload base giống nhau ở toàn bộ 8 cấu hình: **True**. Snapshot prompt/tools khớp hash trong log: **True**.
- Hash chỉ nhận diện prompt/tools, không bao gồm code hoặc toàn bộ môi trường chạy.

### Mẫu lỗi quan sát được

Các ô là số **case**, không phải số lần gọi. Nhóm có thể giao nhau; loại provider exception trước khi đếm. Không dùng nhãn `failure_type` gán sẵn làm nguyên nhân.

| Version | Tool lạ | Sai tên tool | JSON lỗi | Cần tool nhưng không gọi | Thiếu clarify | Gọi lặp y hệt | Tool ở no-tool | Đúng routing, sai args |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v6-qwen3b | 0 | 10 | 0 | 7 | 3 | 0 | 1 | 0 |
| v6-qwen7b | 0 | 7 | 0 | 9 | 3 | 0 | 0 | 0 |
| v4-local-qwen3b | 0 | 4 | 0 | 5 | 3 | 0 | 0 | 5 |
| v4-local-qwen7b | 0 | 6 | 0 | 4 | 3 | 0 | 0 | 5 |
| v5-local-qwen3b | 0 | 4 | 0 | 1 | 3 | 0 | 1 | 1 |
| v5-local-qwen7b | 0 | 3 | 0 | 1 | 2 | 0 | 0 | 1 |
| v6-cloud-reference | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| v5-local-cloud-check | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 1 |

Case ID ví dụ và số backend tool errors nằm trong [bonus-summary.json](bonus-summary.json). Bảng CSV để phân tích: [local_challenge.csv](../analysis/local_challenge.csv).

### Điều kiện chạy được ghi nhận

- [Snapshot môi trường](local_challenge/environment.json), thời điểm 2026-11-10T17:18:32.796681+07:00; Ollama 0.40.15.
- `qwen2.5:3b`: 3.1B, Q4_K_M; capabilities ghi nhận: completion, tools.
- `qwen2.5:7b`: 7.6B, Q4_K_M; capabilities ghi nhận: completion, tools.
- Provider local: `max_tokens=512`, timeout 120.0 giây, retries 0; giữ cùng giới hạn khi so sánh các stage.
- `/api/ps` quan sát `qwen2.5:7b` có `context_length=4096` tại snapshot. Đây là context được quan sát, **không phải `num_ctx` được đặt rõ trong từng request**, và không chứng minh context của mọi case đã được log riêng.

## Giới hạn cần giữ khi demo

- Accuracy chấm tool routing/arguments, không chấm đầy đủ chất lượng câu trả lời hoặc độ đúng của dữ liệu tool.
- Provider errors bị loại khỏi mẫu số; luôn đọc số measured và provider_error_cases cùng accuracy.
- Các case multi-turn eval gộp lịch sử vào một message, không thay thế hội thoại live nhiều vòng.
- Model suy luận local; các tool web/arXiv vẫn gọi mạng và gửi truy vấn tới dịch vụ tương ứng.
- source_audit kiểm tra metadata/loại nguồn, không xác minh sự kiện hay tính độc lập của nhiều nguồn.
- X/Twitter có HTTPError trong các run đã ghi; PASS routing không chứng minh backend nguồn đó hoạt động.
- Không có tin nhắn Telegram thật được gửi trong kiểm chứng bonus này.

## Chạy lại

```text
python scripts/run_local_challenge.py --stage baseline
python scripts/run_local_challenge.py --stage v4-local
python scripts/run_local_challenge.py --stage v5-local
python scripts/run_local_challenge.py --stage cloud-reference
python scripts/run_local_challenge.py --stage cloud-check
python -m pytest --junitxml=artifacts/pytest-results.xml
python scripts/summarize_bonus.py
```

Runner giữ log có sẵn nếu đúng model/hash và đủ 20 measured case; dùng `--force` khi chủ động chạy lại. Thực hiện từng stage, đọc log rồi mới quyết định vòng tiếp theo. Script tổng hợp chỉ đọc bằng chứng, không gọi API.
