---
name: deduplicate
track: core
kind: local_formatter
provider: local_python
requires_env: []
inputs: [items]
outputs: [items, input_count, output_count, duplicates_removed]
side_effect: false
---
# deduplicate

Lọc các bài trùng URL từ danh sách dữ liệu đã có, trước khi tổng hợp thành bản tin.
Không gọi mạng, không cần API key và không ghi file.

## Khi dùng

- Người dùng yêu cầu bỏ bài hoặc liên kết trùng trong một danh sách đã cung cấp.
- Các item đã có từ người dùng hoặc kết quả của các tool truy xuất ở vòng trước.

Không dùng để tìm nguồn, xác minh nội dung hay trình bày Markdown. Nếu chưa có
danh sách, gọi `clarify` hoặc lấy dữ liệu trước; không tự bịa item.

## Input và quy tắc so sánh

`items` phải là một mảng object; mỗi object cần `url` là URL HTTP(S) tuyệt đối.
Mảng rỗng hợp lệ. Các trường khác như `title`, `summary`, `source` và metadata
được giữ nguyên.

Khóa so sánh URL:

- Bỏ khoảng trắng đầu/cuối, fragment `#...`, `utm_*`, `fbclid` và `gclid`.
- Chuẩn hóa chữ hoa/thường của scheme và hostname; coi cổng mặc định 80/443
  tương đương với URL không ghi cổng của cùng protocol.
- Giữ khác biệt HTTP/HTTPS, path phân biệt hoa/thường, dấu `/` cuối path,
  cùng giá trị và thứ tự các query parameter còn lại.

Giữ item xuất hiện đầu tiên cho mỗi khóa; không gộp bài chỉ vì cùng tiêu đề.
URL và dữ liệu trả về vẫn là bản gốc, không sửa danh sách đầu vào.
Các URL redirect về cùng trang hoặc các bài cùng nội dung nhưng URL khác nhau
không được phát hiện vì tool không truy cập mạng.

## Output và lỗi

Trả `items` đã lọc cùng `input_count`, `output_count` và `duplicates_removed`.
Ví dụ 3 item có 1 URL trùng sẽ trả 2 item và `duplicates_removed=1`.

Sai kiểu input, thiếu URL hoặc URL không hợp lệ trả về
`{tool: deduplicate, error: ..., message: ...}` thay vì raise exception.
Nếu một item không hợp lệ, toàn bộ lời gọi trả lỗi; không trả một danh sách đã
lọc dở khiến người dùng hiểu nhầm là đầy đủ.
