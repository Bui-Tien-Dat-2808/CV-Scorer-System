from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class CandidateProfile(BaseModel):
    """Thông tin hồ sơ ứng viên sau khi bóc tách từ CV."""
    full_name: str = Field(default="Unknown Candidate", description="Họ và tên ứng viên")
    email: List[str] = Field(default_factory=list, description="Danh sách email liên hệ")
    phone_number: Optional[str] = Field(default=None, description="Số điện thoại")
    years_experience: float = Field(default=0.0, description="Số năm kinh nghiệm ước tính")
    education_level: str = Field(default="None", description="Trình độ học vấn cao nhất")
    skills_extracted: Dict[str, Dict[str, int]] = Field(
        default_factory=dict,
        description="Kỹ năng kỹ thuật theo danh mục và level số (1: Junior, 2: Mid, 3: Senior)"
    )
    skills_display: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Kỹ năng đã định dạng hiển thị kèm chữ (Junior/Mid/Senior)"
    )
    languages_detected: List[str] = Field(default_factory=list, description="Ngoại ngữ và chứng chỉ kèm theo")
    raw_text: str = Field(default="", description="Nội dung văn bản thô bóc tách từ file")
    extraction_mode: str = Field(
        default="hybrid",
        description="Phương thức trích xuất: 'digital_pdf' (siêu tốc) hoặc 'ocr_fallback' (scan/ảnh)"
    )

class JDRequirements(BaseModel):
    """Yêu cầu công việc (Job Description) đã được chuẩn hóa."""
    job_title: str = Field(default="Software Engineer", description="Vị trí tuyển dụng")
    required_experience_years: float = Field(default=0.0, description="Số năm kinh nghiệm tối thiểu")
    education_level: str = Field(default="Bachelor", description="Bằng cấp tối thiểu")
    programming_languages: Dict[str, int] = Field(default_factory=dict, description="Ngôn ngữ lập trình và level yêu cầu")
    frameworks: Dict[str, int] = Field(default_factory=dict, description="Frameworks và level yêu cầu")
    databases: Dict[str, int] = Field(default_factory=dict, description="Cơ sở dữ liệu và level yêu cầu")
    foreign_languages: List[str] = Field(default_factory=list, description="Yêu cầu ngoại ngữ")
    language_levels: Dict[str, int] = Field(default_factory=dict, description="Trình độ ngoại ngữ tối thiểu theo LANGUAGE_LEVELS")
    raw_description: Optional[str] = Field(default="", description="Mô tả công việc chi tiết nếu có")

class ScoreBreakdown(BaseModel):
    """Chi tiết điểm số thành phần (0 - 100)."""
    skills_score: float = Field(default=0.0, description="Điểm kỹ năng kỹ thuật (Tối đa 40-50)")
    experience_score: float = Field(default=0.0, description="Điểm số năm kinh nghiệm (Tối đa 25-30)")
    semantic_score: float = Field(default=0.0, description="Điểm tương đồng ngữ nghĩa dự án/trách nhiệm (Tối đa 15)")
    education_score: float = Field(default=0.0, description="Điểm học vấn (Tối đa 10)")
    language_score: float = Field(default=0.0, description="Điểm ngoại ngữ (Tối đa 5-10)")
    total_score: float = Field(default=0.0, description="Tổng điểm phù hợp")
    details: Dict[str, str] = Field(default_factory=dict, description="Ghi chú chi tiết cho từng tiêu chí")

class EvaluationResult(BaseModel):
    """Kết quả đánh giá toàn diện một hồ sơ ứng viên."""
    candidate: CandidateProfile
    jd: JDRequirements
    score: float
    breakdown: ScoreBreakdown
    ai_feedback: Optional[str] = None
    timestamp: str = ""

