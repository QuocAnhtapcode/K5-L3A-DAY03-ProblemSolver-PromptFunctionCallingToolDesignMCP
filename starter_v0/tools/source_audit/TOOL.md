---
name: source_audit
track: bonus
kind: local_knowledge
provider: local_python
requires_env: []
inputs: [items, official_domains]
outputs: [items, item_count, domain_count, domains, missing_url_count, invalid_url_count, duplicate_url_count, category_counts, caveat]
side_effect: false
---
# source_audit

Kiểm tra độ đầy đủ của trích dẫn và phân loại sơ bộ nguồn trong danh sách
item đã có. Tool chạy offline và **không xác minh sự thật, uy tín, tác giả,
peer review, nội dung trang hay tính độc lập giữa các nguồn**.

## Khi dùng / khi không dùng

- Dùng khi cần kiểm tra danh sách thiếu URL, URL lỗi/trùng hoặc độ đa dạng
  tên miền trước khi trình bày bản tin.
- Không dùng để kết luận một tuyên bố đúng/sai hoặc rằng nhiều bài cùng
  khẳng định một điều đã được xác minh độc lập.
- Không dùng để tìm nguồn mới. Cần tra cứu thật thì dùng `lookup`, `fetch`
  hoặc các tool research tương ứng.

## Input và phân loại

`items` phải là mảng object; mảng rỗng hợp lệ. Mỗi object có thể có `url` và
các metadata khác. Item thiếu URL hoặc URL sai không làm hỏng toàn bộ lời
gọi: chúng được gắn issue để người dùng thấy chỗ thiếu bằng chứng.

`official_domains` là mảng hostname thuần tùy chọn do người gọi khai báo,
không chứa `https://`, path, port hoặc thông tin đăng nhập. Mặc định rỗng.
Tool không tự suy đoán hay xác minh danh sách này.

- `preprint`: `arxiv.org` hoặc subdomain; chưa mặc nhiên có peer review.
- `social`: X/Twitter, Facebook, Reddit, TikTok, LinkedIn và subdomain.
- `declared_official`: khớp chính xác hoặc subdomain của một hostname trong
  `official_domains`; chỉ là khai báo của người gọi.
- `other_web`, `missing_url`, `invalid_url`: các trường hợp còn lại.

Social/preprint vẫn giữ category tương ứng ngay cả khi người gọi đưa nó
vào danh sách official. `openai.com.evil.example` không khớp `openai.com`.

Trùng URL được so theo scheme/host không phân biệt hoa thường, giữ path và
query, bỏ fragment; không theo redirect và không bỏ tracking.

## Output và lỗi

Trả bản sao của `items`, mỗi item được thêm `audit: {domain, category, issues}`,
cùng các số đếm và `caveat` nêu rõ giới hạn. Các trường metadata gốc được giữ.
Sai kiểu mảng/object hoặc cấu hình official domain không hợp lệ trả
`{tool: source_audit, error: ..., message: ...}` thay vì raise.
