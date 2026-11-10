---
name: export_digest
track: bonus
kind: local_formatter
provider: local_python
requires_env: []
inputs: [items, format, filename]
outputs: [path, filename, format, mime_type, item_count, bytes_written]
side_effect: local_file_write
---
# export_digest

Xuất các item research đã có thành file Markdown, JSON hoặc CSV tải về.
Chỉ ghi file cục bộ dưới `starter_v0/exported_digests/`; không gửi email,
đăng Telegram hoặc công khai file ra dịch vụ bên ngoài.

## Khi dùng / khi không dùng

- Dùng khi người dùng yêu cầu lưu, xuất hoặc tải file từ dữ liệu đã cung cấp
  hay kết quả tool có sẵn.
- `format` chỉ tạo văn bản hiển thị; `export_digest` tạo file thật.
- Không tìm kiếm, đọc trang web hoặc tự bịa item để xuất. Nếu thiếu dữ liệu,
  lấy dữ liệu hoặc hỏi lại trước.

## Input

- `items`: mảng object; mảng rỗng hợp lệ. Các field `title`, `url`, `source`,
  `summary`, `section`, nếu có, phải là chuỗi hoặc null. URL không rỗng phải
  dùng HTTP(S), có hostname/cổng hợp lệ và không có thông tin đăng nhập.
- `format`: `markdown` (mặc định), `json` hoặc `csv`.
- `filename`: tên cơ sở tùy chọn, ví dụ `ai-weekly` hoặc `ai-weekly.md`.
  Chỉ nhận chữ ASCII, số, `_`, `-`, với tối đa 80 ký tự ở phần stem và
  extension khớp định dạng. Không nhận đường dẫn, `..` hoặc tên thiết bị
  Windows như `CON`. Bỏ trống để tool tự tạo tên duy nhất.

Không ghi đè file đã tồn tại. Lời gọi lỗi không được trả đường dẫn thành công.
JSON giữ metadata có thể serialize; Markdown/CSV dùng năm field chuẩn trên.
CSV dùng UTF-8 BOM để Excel hiển thị tiếng Việt; cell có thể được Excel hiểu
là công thức được thêm dấu nháy đơn ở đầu. Markdown escape nội dung và giữ
URL nguồn. Tool không xác minh tính đúng đắn của nội dung được xuất.

## Output và lỗi

Trả đường dẫn tuyệt đối `path`, `filename`, `format`, `mime_type`, `item_count`
và số byte thực sự đã ghi `bytes_written`. UI chỉ cho tải file dưới thư mục
export cố định. Lỗi input, serialize, trùng tên hoặc ghi file trả
`{tool: export_digest, error: ..., message: ...}` thay vì raise.
