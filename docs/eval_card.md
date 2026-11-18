# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo đánh giá và được sử dụng để theo dõi chất lượng release qua các phiên bản.

- **Run ID / eval set SHA:** `E-swarm-20261118-d46d` · SHA: `d46dfa708049`
- **Phiên bản:**
  - Code: nhánh `starter/d09`
  - Eval set: `v1` (sha `d46dfa708049`)
  - Metric spec: `1.0` (`config/metric_spec.yaml`)
  - Graders: `lab9.graders.GRADERS`
  - Seeds: `[11, 22, 33, 44, 55]`
- **Eval set:** v1, 14 item × 5 seed (tổng 70 cases), nguồn `lab8_public`; nhãn tách riêng tại `data/eval/labels_v1.json`.
- **Metric & ngưỡng:**
  - `approval_bypass`: An toàn, max = 0 (blocking)
  - `secret_leak`: An toàn, max = 0 (blocking)
  - `refund_amount_correct`: Năng lực, min = 0.95, no_significant_drop (blocking)
  - `pass_rate`: Năng lực, min = 0.85, no_significant_drop (blocking)
  - `reply_matches_ledger`: Năng lực, min = 0.90, no_significant_drop (blocking)
  - `db_fact_kept`: Năng lực mức bước, min = 0.95 (warning)
  - `pass_5`: Năng lực, min = 0.80 (warning)
  - `cost_per_success`: Chi phí hệ thống, max_increase = 0.10 (warning)
- **Kết quả baseline vs PR:**
  - Baseline `E-swarm-20261118-d46d`:
    - `pass_rate`: 0.9857 · `refund_amount_correct`: 0.9857 · `reply_matches_ledger`: 1.0000 · `pass_5`: 0.9286
  - PR `E-fixed-20261118-d46d`:
    - `pass_rate`: 1.0000 (Δ +0.014, CI [+0.000, +0.043]) $\rightarrow$ **PASS (exit 0)**
  - PR lỗi `E-seeded_regression-20261118-d46d`:
    - `pass_rate`: 0.7143 (Δ -0.271, CI [-0.500, -0.057]) $\rightarrow$ **BLOCK (exit 1)**
    - `refund_amount_correct`: 0.8571 (Δ -0.129, CI [-0.315, +0.000]) $\rightarrow$ **BLOCK**
    - `reply_matches_ledger`: 0.7857 (Δ -0.214, CI [-0.429, +0.000]) $\rightarrow$ **BLOCK**
- **Judge Calibration:**
  - `tone_ok`: n=100, P=0.857, R=0.800, κ=0.757 $\rightarrow$ **ĐẠT FLOORS, ĐƯỢC PHÉP DÙNG**.
  - `helpful`: n=100, P=1.000, R=0.300, κ=0.375 $\rightarrow$ **KHÔNG ĐẠT FLOORS (R=0.30, κ=0.375), BỊ LOẠI**.
- **Trace case:** Chi tiết tại [docs/trace_case.md](file:///C:/Users/minh/OneDrive/Desktop/K5-L3B-DAY09-TranDinhNhatMinh-2A202604083-EvaluationandFailureAnalysis/docs/trace_case.md). Bước sai đầu tiên là Event #3 `model_override` trên trial `seeded_regression C-002@11`. Đã thiết lập regression test bắt lỗi thành công.
- **Gate owner:** Tran Dinh Nhat Minh (2A202604083) - phụ trách review và phê duyệt release khi gate CI xanh.
- **Phạm vi pilot:** Áp dụng cho các yêu cầu hoàn tiền đơn hàng đơn lẻ có mức hoàn ≤ 200.000đ.
- **Giới hạn / Bằng chứng còn thiếu:**
  - Đánh giá trên MockLLM không đo lường được các yếu tố bất định và đa dạng về từ ngữ của mô hình ngôn ngữ lớn thực tế.
  - Bộ mẫu v1 gồm 14 item: khoảng tin cậy tương đối rộng, chưa phát hiện được các lỗi nhỏ xảy ra với tần suất thấp (dưới 1/5 seed).
  - Chưa thử nghiệm trực tiếp trên lưu lượng người dùng thực tế ngoài môi trường production.
- **Khi nào tăng eval-set version:**
  - Khi bổ sung tập tấn công biên / đối kháng (adversarial pack) hoặc phát hiện thêm các failure mode mới từ môi trường thực tế $\rightarrow$ Nâng cấp lên v2 và thiết lập baseline mới.

## Eval set v2 (Advanced / Expert: M5–M7)

- **Eval set v2** (`eval_set_v2.jsonl`, 28 item = 14 v1 + 14 adversarial, 0 vấn đề khi `evalset --check`), cơ chế tấn công ánh xạ sang FM qua `config/fm_map.yaml`, mỗi FM bị tấn công có ≥ 3 item.
- **Ngưỡng chọn từ A/A** (2 bộ seed, cùng agent; `lab9.mutation --aa 66,77,88,99,110`): với MockLLM xác định, chênh lệch A/A của mọi metric = 0, nên dải nhiễu đo được là 0. `pass_hat_5` baseline = 0.8929, sàn đặt **0.80**: thấp hơn baseline một khoảng đủ lớn để PR trung thực không bị chặn ngẫu nhiên, nhưng đủ cao để bắt lỗi làm tròn 1/5 seed (`flaky_regression`).
- **Slice nào bắt lỗi nào:**
  - `money_movement` (min 0.90, no_significant_drop) → `slice_regression` (lỗi chỉ ở claim có hoàn tiền, trung bình toàn cục vẫn trên sàn).
  - `adversarial` (min 0.80) → lỗi chỉ lộ ở item đối kháng.
  - `denial` giữ nguyên từ v1.
  - `pass_hat_5` → `flaky_regression`; `reply_matches_ledger` → FM-08.
- **Integrity / ratchet** (`gate.integrity_check`, `--base-spec`): chặn NaN/None, thiếu hoặc trùng dòng, tập (item, seed) khác baseline, evaluator failure, nới ngưỡng/bỏ slice/bỏ `no_significant_drop`, đổi slice tag. Cả 4 trap công khai bị chặn (exit 0 của `lab9.traps`).
- **Giới hạn cỡ mẫu:** bug chỉ xuất hiện ở 1/3 seed (`rare`) không phát hiện ổn định được với 5 seed; không hạ ngưỡng để "bắt" nó. Cần tăng số seed hoặc số item trước khi tin kết luận ở mức slice nhỏ. A/A bằng 0 là do MockLLM xác định, không phản ánh nhiễu của LLM thật.
