---
name: deduplicate
track: core
kind: local_formatter
provider: local Python
requires_env: []
inputs: [items]
outputs: [items, input_count, item_count, removed_count]
side_effect: false
---
# deduplicate

Loại nguồn trùng URL trong danh sách đã thu thập trước khi định dạng bản tin.
Giữ mục xuất hiện đầu tiên theo thứ tự ban đầu, sao chép nông từng dictionary
và giữ nguyên URL cùng các trường dữ liệu. Chạy cục bộ, không gọi mạng.

Khi so sánh, bỏ fragment sau `#` và tham số theo dõi `utm_*`, `fbclid`, `gclid`.
Tên tham số theo dõi được giải mã percent-encoding và so sánh không phân biệt
hoa thường. Scheme và hostname cũng không phân biệt hoa thường. Các khác biệt
HTTP/HTTPS, `www`, chữ hoa thường trong path, dấu `/` cuối, thông tin đăng nhập,
port tường minh và tham số thật vẫn được giữ. Tham số thật giữ nguyên cách viết,
thứ tự và số lần lặp.

Đầu vào là list các dictionary, mỗi mục có `url` HTTP/HTTPS tuyệt đối, khác rỗng,
có hostname và port hợp lệ nếu được cung cấp. List rỗng hợp lệ. Nếu có mục sai,
toàn bộ lời gọi trả error dictionary. Dữ liệu đầu vào được giữ nguyên.

Ví dụ đầu vào

```json
{"items": [{"url": "https://example.com/a", "title": "Nguồn đầu"}, {"url": "https://example.com/a?utm_source=mail#intro"}]}
```

Kết quả

```json
{"tool": "deduplicate", "items": [{"url": "https://example.com/a", "title": "Nguồn đầu"}], "input_count": 2, "item_count": 1, "removed_count": 1}
```
