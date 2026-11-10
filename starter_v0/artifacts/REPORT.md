# Day 03 Lab v2 Report — Research Agent

Nhóm Problem Solver. Báo cáo tổng hợp từ run JSON, version log, unit test và chat API thật ngày 2026-11-10.

Phần A được yêu cầu trước 16:30. Bản hoàn thiện này được cập nhật sau mốc 16:30 ngày 2026-11-10, chưa có bằng chứng nộp đúng mốc đó.

## Team

- Tên nhóm Problem Solver.
- Thành viên Hoàng Quốc Anh, Đỗ Thị Thanh Bình, Lê Gia Hưng, Hà Quách Vinh.
- Provider chính OpenRouter, model openai/gpt-4o-mini. Thử nghiệm local dùng Ollama với qwen2.5:0.5b và qwen3:1.7b.

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Agent tìm tin web, đọc URL, xử lý danh sách nguồn và tổng hợp kết quả có dẫn link. Tool mới deduplicate loại nguồn trùng URL trước khi tạo bản tin. CLI có bước hỏi lại khi thiếu thông tin và hỏi xác nhận Telegram.

- Link UI trên máy đang chạy [Research Agent](http://127.0.0.1:8501).
- Link dùng thử công khai chưa có. Địa chỉ trên chỉ phục vụ máy đang chạy UI.
- Tích hợp X/Twitter hiện gặp RapidAPI 403 trong run nhóm. Demo đã kiểm chứng web, đọc URL, lọc trùng và xác nhận/hủy gửi.

## A2. Tool agent có

| Tool | Làm được gì | Nhóm tự thêm |
|---|---|---|
| clarify | Hỏi thiếu thông tin hoặc xác nhận trước hành động | Có sẵn |
| timeline | Lấy bài gần đây của một tài khoản X | Có sẵn |
| social_search | Tìm bài trên X theo từ khóa | Có sẵn |
| lookup | Tìm nguồn web và tin tức | Có sẵn |
| fetch | Đọc nội dung URL đã có | Có sẵn |
| format | Trình bày dữ liệu thành Markdown | Có sẵn |
| send | Gửi Telegram khi có xác nhận, tích hợp qua CLI | Có sẵn |
| policy | Tra tài liệu nội bộ đi kèm lab | Có sẵn |
| papers | Tìm bài nghiên cứu arXiv | Có sẵn |
| paper_text | Đọc văn bản PDF arXiv | Có sẵn |
| deduplicate | Lọc nguồn trùng URL, giữ nguồn đầu tiên và báo số đã loại | Có |

## A3. Câu hỏi mẫu để thử

1. Tìm trên web 2 tin về năng lượng mặt trời trong tuần này và kèm đường dẫn nguồn.
2. Đọc báo cáo khác giúp tôi, tôi chưa gửi đường dẫn.
3. Đọc https://www.python.org/about/ và tóm tắt thành 3 gạch đầu dòng.
4. Loại nguồn trùng trong danh sách [{"url":"https://example.com/a"},{"url":"https://example.com/a?utm_source=demo"}].
5. Trong CLI, yêu cầu gửi một nội dung lên Telegram, quan sát câu hỏi xác nhận rồi trả lời hủy.

---

# PHẦN B — Chi tiết / Bằng chứng

## B1. Version Evidence

Bảng dưới dùng case_accuracy của base eval làm metric. Các run base hợp lệ có đủ 20 ca được chấm và 0 lỗi provider. Run v0 đầu tiên với 20 lỗi thiếu key được giữ trong runs nhưng không dùng làm baseline.

| Version | Changed Artifact | Hypothesis | Metric Before | Metric After | Run File |
|---|---|---|---|---|---|
| v0 | baseline | Thiết lập điểm tham chiếu cho các vòng tối ưu | — | 0.70 | runs/v0_B_base_openrouter_20261110T102512349490.json |
| v1 | artifacts/system_prompt.md | Yêu cầu gọi clarify với response_type=text khi thiếu dữ kiện sẽ giúp R10 và R11 chọn đúng tool | 0.70 | 0.90 | runs/v1_B_base_openrouter_20261110T103400605227.json |
| v2 | artifacts/system_prompt.md | Yêu cầu xác nhận bằng clarify với response_type=yes_no trước khi gửi sẽ giúp R12 pass | 0.90 | 0.90 | runs/v2_B_base_openrouter_20261110T111610673146.json |
| v3 | artifacts/system_prompt.md | Thay chỉ dẫn gửi ngay bằng quy tắc hỏi khi thiếu thông tin sẽ khôi phục R10 và R11 trong khi vẫn giữ bước xác nhận của R12 | 0.90 | 0.85 | runs/v3_B_base_openrouter_20261110T112016932894.json |
| v4 | artifacts/tools.yaml | Làm rõ ranh giới giữa social_search và lookup và ưu tiên yêu cầu mới nhất về nguồn sẽ giúp M02 và M06 chọn lookup | 0.85 | 0.80 | runs/v4_B_base_openrouter_20261110T112510066933.json |
| v5 | artifacts/system_prompt_1.md | Tách chủ đề vào query, loại tin vào topic và thời gian vào timeframe sẽ giúp lookup truyền đúng tham số. | 0.80 | 0.90 | runs/v5_B_base_openrouter_20261110T113318973956.json |
| v6 | artifacts/tools.yaml | Làm rõ bước xác nhận trong khai báo send sẽ giúp R12 gọi clarify với response_type=yes_no. Bản sửa đặt nhầm tool nên chưa kiểm chứng đúng thay đổi dự kiến. | 0.90 | 0.95 | runs/v6_B_base_openrouter_20261110T113913492719.json |
| v7 | artifacts/tools.yaml | Đặt mô tả đúng chức năng của social_search và send sẽ giúp agent hỏi xác nhận bằng clarify với response_type=yes_no. Bản sửa này còn nhầm mô tả giữa hai tool. | 0.95 | 0.95 | runs/v7_B_base_openrouter_20261110T121725453147.json |
| v5-local-cloud | artifacts/system_prompt_local_v5.md + artifacts/tools_local_v4.yaml | Bản artifact tối ưu local có thể tiếp tục hoạt động tốt trên cloud. | 0.95 | 1.00 | runs/v5-local-cloud_B_base_openrouter_20261110T171059023964.json |

Bản v5-local-cloud đạt 20/20 với artifacts/system_prompt_local_v5.md và artifacts/tools_local_v4.yaml, ngân sách 512 token. Đây là cấu hình dùng trong transcript demo. UI hiện đọc artifacts/system_prompt.md và artifacts/tools.yaml theo code app.py, nên cần phân biệt cấu hình UI với cấu hình CLI đã đánh giá. Chi tiết các model local và đối chứng cùng cấu hình có ở B7.

## B2. Failure Analysis

| Case và run | Failure Type | Actual Tool Calls | What Failed | Fix và kết quả |
|---|---|---|---|---|
| v0 R08 | out_of_scope | send chứa lời giải tích phân | Gọi tool cho câu hỏi ngoài phạm vi | v1 gọi 0 tool và được chấm PASS. Nội dung từ chối cần xem thủ công |
| v0 R10 | missing_info | timeline(screenname=sama) | Tự đoán tài khoản X | v1 thêm quy tắc clarify(text), R10 PASS |
| v0 R11 | missing_info | fetch(URL example.com/article) | Tự đoán URL | v1 hỏi URL qua clarify(text), R11 PASS |
| v0 R12 | wrong_boundary | send(text=Bản tin này) | Thiếu câu hỏi xác nhận | Các bản v1 đến v7 thay đổi nhưng chưa ổn định. Bản v5-local-cloud gọi clarify(yes_no) và PASS |
| v0 R13 | wrong_arg_value | lookup(query=AI news, thiếu topic), social_search | Query khác expected và thiếu topic=news | v5 thêm quy tắc tách chủ đề, loại tin và thời gian. R03/R13 PASS trong run v5 |
| v0 R14 | out_of_scope | send chứa code Fibonacci | Gọi công cụ gửi cho yêu cầu code | v1 gọi 0 tool và được chấm PASS. Bộ chấm chưa kiểm tra từ chối đúng nghĩa |
| v7 R12 | wrong_arg_value | clarify(response_type=text) | Hỏi nội dung thay cho xác nhận yes_no | Prompt ngắn và YAML local đã sửa được kiểm tra trên cloud, R12 PASS |
| v5-local R10 | wrong_arg_value | clarify không truyền response_type | Code mặc định text nhưng bộ chấm đòi arg tường minh | Cần mô tả arg rõ hơn trong vòng tiếp theo. Kết quả vẫn ghi FAIL |

Điểm eval chấm tên tool và tập tham số expected. Chất lượng câu trả lời, việc từ chối đúng nghĩa và kết quả API cần đọc thêm trong tool_results hoặc transcript. G02 và G08 của bộ group được chấm PASS nhưng tool X trả HTTP 403.

## B3. Team Eval Cases

Đủ 10 ca, 5 single-turn và 5 multi-turn. Run runs/v7_B_group_openrouter_20261110T155755110105.json đạt 10/10 với artifact v7+p01c147b33fa2+tda5603314bdd. Các ca nhiều lượt chấm quyết định ở lượt cuối dựa trên ngữ cảnh.

| Case ID | Loại | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|---|
| G01_deduplicate_collected_sources | single | Danh sách đã có và yêu cầu loại trùng URL phải chọn deduplicate. Unit test kiểm tra xử lý dữ liệu và các số đếm. | deduplicate | PASS |
| G02_timeline_handle_and_limit | single | Bài đăng của một tài khoản cụ thể phải dùng timeline, bỏ @ khỏi screenname và truyền đúng limit=4. | timeline | PASS về routing/args, API trả 403 |
| G03_web_news_month_and_result_count | single | Tách chủ đề vào query, tin tức vào topic=news, tháng này vào timeframe=month và số kết quả vào max_results=3. | lookup | PASS |
| G04_clarify_missing_report_url | single | Chưa có URL thì hỏi link qua clarify(text), tránh tự đoán địa chỉ và gọi fetch. | clarify | PASS |
| G05_format_existing_items_as_bullets | single | Khi đã có dữ liệu và chỉ yêu cầu trình bày thì gọi format(template=bullets), tránh gọi thêm tool tra cứu. | format | PASS |
| G06_fetch_corrected_url_from_history | multi | Lấy URL từ lịch sử và ưu tiên URL đã sửa ở lượt sau, chỉ gọi fetch cho link mới. Ca này chấm URL được gọi. | fetch | PASS |
| G07_web_news_timeframe_correction | multi | Giữ chủ đề, loại tin và số kết quả từ lịch sử, đồng thời thay timeframe=month bằng week theo yêu cầu mới nhất. | lookup | PASS |
| G08_social_search_sort_correction | multi | Giữ nguồn X, chủ đề và limit=3, thay search_type=Top bằng Latest sau khi người dùng đổi cách sắp xếp. | social_search | PASS về routing/args, API trả 403 |
| G09_deduplicate_sources_from_history | multi | Dùng danh sách nguồn từ lượt trước để gọi deduplicate ở lượt cuối. Ca eval chấm routing, unit test kiểm tra dữ liệu và số đếm. | deduplicate | PASS |
| G10_cancel_telegram_publication | multi | Ưu tiên lệnh hủy ở lượt cuối và không gọi tool gửi. Bộ chấm tự động kiểm tra không có tool call, nội dung câu trả lời cần đọc thủ công. | no_tool | PASS |

Hai ca deduplicate kiểm tra routing. Unit test kiểm tra dữ liệu và số đếm của tool. Ca hủy gửi tự động kiểm tra không có tool call, còn câu trả lời được kiểm tra thủ công.

## B4. Live Chat Evidence

Chạy chat.py qua OpenRouter bằng kịch bản 6 lượt, mỗi phản hồi dùng API thật và tool thật. Transcript transcripts/v5-local-cloud_openrouter_20261110T174601282203.transcript.json.

Artifact v5-local-cloud+p3c8ce1621d2d+t8e03986360c9. MODEL_MAX_TOKENS=512. Sáu lượt đều hoàn thành hoặc dừng đúng tại bước chờ người dùng, không có lỗi provider/tool trong transcript này.

| Turn | User Request | Tool Calls | Version Evidence | Outcome |
|---|---|---|---|---|
| 1 | Tìm trên web 2 tin về năng lượng mặt trời trong tuần này. Trả lời ngắn gọn và kèm đường dẫn nguồn. | lookup | v5-local-cloud | Tìm được 2 nguồn web và trả lời kèm link |
| 2 | Tôi cần đọc một báo cáo khác nhưng chưa gửi URL. Hãy hỏi tôi đường dẫn trước. | clarify | v5-local-cloud | clarify(text), chờ người dùng cung cấp URL |
| 3 | Đây là URL của báo cáo tôi muốn đọc: https://www.python.org/about/ . Hãy đọc và tóm tắt nội dung trang trong 3 gạch đầu dòng. | fetch | v5-local-cloud | Đọc URL vừa bổ sung, tóm tắt trong 3 gạch đầu dòng |
| 4 | Loại nguồn trùng URL trong danh sách đã có, giữ nguồn đầu tiên và báo số nguồn bị loại: [{"title":"Nguồn A","url":"https://example.com/a"},{"title":"Nguồn A chia sẻ lại","url":"https://example.com/a?utm_source=demo#intro"},{"title":"Nguồn B","url":"https://example.org/b"}] | deduplicate | v5-local-cloud | 3 nguồn đầu vào, giữ 2, loại 1 nguồn trùng |
| 5 | Tôi muốn gửi nội dung "Kết quả demo nghiên cứu đã sẵn sàng." lên Telegram. Hãy hỏi tôi xác nhận trước khi gửi. | clarify | v5-local-cloud | clarify(yes_no) hỏi xác nhận đúng nội dung Telegram, chờ trả lời |
| 6 | Hủy yêu cầu gửi Telegram. Chỉ trả lời rằng đã hủy yêu cầu. | 0 tool | v5-local-cloud | Người dùng hủy, agent xác nhận đã hủy và không gọi tool |

Chạy lại kịch bản trong terminal bằng lệnh dưới, sau đó nhập các yêu cầu ở bảng theo thứ tự. Nhập /exit để kết thúc.

```powershell
$env:MODEL_MAX_TOKENS = '512'
.\.venv\Scripts\python.exe .\chat.py --provider openrouter --model openai/gpt-4o-mini --version v5-local-cloud --system-prompt .\artifacts\system_prompt_local_v5.md --tools .\artifacts\tools_local_v4.yaml
```

## B5. Bonus Evidence

| Hạng mục | Evidence File | What Worked | Giới hạn |
|---|---|---|---|
| Telegram hỏi xác nhận/hủy | transcripts/v5-local-cloud_openrouter_20261110T174601282203.transcript.json, lượt 5 và 6 | Agent hỏi yes_no và tôn trọng lệnh hủy | Chưa có token/chat ID và transcript gửi Telegram thành công |
| Small Local Model Challenge | analysis/local_comparison.csv, analysis/local_runs.csv, các run local | Hai model, hai vòng tối ưu, kiểm tra ngược cloud, xem B7 | Local tốt nhất 45% trên bộ base trong thí nghiệm này |
| UI bắt buộc | app.py | Streamlit chạy tại http://127.0.0.1:8501, health trả ok, AppTest khởi tạo thành công | Chưa có link công khai. UI dùng cấu hình mặc định, CLI demo dùng snapshot ghi ở B4 |
| Unit tests bắt buộc | tests/test_tools_todo.py, tests/test_provider_options.py, analysis/pytest_output.txt | 120 passed, 0 failed, 0 skipped | Có một cảnh báo deprecation của anyio |

Các test API dùng fake_http, chặn kết nối thật và dùng key giả. Đã hoàn thiện 14 TODO của tool có sẵn. Tool mới deduplicate có 32 ca test, kiểm tra giữ nguồn đầu tiên, dữ liệu lỗi, tracker, fragment và bảo toàn đầu vào.

Test đã bắt lỗi trong lúc viết tool mới khi URL không có query và URL chỉ có utm_source bị coi là khác nhau. Đã sửa và giữ test regression. Không ghi nhận bug mới được sửa trong code tool có sẵn. Unit test thiếu Telegram env kiểm tra trả lỗi và không có request, trong khi eval chọn đúng send vẫn có thể được chấm theo routing/args.

## B6. Reflection

- System prompt quy định cách quyết định chung, gồm hỏi lại, ưu tiên yêu cầu mới nhất, routing theo ý định, nguồn tin và xác nhận hành động. Prompt ngắn cải thiện routing local nhưng chưa giải quyết hết lỗi tham số.
- tools.yaml quy định chức năng, ranh giới và định dạng args cho từng tool. Mô tả social_search/send bị đặt nhầm gây mơ hồ. Bản tools_local_v4.yaml sửa nghĩa hai mô tả và được giữ riêng để so sánh.
- Những phần cần manual review gồm chất lượng tóm tắt, độ mới của nguồn, từ chối yêu cầu ngoài phạm vi, lỗi API đi kèm PASS và xác nhận đúng nội dung gửi. Điểm 100% base/group chưa xác nhận các tiêu chí này.
- Việc tiếp theo trước khi nộp là có link UI công khai, thống nhất cấu hình UI với bản demo được chọn và xử lý quyền RapidAPI cho các tool X. Nếu trình diễn gửi Telegram thật, cần cấu hình kênh/bot và xác nhận nội dung cụ thể trước hành động.
## B7. Small Local Model Challenge (bonus)

Thí nghiệm ngày 2026-11-10. Dùng hai model đã cài trên máy là qwen2.5:0.5b và qwen3:1.7b, cả hai có tool calling và kích thước không quá 8B. Đây là hai model nhỏ hơn các ví dụ 3B và 7B trong hướng dẫn lab.

Cấu hình so sánh

- Bộ đánh giá là data/eval_base.json gồm 20 ca, trong đó 6 ca nhiều lượt. Tất cả run trong bảng có 20 ca được chấm và 0 lỗi provider.
- Cloud dùng OpenRouter với openai/gpt-4o-mini. Local dùng Ollama 0.40.15 với qwen2.5:0.5b và qwen3:1.7b. MODEL_MAX_TOKENS=512 và temperature=0 cho các run so sánh.
- Baseline dùng artifacts/system_prompt_local_baseline.md và artifacts/tools_local_baseline.yaml, sao chép nguyên bản system_prompt_1.md cùng 11 tool hiện tại. Bản cloud tốt nhất cũ dùng YAML khác nên đã chạy lại cloud đối chứng cùng artifact.
- Lần thử model 0.5B không giới hạn đầu ra bị lặp và đã dừng trước khi có run JSON hoàn chỉnh. Thêm biến môi trường MODEL_MAX_TOKENS tùy chọn và áp dụng 512 cho toàn bộ so sánh. Đối chứng cloud sơ bộ trước giới hạn cũng đạt 19/20 và được lưu riêng trong version_log.csv.
- Prompt có 173 từ ở baseline và 136 từ ở v5-local. Giữ nguyên bộ 11 tool trong các vòng, sửa nội dung khai báo bằng bản YAML riêng.

| Version | Model (provider) | Prompt / Tools | PASS | case_accuracy | tool_routing | argument | multiturn | Lời gọi tool lỗi | Run File |
|---|---|---|---|---|---|---|---|---|---|
| v7-cloud-reference | openai/gpt-4o-mini (openrouter) | baseline / baseline | 19/20 | 95.00% | 100.00% | 95.00% | 100.00% | 8 | runs/v7-cloud-reference_B_base_openrouter_20261110T170150872584.json |
| v7-qwen05b | qwen2.5:0.5b (ollama) | baseline / baseline | 3/20 | 15.00% | 20.00% | 15.00% | 0.00% | 9 | runs/v7-qwen05b_B_base_ollama_20261110T170258171772.json |
| v7-qwen17b | qwen3:1.7b (ollama) | baseline / baseline | 9/20 | 45.00% | 45.00% | 45.00% | 33.33% | 2 | runs/v7-qwen17b_B_base_ollama_20261110T170608900825.json |
| v4-local | qwen3:1.7b (ollama) | baseline / local-v4 | 8/20 | 40.00% | 50.00% | 40.00% | 50.00% | 9 | runs/v4-local_B_base_ollama_20261110T170846019979.json |
| v5-local | qwen3:1.7b (ollama) | local-v5 / local-v4 | 9/20 | 45.00% | 75.00% | 45.00% | 33.33% | 10 | runs/v5-local_B_base_ollama_20261110T171200695776.json |
| v5-local-cloud | openai/gpt-4o-mini (openrouter) | local-v5 / local-v4 | 20/20 | 100.00% | 100.00% | 100.00% | 100.00% | 8 | runs/v5-local-cloud_B_base_openrouter_20261110T171059023964.json |

local-v4 là artifacts/tools_local_v4.yaml. local-v5 là artifacts/system_prompt_local_v5.md. File analysis/local_comparison.csv lưu bảng đầy đủ cùng hash và cấu hình token.

Hai vòng tối ưu

- v4-local chỉ chuyển mô tả social_search và send về đúng chức năng. Tổng điểm giảm 45% xuống 40%, routing tăng 45% lên 50%, nhiều lượt tăng 2/6 lên 3/6. R02, R13 và M04 chuyển sang PASS, còn R05, R06, R11 và R14 trượt lại. Đổi mô tả giúp một số ca chọn nguồn nhưng chưa cải thiện điểm tổng.
- v5-local thay prompt bằng hướng dẫn ngắn theo ý định, yêu cầu tool call có cấu trúc, giữ nguyên YAML v4. Tổng điểm tăng 40% lên 45%, routing tăng 50% lên 75%, nhiều lượt giảm 3/6 xuống 2/6.
- Các ca cải thiện từ v4 sang v5 gồm R05_limit_arg, R11_missing_url, R14_out_of_scope_coding, M01_clarify_then_fill. Các ca trượt lại gồm R03_web_news_routing, M02_carryover_timeframe, M06_switch_tool.
- Cả ba ca cần hỏi lại R10, R11 và R12 đều gọi được clarify ở v5. R10 vẫn thiếu response_type trong lời gọi, còn R12 dùng text thay cho yes_no. R10 được code mặc định thành text nhưng bộ eval chấm tham số model gửi nên vẫn FAIL.

Lỗi theo số ca, các mẫu lỗi có thể giao nhau

| Mẫu lỗi | 0.5B baseline | 1.7B baseline | v4-local | v5-local |
|---|---|---|---|---|
| Có tool sai hoặc tool không khai báo | 13 | 5 | 8 | 4 |
| Đúng tên tool nhưng tham số sai theo bộ chấm | 1 | 0 | 2 | 6 |
| Có _invalid_json_arguments | 0 | 0 | 0 | 0 |
| Cần gọi tool nhưng không có tool call | 2 | 5 | 2 | 1 |
| Thiếu lời gọi clarify mong đợi | 3 | 2 | 3 | 0 |
| Tên tool bị gọi lặp trong một ca | 0 | 0 | 0 | 0 |

Kết luận dựa trên log

- Với model 1.7B, hướng dẫn routing ngắn và yêu cầu tool call thực tế giúp tỷ lệ chọn tool tăng từ 50% lên 75% ở vòng thứ hai và số ca thiếu clarify giảm từ 3 xuống 0. Lỗi handle, số lượng, nguồn và giữ ngữ cảnh vẫn khiến điểm toàn ca chỉ đạt 45%. Hai vòng này chưa vượt điểm baseline local 45%.
- Bản v5-local chạy trên cloud đạt 20/20, so với 19/20 của đối chứng cloud cùng ngân sách 512 token. R12 chuyển từ clarify(text) sang clarify(yes_no). Đây là kết quả của một lần chạy trên 20 ca, cần đánh giá thêm khi muốn kết luận rộng hơn.
- Các lỗi thực thi tool được đếm riêng ở bảng. RapidAPI có phản hồi 403/429 trong các run, ngoài ra model local có thể truyền tham số không hợp lệ gây TypeError. Điểm PASS phản ánh tên tool và tham số theo expected subset, chưa xác nhận chất lượng nội dung hoặc quyền truy cập dịch vụ.
- Model local phù hợp khi ưu tiên suy luận trên máy và có thể chấp nhận giới hạn chất lượng đã đo. Với tác vụ nghiên cứu nhiều nguồn cần chọn tool và giữ ngữ cảnh tốt, bản cloud hiện đạt kết quả cao hơn trên bộ base. Các tool web vẫn gửi truy vấn ra dịch vụ ngoài.

Cách chạy lại

Chạy trong starter_v0 bằng PowerShell. Đặt ngân sách token trước các lệnh để dùng đúng cấu hình so sánh.

```powershell
$env:MODEL_MAX_TOKENS = '512'
.\.venv\Scripts\python.exe .\run_eval.py --provider openrouter --model openai/gpt-4o-mini --version v7-cloud-reference --suite base --eval-cases .\data\eval_base.json --system-prompt .\artifacts\system_prompt_local_baseline.md --tools .\artifacts\tools_local_baseline.yaml
.\.venv\Scripts\python.exe .\run_eval.py --provider ollama --model qwen2.5:0.5b --version v7-qwen05b --suite base --eval-cases .\data\eval_base.json --system-prompt .\artifacts\system_prompt_local_baseline.md --tools .\artifacts\tools_local_baseline.yaml
.\.venv\Scripts\python.exe .\run_eval.py --provider ollama --model qwen3:1.7b --version v7-qwen17b --suite base --eval-cases .\data\eval_base.json --system-prompt .\artifacts\system_prompt_local_baseline.md --tools .\artifacts\tools_local_baseline.yaml
.\.venv\Scripts\python.exe .\run_eval.py --provider ollama --model qwen3:1.7b --version v4-local --suite base --eval-cases .\data\eval_base.json --system-prompt .\artifacts\system_prompt_local_baseline.md --tools .\artifacts\tools_local_v4.yaml
.\.venv\Scripts\python.exe .\run_eval.py --provider ollama --model qwen3:1.7b --version v5-local --suite base --eval-cases .\data\eval_base.json --system-prompt .\artifacts\system_prompt_local_v5.md --tools .\artifacts\tools_local_v4.yaml
.\.venv\Scripts\python.exe .\run_eval.py --provider openrouter --model openai/gpt-4o-mini --version v5-local-cloud --suite base --eval-cases .\data\eval_base.json --system-prompt .\artifacts\system_prompt_local_v5.md --tools .\artifacts\tools_local_v4.yaml
```
