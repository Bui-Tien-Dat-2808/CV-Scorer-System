# services/llm_service.py
from typing import Dict, Any, Optional
from core.logger import logger
from models.llm_model import GeminiProvider, LocalLLM, LLMProviderError

SYSTEM_PROMPT = """Bạn là một Chuyên gia Tuyển dụng Kỹ thuật Cấp cao (Lead Technical Recruiter) và Kiến trúc sư Hệ thống (Principal Engineer).
Nhiệm vụ của bạn là phân tích sâu hồ sơ ứng viên (CV) đối chiếu với bản mô tả công việc (JD), đưa ra nhận xét chuyên môn sắc sảo, công tâm và xây dựng bộ câu hỏi phỏng vấn kỹ thuật cá nhân hóa cho ứng viên đó."""

# Thông báo thân thiện gửi về UI: không chứa exception text hay chi tiết kỹ thuật thô.
CLOUD_UNAVAILABLE_NOTICE = """### ⚠️ Báo cáo thẩm định AI tạm hoãn

Hệ thống không sinh được nhận xét chuyên sâu: Google Gemini không khả dụng và động cơ Local LLM chưa được nạp sẵn.

Điểm số và các tiêu chí đối chiếu ở trên vẫn hợp lệ. **Cách khắc phục:** kiểm tra lại `GEMINI_API_KEY` (ô cấu hình hoặc file `.env`), hoặc nạp mô hình On-Premise Local LLM rồi chọn lại động cơ."""

LOCAL_UNAVAILABLE_NOTICE = """### ⚠️ Báo cáo thẩm định AI tạm hoãn

Không thể nạp hoặc chạy mô hình Local LLM (thiếu thư viện `llama-cpp-python` hoặc trọng số GGUF).

Điểm số và các tiêu chí đối chiếu ở trên vẫn hợp lệ. **Cách khắc phục:** cài `llama-cpp-python` và cho phép tải trọng số vào `models_cache/`, hoặc chuyển sang động cơ Google Gemini."""

