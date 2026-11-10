# Day 03 Lab v2 Report — ProblemSolver Research Agent

Cập nhật ngày 10/11/2026. Số liệu lấy từ run JSON, version log, transcript và pytest thực tế.

## Team

- **Team:** ProblemSolver.
- **Thành viên:** Hoàng Quốc Anh, Đỗ Thị Thanh Bình, Lê Gia Hưng, Hà Quang Vinh.
- **Provider/model:** OpenAI / `gpt-4o-mini`.
- **Repo nhóm:** [ResearchAgentToolEval](https://github.com/QuocAnhtapcode/K5-L3A-DAY03-ProblemSolver-ResearchAgentToolEval).
- **Demo hiện tại:** `v8-bonus`, UI Streamlit, 14 tool; chọn OpenAI hoặc Ollama. Lịch sử MVP v0–v6 được giữ nguyên bên dưới.

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Research agent tìm thông tin trên web, đọc URL, lọc bài trùng, tách đường dẫn, kiểm tra metadata nguồn và tạo tệp Markdown/JSON/CSV để tải về. UI cho chọn OpenAI hoặc hai model Ollama đã cài. Agent tiếp nhận thông tin bổ sung và đính chính; thao tác xuất bản luôn được phân biệt với tra cứu.

**Link dùng thử:** [ProblemSolver Research Desk](https://regarded-height-belongs-manor.trycloudflare.com).

**Link trên máy chạy demo:** [http://127.0.0.1:8501](http://127.0.0.1:8501).

UI có chat nhiều lượt, câu hỏi gợi ý, nguồn/các bước xử lý, tải transcript, danh sách công cụ và bảng kết quả đánh giá. [Ảnh UI bonus đã kiểm tra](bonus-ui-ollama.jpg).

Link công khai là Cloudflare Quick Tunnel: cần giữ máy và tiến trình app/tunnel chạy; hostname sẽ đổi khi mở tunnel mới. Đây là link demo, không có cam kết uptime. Xem [deployment.json](deployment.json) và [tài liệu Cloudflare](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## A2. Tool agent có

| Tool | Chức năng | Nhóm thêm? |
|---|---|---|
| `clarify` | Hỏi thông tin thiếu hoặc xin xác nhận | Không |
| `timeline` | Lấy bài đăng của một tài khoản X/Twitter | Không |
| `social_search` | Tìm bài đăng X/Twitter theo chủ đề | Không |
| `lookup` | Tìm thông tin/tin tức web theo thời gian | Không |
| `fetch` | Đọc một URL đã biết | Không |
| `format` | Trình bày item đã có thành Markdown | Không |
| `send` | Gửi Telegram khi xác nhận; web demo chỉ tạo bản nháp | Không |
| `policy` | Tra bộ chính sách mẫu của lab | Không |
| `papers` | Tìm paper/preprint arXiv | Không |
| `paper_text` | Tải PDF arXiv và trích văn bản | Không |
| `deduplicate` | Bỏ URL trùng/tracking, giữ item đầu tiên và metadata | **Có** |
| `extract_links` | Tách HTTP(S) URL từ văn bản/Markdown đã có | **Có** |
| `source_audit` | Kiểm tra URL thiếu/lỗi/trùng và loại nguồn theo metadata | **Có** |
| `export_digest` | Tạo tệp Markdown/JSON/CSV để tải về | **Có** |

**Có 4 tool do nhóm tự viết**, đạt điều kiện “hơn 3 tool mới + UI”. Policy và hai tool arXiv đã qua smoke test 3/3; ba tool bổ sung đều có routing eval và unit test. Nguồn X/Twitter vẫn trả HTTPError trong các run đã ghi. `source_audit` chỉ đánh giá metadata nguồn, không xác minh sự thật. Chế độ Ollama tối ưu dùng 5 tool cho bộ base; chế độ OpenAI dùng đủ 14 tool.

## A3. Câu hỏi mẫu để thử

1. “Tìm 2 tin AI trong tuần này, tóm tắt ngắn bằng tiếng Việt và kèm nguồn.”
2. “Đọc và tóm tắt 3 ý chính: https://www.python.org/about/”.
3. “Tóm tắt bài viết này giúp tôi.” Sau khi được hỏi, bổ sung URL ở lượt sau.
4. “Lọc URL trùng, giữ bản đầu tiên: https://example.org/ai?utm_source=mail ; https://example.org/ai#intro ; https://example.org/robotics”.
5. “Theo chính sách nội bộ mẫu, một tweet viral đã đủ để xác nhận sự kiện chưa?”

---

# PHẦN B — Chi tiết / Bằng chứng

## B1. Version Evidence

Nguồn: [version_log.csv](version_log.csv). Metric chính là `summary.case_accuracy`, được tính trên số case đo được sau khi loại lỗi provider.

| Version | Bộ | Đạt/được đo | Accuracy | Routing | Args | Multi-turn | Lỗi provider | Run JSON |
|---|---|---:|---:|---:|---:|---:|---:|---|
| v0 | base | 13/20 | 65% | 75% | 65% | 100% | 0 | [v0](../runs/v0_B_base_openai_20261110T102336357810.json) |
| v1 | base | 9/10 | 90% | 90% | 90% | 100% | 10 | [v1](../runs/v1_B_base_openai_20261110T105116416581.json) |
| v2 | base | 19/20 | 95% | 100% | 95% | 100% | 0 | [v2](../runs/v2_B_base_openai_20261110T111110058962.json) |
| v3 | base | 19/20 | 95% | 100% | 95% | 100% | 0 | [v3](../runs/v3_B_base_openai_20261110T113153288818.json) |
| v4 | base | 19/20 | 95% | 100% | 95% | 100% | 0 | [v4](../runs/v4_B_base_openai_20261110T113537033825.json) |
| v5 | group cũ | 1/1 | 100% | 100% | 100% | Không có | 0 | [v5](../runs/v5_B_group_openai_20261110T114142849968.json) |
| v6 | group mở rộng | 10/10 | 100% | 100% | 100% | 100% | 0 | [v6](../runs/v6_B_group_openai_20261110T115504277225.json) |

| Version | Thay đổi / giả thuyết | Kết luận |
|---|---|---|
| v0 | Đo starter trước tối ưu | Có 7 case FAIL để phân tích |
| v1 | Thay prompt xấu bằng scope, hỏi lại, xác nhận, routing và args | Chỉ đo 10/20 case; trên 10 case chung với v0 tăng 7/10 → 9/10 |
| v2 | Description rõ chức năng và ranh giới sẽ giảm nhầm tool | 19/20 base; trên 10 case chung với v1 đạt 10/10 |
| v3 | Convention args cụ thể sẽ giảm sai giá trị | Vẫn 19/20; chưa có bằng chứng tăng điểm so với v2 |
| v4 | Điều kiện của `send` rõ hơn sẽ phân biệt yêu cầu gửi và xác nhận | Vẫn 19/20; R12 chưa đạt yêu cầu `response_type` |
| v5 | Model chọn `deduplicate` khi có dữ liệu cần lọc | Một case routing đạt; tool lọc 3 item còn 2 |
| v6 | Mở rộng routing/args/boundary; hoàn thành unit test và siết boolean của `send` | 10/10 case nhóm đạt; không so trực tiếp với group cũ 1 case |

Base đầy đủ tăng **65% ở v0 → 95% ở v2–v4**, chênh 30 điểm phần trăm. Tại thời điểm MVP v6, chưa chạy lại base trên bộ 11 tool, nên không gán điểm v4 cho v6. Đợt bonus đã chạy lại riêng bản 14 tool và đối chứng đúng snapshot v6; xem bảng bổ sung dưới đây. v1 có 6 lỗi kết nối và 4 timeout; 90% không phải kết quả trên đủ 20 case.

| Version | Prompt hash (12 ký tự đầu) | Tools hash (12 ký tự đầu) |
|---|---|---|
| v0 | `eb1c8179815b` | `5b22a2476d41` |
| v1 | `508a98436ab2` | `5b22a2476d41` |
| v2 | `508a98436ab2` | `3bff7d02ec01` |
| v3 | `508a98436ab2` | `371e4cf60e41` |
| v4 | `508a98436ab2` | `c2d76a248cca` |
| v5 | `508a98436ab2` | `33f07f67b016` |
| v6 | `508a98436ab2` | `33f07f67b016` |

Hash đầy đủ và `artifact_version` nằm trong CSV/run JSON. Hai hash hiện chưa bao gồm code tool, UI hoặc dataset; v5 và v6 vì thế cùng hash dù có thay đổi test, guard và số case. [Bảng phân tích toàn bộ run](../analysis/all_runs.csv).

### Bản bonus hiện tại và thay đổi có bằng chứng

| Version | Bộ | Đạt/được đo | Accuracy | Lỗi provider | Run |
|---|---|---:|---:|---:|---|
| v8-bonus | base | 19/20 | 95% | 0 | [v8-bonus_B_base_openai_20261110T170920329810.json](../runs/v8-bonus_B_base_openai_20261110T170920329810.json) |
| v8-bonus | group | 16/16 | 100% | 0 | [v8-bonus_B_group_openai_20261110T170816913898.json](../runs/v8-bonus_B_group_openai_20261110T170816913898.json) |
| v8-bonus | extension | 8/10 | 80% | 0 | [v8-bonus_B_extension_openai_20261110T170913555070.json](../runs/v8-bonus_B_extension_openai_20261110T170913555070.json) |

v7-bonus tích hợp 14 tool, thêm 6 case và giữ nguyên các case cũ. Group v7 đạt 15/16: G11 gọi `extract_links` hai lần với cùng arguments. v8 chỉ thêm một quy tắc vào description của tool: một lần gọi xử lý toàn bộ văn bản, không lặp cùng arguments. Group v8 đạt 16/16; đây là một lần chạy mỗi cấu hình, chưa chứng minh ổn định thống kê. Base v7/v8 đều 19/20; không gán mức tăng nào cho các thay đổi không cải thiện điểm.

Base vẫn còn R12: hỏi nội dung bằng `clarify(text)` thay vì `yes_no`. Extension còn E01 chọn đúng policy nhưng `policy_area=all`; E06 chỉ kiểm tra policy ở bước đầu theo yêu cầu “trước”, trong khi evaluator một lượt mong cả lookup. Giữ nguyên dataset, báo cáo đúng giới hạn thay vì sửa case để tăng điểm.

## B2. Failure Analysis

Đọc `actual_tool_calls`, `failures` và `observed_mismatch` trong v0; nhãn lỗi gán sẵn chưa chắc là nguyên nhân quan sát được.

| Case | Hành vi v0 | Lỗi | Thay đổi / trạng thái |
|---|---|---|---|
| R03 | `lookup(query="AI news")` | Expected query `AI` | Tách chủ đề khỏi topic/timeframe; đạt ở v2–v4 |
| R08 | Dùng `send` trả lời bài toán | Expected no tool | Quy tắc scope và cấm dùng send như chat; đạt ở v2–v4 |
| R10 | Đoán tài khoản, gọi `timeline` | Thiếu clarify, thừa truy xuất | v1 còn nhầm social_search; description v2 làm rõ và case đạt |
| R11 | Bịa URL `https://example.com/article` | Thiếu clarify, thừa fetch | Hỏi URL khi chưa có; đạt ở v2–v4 |
| R12 | Gọi send khi chưa xác nhận | Thiếu clarify, thừa send | v2–v4 đã hỏi bằng clarify nhưng text thay vì yes_no; vẫn FAIL tự động |
| R13 | Gọi đúng hai tool nhưng query `AI news`, thiếu topic | Sai args, dù nhãn case là wrong_tool | Chủ đề riêng, topic=news và timeframe đúng; đạt ở v2–v4 |
| R14 | Dùng send trả lời yêu cầu Fibonacci | Expected no tool | Quy tắc ngoài scope; đạt ở v2–v4 |

**R12 cần manual review:** “Đăng bản tin này…” chưa kèm nội dung. v4 hỏi xin nội dung và kênh bằng `clarify(response_type="text")`, chưa gửi; evaluator đòi `yes_no`. Sai kiểu câu hỏi theo rubric không đồng nghĩa đã xuất bản trái phép. Giữ nguyên base case và ghi nhận sự khác nhau này.

## B3. Team Eval Cases

Nguồn: [eval_group.json](../data/eval_group.json), [run v6](../runs/v6_B_group_openai_20261110T115504277225.json). Ở MVP v6 có **5 single-turn + 5 multi-turn**, đủ phase, nhãn lỗi và metadata. Bản hiện tại giữ nguyên 10 case này và thêm 6 case, tổng **16 case: 8 single-turn + 8 multi-turn**; v8 đạt **16/16**.

| Case | Lượt | Nội dung | Expected | v6 |
|---|---|---|---|---|
| G01_deduplicate_supplied_items | Single | Lọc URL trùng từ items đã có | deduplicate | PASS |
| G02_two_specific_urls | Single | Đọc hai URL cụ thể | Hai fetch | PASS |
| G03_social_top_and_limit | Single | Chủ đề robotics, top 4 | social_search, Top, limit=4 | PASS |
| G04_missing_clipboard_url | Single | Nhắc clipboard nhưng chưa có URL | clarify, text | PASS |
| G05_capabilities_without_tool | Single | Hỏi khả năng và nguyên tắc | Không tool | PASS |
| G06_carry_month_switch_topic | Multi | Đổi chủ đề, giữ tháng | lookup, news, month | PASS |
| G07_correct_ranking_and_quantity | Multi | Sửa Top → Latest, 8 → 2 | social_search, Latest, limit=2 | PASS |
| G08_use_corrected_url | Multi | URL đính chính và query string | fetch URL mới | PASS |
| G09_cancel_publication | Multi | Hủy xuất bản sau khi được hỏi | Không tool, không gửi | PASS |
| G10_cancel_research_switch_out_of_scope | Multi | Hủy research, chuyển sang bài toán | Không tool | PASS |

Độ phủ gồm cả 6 nhãn lỗi được phép. G01 chỉ chấm routing; logic xử lý mảng object/URL được kiểm tra bằng unit test. Backend `social_search` ở G03/G07 trả HTTPError nhưng routing/args vẫn PASS. Multi-turn eval gộp lịch sử vào một user message, chỉ xử lý lượt cuối. Với case no-tool, evaluator chưa kiểm tra chất lượng text trong `behavior`.

### Sáu case bổ sung cho bonus

| Case | Lượt | Hành vi kiểm tra | v8 |
|---|---|---|---|
| G11_extract_links_from_supplied_text | Single | Tách URL từ đoạn có sẵn, max_links=2 | PASS |
| G12_audit_supplied_citations | Single | Soát metadata và nguồn thiếu URL | PASS |
| G13_export_existing_items_json | Single | Xuất file JSON thật từ items đã có | PASS |
| G14_extract_links_carry_quantity | Multi | Giữ văn bản cũ, lấy giới hạn mới nhất | PASS |
| G15_audit_declared_official_domain | Multi | Dùng đúng official_domains user khai báo | PASS |
| G16_export_corrected_format | Multi | Giữ items, đổi Markdown sang CSV | PASS |

## B4. Live Chat Evidence

Đã chạy **chat.py với OpenAI thật, 4 lượt**, không dùng fake provider. [Transcript CLI](../transcripts/v6_openai_20261110T120147152912.transcript.json).

```text
python -X utf8 chat.py --provider openai --model gpt-4o-mini --version v6
```

| Lượt | Yêu cầu | Tool thực tế | Kết quả |
|---|---|---|---|
| 1 | Tóm tắt “bài này” nhưng thiếu URL | Không tool | Hỏi URL bằng text, không bịa link |
| 2 | Bổ sung python.org/about, yêu cầu 3 ý chính | fetch | Có dữ liệu, tóm tắt 3 ý và dẫn link |
| 3 | Lọc 3 item có URL tracking/fragment trùng | deduplicate | 3 item → 2 item; loại 1 |
| 4 | Tìm 2 tin AI trong tuần và kèm nguồn | lookup | query=AI, topic=news, timeframe=week, max_results=2; có kết quả và nguồn |

Cả 4 lượt kết thúc `answered`; ba lượt có tool không trả error. Lượt 1 hỏi đúng thông tin thiếu nhưng không gọi structured clarify. Positive case trong eval đang ép `tool_choice="required"`, còn chat live dùng tự động; cần kiểm tra riêng khác biệt này.

**Smoke test UI công khai:** bấm “Lọc bài trùng”, agent gọi đúng tool, giữ 2 bài và báo loại 1. Nút tải lịch sử tải được JSON khớp dữ liệu máy chủ; CRLF/LF khác nhau không làm thay đổi JSON.

- [Transcript UI kiểm tra](../transcripts/web_v6_openai_20261110T123039043431_5d1e5bdf.transcript.json).
- [JSON tải thật từ nút UI](ui-download.transcript.json).
- [Ảnh kết quả UI](demo-ui.jpg).

Hai transcript trên là bằng chứng của MVP. Đợt bonus bổ sung transcript và tệp tải được nêu riêng bên dưới. Các phiên thử UI không được trích làm bằng chứng đã được dọn khỏi bản nộp.

### Kiểm chứng giao diện bonus

- Chọn OpenAI/Ollama và hai model `qwen2.5:3b`, `qwen2.5:7b` trên UI thật. Qwen 7B đã trả lời trực tiếp câu hỏi về khả năng; [ảnh UI](bonus-ui-ollama.jpg).
- Xuất CSV bằng OpenAI thật; nút tải nằm ngay dưới câu trả lời. Tệp tải thật có 2 dòng và byte khớp tệp máy chủ; [CSV kiểm chứng](demo-export.csv).
- Metric sidebar lọc đúng provider, model và hash prompt/tools của phiên; không dùng điểm cloud-check của bộ 5 tool cho UI OpenAI 14 tool.
- [demo-verification.json](demo-verification.json) lưu HTTP, hash CSV, đường dẫn transcript và kết quả kiểm thử; bằng chứng MVP cũ được giữ ở [demo-verification-v6.json](demo-verification-v6.json).
- [Transcript xuất CSV](../transcripts/web_v8-bonus_openai_gpt-4o-mini_20261110T173947060197_2305a74a.transcript.json).
- [Transcript UI Ollama](../transcripts/web_v8-bonus_ollama_qwen2.5_7b_20261110T174044370950_8d091d3a.transcript.json).

## B5. UI, unit test và bonus

| Hạng mục | Bằng chứng | Kết quả |
|---|---|---|
| UI và hơn 3 tool mới | [app.py](../app.py), registry/YAML và 4 TOOL.md | 14 tool; 4 tool nhóm thêm: deduplicate, extract_links, source_audit, export_digest |
| Unit test đầy đủ | [JUnit XML](pytest-results.xml) | **229 passed, 0 failed, 0 skipped**; 2 warning protobuf có sẵn |
| Routing tool mới | [eval_group.json](../data/eval_group.json), run v8 group | **16/16**; mỗi tool mới có case riêng |
| Policy + arXiv | [bonus-live-tools.json](bonus-live-tools.json) | **3/3**; policy local, papers và paper_text chạy mạng thật |
| Xác nhận/hủy Telegram | [bonus-confirmation.json](bonus-confirmation.json), transcript đi kèm | **4/4 bằng OpenAI thật, executor dry-run; không gửi Telegram** |
| Small Local Model Challenge | [BONUS.md](BONUS.md), B7, 8 run JSON | 2 model khác kích thước, 2 vòng tối ưu trên cả hai và cloud-check |
| Poster demo | [poster.html](poster.html) | Một trang; số liệu sinh từ log thật |

Tool mới có kiểm thử happy path, input lỗi và nhánh error trả dict. Regression tests bắt lỗi guard `send` trước đây chấp nhận chuỗi/số truthy: guard hiện chỉ nhận boolean True. Có kiểm tra CSV formula injection, path traversal, không ghi đè file, tải tệp đúng thư mục, snapshot/resume sai dataset và hiển thị metric sai bộ artifact.

Bộ arXiv nay chia sẻ giới hạn thời gian giữa request search/PDF, retry HTTP 429, kiểm chữ ký PDF và tránh để lại file tải dở. Provider Ollama có timeout 120 giây, không SDK retry và giới hạn 512 token cho các lượt chạy đã ghi; OpenAI/OpenRouter giữ mặc định cũ.

Theo lựa chọn của người dùng, **không gửi Telegram thật**. Hội thoại xác nhận là kịch bản kiểm thử với phản hồi model thật, không được coi là sự cho phép xuất bản của người dùng. Executor kiểm thử chặn mọi thao tác gửi, kể cả khi model gọi sớm hoặc đổi nội dung. Web demo cũng chỉ tạo bản nháp. Guard boolean trong CLI chưa tự ràng buộc xác nhận với payload như một hệ thống phê duyệt production.

Policy là handbook mẫu của lab; source_audit là kiểm tra metadata. Model local vẫn có thể dùng API web bên ngoài khi thực thi retrieval.

## B6. Reflection

- **Prompt:** phù hợp cho scope, hỏi dữ liệu thiếu, dùng đính chính mới nhất, phối hợp nhiều bước và nguyên tắc xác nhận.
- **Tool declaration:** phù hợp để phân biệt nguồn tài khoản/chủ đề/URL và mô tả handle, news, timeframe, Top/Latest, kiểu tham số.
- **Code/test:** kiểm tra request HTTP, mapping, input lỗi và guard boolean; prompt không sửa được bug Python.
- **Manual review:** cần cho R12, chất lượng câu trả lời no-tool, trích dẫn, và trường hợp PASS nhưng tool result báo lỗi.
- **Giới hạn thực nghiệm:** v1 gộp nhiều rule, chưa cô lập đóng góp từng rule; v1 mất 10 case; v5/v6 có số case khác nhau. Không quy mọi chênh lệch điểm cho một chỉnh sửa đơn lẻ.
- **Tiếp theo:** kiểm tra quyền/cấu hình nguồn X, test chất lượng nguồn, structured clarify khi chat tự chọn tool, guard gắn xác nhận với payload, lưu dữ liệu tool có cấu trúc qua các lượt và tiếp tục cải thiện các lỗi clarify/context ở model local và các case còn FAIL, sau khi đã có base của bản 14 tool.
- **Tái lập:** đợt bonus đã snapshot prompt/tools và kiểm payload dataset khi resume. Hash code/môi trường chưa đầy đủ, nên vẫn giữ giới hạn này trong kết luận.

## B7. Small Local Model Challenge


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


Chi tiết tái lập và điều kiện môi trường: [BONUS.md](BONUS.md), [environment.json](local_challenge/environment.json). UI local dùng bản 5 tool này; OpenAI vẫn dùng bộ đầy đủ.

## Chạy lại demo

Tại `starter_v0`, dùng Python của Anaconda trong terminal VS Code. App tự đọc `.env`.

```text
python -m pip install -r requirements.txt
python scripts/start_demo.py
```

Giữ lệnh chạy trong lúc demo. Chỉ cần local thì dùng `python scripts/start_demo.py --local-only`. Nếu cổng 8501 đang được dùng, thêm `--port 8502`. Binary Cloudflare chính thức được lưu ở thư mục tạm của máy, không đưa binary/key vào repo. Xem [DEMO.md](../DEMO.md).
