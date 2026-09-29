# Tiêu chí chấm điểm (RUBRIC)

## 1. Bảng điểm tổng quan (100 điểm bắt buộc)

| Tiêu chí | Điểm |
|----------|-----:|
| Core coding + required tests pass | 50 |
| Golden dataset 20 QA | 15 |
| LLM-as-a-Judge rubric design | 10 |
| Benchmark, 5 Whys, failure analysis | 15 |
| Code quality, type hints, regression strategy | 10 |
| **Total** | **100** |

> 📌 **Lưu ý quan trọng:** **Benchmark score không quyết định điểm lab.** LLM output có thể thay đổi theo model và từng lần chạy. Điểm được chấm dựa trên pipeline đúng, dataset có chất lượng, evidence hợp lệ và phân tích có căn cứ — không dựa trên việc pass rate phải đạt một con số cố định.

---

## 2. Chi tiết đánh giá, bằng chứng & điều kiện mất điểm

### 2.1 Core coding + required tests pass (50 điểm)
- **Bằng chứng:** 
  - Toàn bộ TODO bắt buộc trong `template.py` / `solution/solution.py` được hoàn thiện: Task 1 (Data Models, `overall_score`), Task 2 (RAGASEvaluator với 3 answer metrics + 2 retrieval metrics), Task 3 (LLMJudge, `detect_bias`), Task 4 (BenchmarkRunner, `run_regression`), Task 5 (FailureAnalyzer, 5 Whys, improvement log).
  - Lệnh `pytest tests/ -v` đạt **41 passed, 1 skipped** (test reranking của Exercise 3.5 được skip nếu chưa làm bonus).
- **Điều kiện mất điểm:**
  - Có test bắt buộc bị fail (trừ điểm theo tỷ lệ test fail).
  - Can thiệp hoặc sửa đổi file test để làm bài pass (hủy toàn bộ 50 điểm code).
  - Thiếu logic xử lý ngoại lệ hoặc sai signature hàm/class.

### 2.2 Golden dataset 20 QA (15 điểm)
- **Bằng chứng:**
  - File `golden_dataset.json` chứa đầy đủ đúng 20 QA pairs.
  - Phân bổ đúng theo stratified sampling: 5 Easy + 7 Medium + 5 Hard + 3 Adversarial.
  - Context và expected_answer được trích dẫn chính xác từ corpus `data/technology_store/*.md`.
  - Chạy `python validate_golden_dataset.py` báo kết quả **PASS**.
- **Điều kiện mất điểm:**
  - Thiếu số lượng QA hoặc sai tỷ lệ phân bổ độ khó.
  - Context bịa đặt hoặc không có provenance trong corpus.
  - Chạy `validate_golden_dataset.py` báo `FAIL`.

### 2.3 LLM-as-a-Judge rubric design (10 điểm)
- **Bằng chứng:**
  - Hoàn thành Exercise 3.3 trong `exercises.md`.
  - Thiết kế rubric chấm điểm 1–5 chi tiết cho ít nhất 2 tiêu chí đánh giá câu trả lời của trợ lý khách hàng OrbitTech Store.
  - Mô tả rõ ràng tiêu chuẩn đạt được ở từng mức điểm (1, 2, 3, 4, 5).
  - Có phương án kiểm soát các loại bias: positional bias, verbosity bias, self-preference bias.
- **Điều kiện mất điểm:**
  - Rubric chung chung, copy nguyên mẫu lý thuyết mà không bám sát domain hỗ trợ khách hàng của OrbitTech Store.
  - Thiếu mô tả từng mức điểm hoặc không có phần kiểm soát bias.

### 2.4 Benchmark, 5 Whys, failure analysis (15 điểm)
- **Bằng chứng:**
  - Chạy benchmark trên actual answers thật sinh ra từ `domain_assistant.py`, điền kết quả 5 metrics và phân tích 3 cases thấp nhất vào Exercise 3.2 (`exercises.md`).
  - Phân tích sâu 3 failure cases tiêu biểu trong `reflection.md` bằng kỹ thuật 5 Whys để tìm ra root cause thực sự.
  - Hoàn thiện bảng phân loại lỗi (failure taxonomy) và danh sách hành động cải tiến (improvement log).
- **Điều kiện mất điểm:**
  - Không chạy thực tế trên actual answers mà điền số liệu giả định.
  - Phân tích 5 Whys hời hợt, dừng lại ở triệu chứng bề mặt thay vì root cause.
  - Thiếu đề xuất cải tiến cụ thể hoặc không gắn liền với metrics đo lường.

### 2.5 Code quality, type hints, regression strategy (10 điểm)
- **Bằng chứng:**
  - Code rõ ràng, đặt tên biến có nghĩa, tuân thủ type hints đầy đủ.
  - Trình bày chiến lược regression testing và quality gate CI / CD chi tiết trong `reflection.md`: ngưỡng chặn, bộ test regression, cơ chế giám sát.
- **Điều kiện mất điểm:**
  - Code vi phạm style, không có type hints, import thư viện không có trong `requirements.txt`.
  - Phần regression strategy trong `reflection.md` sơ sài hoặc bỏ trống.

---

## 3. Điểm thưởng (Bonus — Tối đa +10 điểm)

| Tiêu chí Bonus | Điểm tối đa |
|---|---:|
| Exercise 3.4 — So sánh hai evaluation frameworks | +5 |
| Exercise 3.5 — Reranking và phân tích retrieval metrics | +5 |
| **Tổng bonus tối đa (Max total bonus)** | **+10** |

> 💡 **Quy tắc Bonus:** Mỗi bài tập bonus đạt tối đa +5 điểm (Exercise 3.4 +5, Exercise 3.5 +5). **Tổng bonus tối đa của toàn bài lab là +10 điểm** (không phải +10 cho mỗi mục). Đây là điểm sản phẩm lab, không phải điểm giơ tay / pitching. Bonus chỉ được chấm khi phần bài làm bắt buộc đã hoàn thành đầy đủ.

---

## 4. Các trường hợp trừ điểm và vi phạm (Deductions)

| Vi phạm | Hình thức xử lý |
|---|---|
| Đặt sai tên repository nộp bài | Trừ **5 điểm** (-5) |
| Commit file `.env`, API key, token bí mật lên GitHub | Trừ **10 điểm** (-10) |
| Không giải thích được mã nguồn hoặc bài làm khi coach vấn đáp | **Hủy điểm phần tương ứng (0 điểm phần đó)** |
| Đạo văn, sao chép bài của học viên khác (plagiarism) | **0 điểm toàn bài** cho cả hai bên liên quan |

---

## Tài liệu liên quan
- [README.md](README.md) — Tổng quan bài lab và hướng dẫn khởi động
- [SUBMISSION.md](SUBMISSION.md) — Hướng dẫn nộp bài, định dạng tên repo và checklist
- [CHECKPOINTS.md](CHECKPOINTS.md) — Hướng dẫn từng checkpoint và tiêu chuẩn nghiệm thu
- [RULES.md](RULES.md) — Quy định làm bài, sử dụng AI và bảo mật