def build_evaluation_prompt(cv_data: Dict[str, Any], jd_parsed: Dict[str, Any], match_score: float, breakdown: Dict[str, str]) -> str:
    """Xây dựng Prompt chi tiết theo kỹ thuật Chain-of-Thought & Role Prompting."""
    
    # Chuẩn bị danh sách kỹ năng
    skills_text = "Không có thông tin kỹ năng cụ thể"
    if cv_data.get('skills_display'):
        lines = []
        for cat, items in cv_data['skills_display'].items():
            if items:
                lines.append(f"- {cat}: {', '.join(items)}")
        if lines:
            skills_text = "\n".join(lines)
    elif cv_data.get('skills_detected'):
        lines = []
        for cat, items in cv_data['skills_detected'].items():
            if items:
                lines.append(f"- {cat}: {', '.join(items)}")
        if lines:
            skills_text = "\n".join(lines)

    # Trích xuất trích đoạn dự án / kinh nghiệm thực tế từ CV
    raw_text = cv_data.get('raw_text', '')
    text_snippets = ""
    if raw_text:
        lines = [line.strip() for line in raw_text.split('\n') if len(line.strip().split()) >= 6]
        text_snippets = "\n".join(lines[:15])  # Lấy 15 đoạn tiêu biểu

    # Kỹ năng JD yêu cầu
    req_skills = []
    for cat in ['programming_languages', 'frameworks', 'databases']:
        for s, l in jd_parsed.get(cat, {}).items():
            req_skills.append(f"{s} (Level {l})")
    req_skills_str = ", ".join(req_skills) if req_skills else "Chưa chỉ định rõ"

    prompt = f"""Hãy lập Báo cáo Phân tích Chuyên sâu (Technical Evaluation Report) bằng Tiếng Việt theo cấu trúc chuẩn Markdown cho hồ sơ sau:

### 1. THÔNG TIN VỊ TRÍ TUYỂN DỤNG (JD)
- Vị trí: {jd_parsed.get('job_title', 'Chưa rõ')}
- Số năm kinh nghiệm yêu cầu: {jd_parsed.get('required_experience_years', 0)} năm
- Bằng cấp yêu cầu: {jd_parsed.get('education_level', 'Bachelor')}
- Kỹ năng & Công nghệ cốt lõi: {req_skills_str}
- Ngoại ngữ yêu cầu: {', '.join(jd_parsed.get('foreign_languages', [])) or 'Không bắt buộc'}

### 2. THÔNG TIN ỨNG VIÊN (CV)
- Họ và tên: {cv_data.get('full_name', 'Ứng viên')}
- Kinh nghiệm thực tế: {cv_data.get('years_experience', 0)} năm
- Bằng cấp ghi nhận: {cv_data.get('education_level', 'Chưa rõ')}
- Kỹ năng bóc tách từ CV:
{skills_text}
- Ngoại ngữ ghi nhận: {', '.join(cv_data.get('languages_detected', [])) or 'Không phát hiện rõ'}
- Trích đoạn kinh nghiệm / dự án tiêu biểu từ CV:
{text_snippets[:800]}

### 3. KẾT QUẢ ĐỐI CHIẾU TIÊU CHÍ (AI SCORING ENGINE)
- **Điểm Kỹ năng Chuyên môn (Thang điểm 10):** {breakdown.get('Skills', 'N/A')} (Nhận xét: {breakdown.get('Skills_Status', 'Chưa đạt')})
- **Kinh nghiệm làm việc:** {breakdown.get('Experience', 'N/A')} (Nhận xét: {breakdown.get('Experience_Status', 'Chưa đạt')})
- **Trình độ học vấn:** {breakdown.get('Education_Status', 'Chưa đạt')} ({breakdown.get('Education_Details', '')})
- **Ngoại ngữ:** {breakdown.get('Languages_Status', 'Chưa đạt')} ({breakdown.get('Languages_Details', '')})
- **Điểm tổng hợp đa tiêu chí (Thang điểm 10):** {breakdown.get('Total_Score', f'{match_score:.1f}')}/10 — {breakdown.get('Weights', 'Kỹ năng 60% · Kinh nghiệm 20% · Học vấn 10% · Ngoại ngữ 10%')}
- **Xếp loại tổng hợp:** {breakdown.get('Overall', 'Chưa Đạt Yêu Cầu')}

---
### YÊU CẦU ĐẦU RA (XUẤT RA THEO ĐÚNG CẤU TRÚC MARKDOWN SAU):

#### 🎯 1. Đánh giá Tổng quan (Executive Summary)
(Tóm tắt súc tích trong 2-3 câu về mức độ tương thích giữa ứng viên và vị trí.)

#### 🌟 2. Điểm mạnh Nổi bật (Key Strengths)
(Nêu từ 2 - 3 điểm mạnh nhất của ứng viên, đối chiếu cụ thể với những yêu cầu trọng yếu trong JD.)

#### ⚠️ 3. Lỗ hổng Kỹ năng & Rủi ro (Gaps & Risks)
(Chỉ rõ các công nghệ hoặc yêu cầu mà ứng viên còn thiếu, chưa đạt mức yêu cầu hoặc chưa thể hiện rõ trong CV.)

#### ❓ 4. Bộ Câu hỏi Phỏng vấn Kỹ thuật Chuyên sâu (Tailored Technical Interview Kit)
(Thiết kế chính xác 3 câu hỏi phỏng vấn kỹ thuật nhắm thẳng vào các công nghệ cốt lõi hoặc lỗ hổng được phát hiện. Mỗi câu hỏi PHẢI kèm theo tiêu chí đánh giá cho người phỏng vấn theo định dạng:
- **Câu hỏi [X]:** [Nội dung câu hỏi kỹ thuật thực tế / tình huống xử lý lỗi / kiến trúc hệ thống]
  - *Mục đích kiểm tra:* [Kiểm tra kiến thức gì]
  - *Kỳ vọng câu trả lời (Good Answer):* [Ứng viên cần giải thích được những điểm kỹ thuật nào]
)

#### 📋 5. Đề xuất Quyết định Tuyển dụng (Hiring Recommendation)
(Chọn rõ 1 trong 3 trạng thái: [TIẾN HÀNH PHỎNG VẤN NGAY] / [CÂN NHẮC XEM XÉT THÊM] / [TỪ CHỐI HỒ SƠ] kèm theo 1 câu tóm lược lý do cốt lõi.)
"""
    return prompt

def generate_ai_feedback(
    cv_data: Dict[str, Any],
    jd_parsed: Dict[str, Any],
    match_score: float,
    breakdown: Dict[str, str],
    provider_type: str = "gemini",
    api_key: str = "",
    local_llm_instance: Optional[LocalLLM] = None
) -> str:
    """Điều phối sinh nhận xét chuyên sâu bằng Gemini hoặc Local LLM."""
    prompt = build_evaluation_prompt(cv_data, jd_parsed, match_score, breakdown)

    if provider_type == "gemini":
        try:
            logger.info("Đang sinh báo cáo thẩm định qua Google Gemini API...")
            provider = GeminiProvider(api_key=api_key)
            return provider.generate_analysis(prompt, system_instruction=SYSTEM_PROMPT)
        except LLMProviderError as e:
            # Gemini thất bại thật sự (thiếu key / API lỗi) -> fallback sang Local LLM đã nạp sẵn.
            logger.warning(f"Gemini không khả dụng: {e}. Thử fallback sang Local LLM...")
            local = local_llm_instance or LocalLLM.get_instance()
            if local.is_loaded():
                try:
                    return local.generate_response(prompt, system_instruction=SYSTEM_PROMPT)
                except LLMProviderError as local_error:
                    logger.error(f"Local LLM fallback thất bại: {local_error}")
            return CLOUD_UNAVAILABLE_NOTICE

    elif provider_type == "local":
        local = local_llm_instance or LocalLLM.get_instance()
        try:
            logger.info("Đang sinh báo cáo thẩm định qua Local LLM (Qwen2.5-7B)...")
            return local.generate_response(prompt, system_instruction=SYSTEM_PROMPT)
        except LLMProviderError as e:
            logger.error(f"Local LLM không khả dụng: {e}")
            return LOCAL_UNAVAILABLE_NOTICE

    return "Động cơ LLM không hợp lệ."
