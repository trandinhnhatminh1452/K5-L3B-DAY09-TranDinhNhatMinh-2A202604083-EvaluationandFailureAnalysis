# Judge audit

Chạy kiểm tra:
```bash
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | ĐẠT (0.757 ≥ 0.6, 0.857 ≥ 0.8, 0.800 ≥ 0.7) | **Dùng** |
| helpful | 100 | 0.375 | 1.000 | 0.300 | KHÔNG ĐẠT (κ = 0.375 < 0.6, R = 0.300 < 0.7) | **Loại** |

## ≥5 case audit thủ công

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa Rubric |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người đúng | Câu reply: *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* Xưng hô "anh/em", dùng từ "nha", "check" suồng sã, vi phạm tone chuyên nghiệp của LogiX. **Sửa rubric:** Bổ sung quy định cấm đại từ nhân xưng phi chuẩn mực (chỉ chấp nhận *"Dạ, LogiX..."*). |
| 2 | H-017 | PASS | FAIL | Người đúng | Câu reply: *"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."* Có cấu trúc thân mật thái quá ("bạn ơi", "nha"). Judge bị lừa bởi tiền tố "Dạ". **Sửa rubric:** Thêm tiêu chí phạt các thán từ suồng sã ("nha", "nhé", "bạn ơi"). |
| 3 | H-029 | PASS | FAIL | Người đúng | Câu reply: *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* Giọng điệu cộc lốc, mang tính gạt bỏ khách hàng. Judge không phân biệt được sự lịch sự giả tạo. **Sửa rubric:** Thêm hướng dẫn đánh giá thái độ phục vụ khách hàng (không được yêu cầu khách ngừng liên hệ). |
| 4 | H-042 | FAIL | PASS | Người đúng | Câu reply: *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* Câu trả lời rất chuẩn và hữu ích, nêu rõ thời gian hoàn tiền. Judge phạt nhầm vì cho rằng cung cấp thông tin thời gian không chắc chắn. **Sửa rubric:** Nêu rõ hướng dẫn thời gian hoàn tiền 3-5 ngày là thông tin chuẩn được khuyến khích. |
| 5 | H-051 | FAIL | PASS | Người đúng | Câu reply: *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* Khách hàng hiểu rõ từ "refund" trong ngữ cảnh thương mại điện tử. Judge quá khắt khe khi bắt bẻ việc dùng từ mượn. **Sửa rubric:** Cho phép các thuật ngữ thương mại phổ biến như "refund", "ship" nếu không gây hiểu lầm. |

## Kết luận
- **Tiêu chí bị loại (`helpful`) và lý do:**
  - Ma trận nhầm lẫn của `helpful`: `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`.
  - Recall chỉ đạt **0.30** (bỏ lọt tới 21 trong tổng số 30 ca không đạt yêu cầu thực tế). Tỉ lệ lỗi thực tế hiệu chỉnh bằng Rogan-Gladen là 30.0% trong khi tỉ lệ lỗi quan sát qua judge chỉ là 9.0%.
  - Judge bị đánh lừa bởi phong cách xin lỗi dài dòng hoặc câu chữ văn hoa của LLM nhưng thực chất không đưa ra hướng giải quyết cụ thể cho khách hàng. Nếu dùng judge này làm gate release thì 70% các phản hồi vô dụng sẽ bị lọt lưới.
- **Rủi ro còn lại:**
  - Dữ liệu `judge_tone` mới chỉ kiểm nghiệm trên tập replay public; khi ra môi trường production cần có nhãn người trên tập held-out mới liên tục để tránh hiện tượng data drift hoặc judge overfitting.
