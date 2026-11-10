---
name: extract_links
track: bonus
kind: local_formatter
provider: local_python
requires_env: []
inputs: [text, max_links]
outputs: [items, link_count, unique_link_count, candidates_seen, rejected_count, truncated]
side_effect: false
---
# extract_links

Trích liên kết HTTP(S) từ văn bản người dùng đã cung cấp: đoạn Markdown,
email đã sao chép, ghi chú hoặc kết quả của một tool khác. Không gọi mạng,
không đọc clipboard và không tự tìm kiếm trang web.

## Khi dùng / khi không dùng

- Dùng khi người dùng muốn lấy danh sách URL từ một đoạn văn bản đã có.
- Không dùng thay `fetch` để đọc trang hay `lookup` để tìm nguồn mới.
- Không khẳng định URL tồn tại hoặc nội dung trong URL là đúng.

## Input

- `text`: chuỗi văn bản. Chuỗi rỗng hợp lệ và trả danh sách rỗng.
- `max_links`: số nguyên từ 1 đến 200, mặc định 50. Boolean và chuỗi số
  không được chấp nhận làm số nguyên.

Tool giữ thứ tự xuất hiện và chỉ giữ lần đầu của mỗi URL giống hệt nhau.
Đây không phải chuẩn hóa URL: tracking/query và fragment khác nhau vẫn là
các URL khác nhau; dùng `deduplicate` nếu cần chuẩn hóa chúng.

Dấu câu văn xuôi ở cuối URL và dấu ngoặc đóng thừa của Markdown được bỏ.
Ngoặc cân bằng bên trong URL được giữ. URL HTTP(S) có hostname/cổng không
hợp lệ hoặc có username/password bị loại. Các scheme khác không được trích.
Vì văn bản thuần có thể mơ hồ, dấu câu thực sự thuộc cuối URL có thể bị bỏ;
hãy cung cấp URL đã percent-encode nếu cần giữ chính xác dấu đó.

## Output và lỗi

`items` gồm `{url, title, source}`; `title` mặc định chính là URL, không phải
tiêu đề lấy từ trang. `unique_link_count` đếm mọi URL hợp lệ không trùng,
`link_count` là số URL trả về sau giới hạn, `truncated` báo còn URL bị cắt.
`candidates_seen` và `rejected_count` mô tả những candidate HTTP(S) tìm thấy.

Input sai kiểu hoặc giới hạn không hợp lệ trả
`{tool: extract_links, error: ..., message: ...}` thay vì raise.
