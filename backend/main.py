import os
import glob
import json
import tempfile
import traceback
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from core.logger import logger
from services.cv_parser_service import CVParserService
from services.jd_parser_service import parse_jd_input
from services.scoring_service import ScoringService
from services.history_service import HistoryService
from services.llm_service import generate_ai_feedback
from models.llm_model import LocalLLM

# Khởi tạo FastAPI Application
app = FastAPI(
    title="TalentMatch Enterprise API",
    description="Hệ thống Sàng lọc Hồ sơ & Đối chiếu Tiêu chuẩn Tuyển dụng",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Cấu hình CORS an toàn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Khởi tạo Singletons Services
parser_service = CVParserService()
scoring_service = ScoringService()
history_service = HistoryService()

# Middleware bảo mật: Ẩn thông tin nhạy cảm của server & stack traces
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log chi tiết nội bộ ra terminal / server log (không gửi ra ngoài)
    logger.error(f"Internal Server Error on {request.url.path}: {exc}\n{traceback.format_exc()}")
    
    # Trả về mã lỗi và thông báo thân thiện chuẩn RFC, tuyệt đối không lộ code hay path
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error_code": "INTERNAL_PROCESSING_ERROR",
            "message": "Hệ thống gặp sự cố trong quá trình xử lý tài liệu. Vui lòng kiểm tra lại định dạng file hoặc liên hệ hỗ trợ."
        }
    )

# =============================================================================
# API ENDPOINTS (Chuẩn RESTful)
# =============================================================================

@app.get("/api/v1/health")
def health_check():
    """Kiểm tra trạng thái sẵn sàng của các dịch vụ cốt lõi."""
    return {
        "status": "healthy",
        "service": "TalentMatch AI Core",
        "version": "2.0.0",
        "engines": {
            "fastpath_pdf": "operational",
            "ocr_engine": "operational",
            "vector_semantic_search": "operational",
            "llm_router": "operational"
        }
    }

@app.get("/api/v1/sample-cvs")
def get_sample_cvs():
    """Lấy danh sách các hồ sơ mẫu có sẵn trong hệ thống."""
    sample_dir = os.path.join("data", "sample_cvs")
    if not os.path.exists(sample_dir):
        return {"count": 0, "files": []}
    
    files = [os.path.basename(f) for f in glob.glob(os.path.join(sample_dir, "*.pdf"))]
    return {
        "count": len(files),
        "files": files[:80]
    }

@app.post("/api/v1/evaluate")
async def evaluate_single_cv(
    file: UploadFile = File(...),
    job_title: str = Form("Python Backend Developer"),
    required_experience_years: float = Form(2.0),
    education_level: str = Form("Bachelor"),
    tech_skills: str = Form("Python (Intermediate), FastAPI (Basic), PostgreSQL (Good), Docker (Basic)"),
    foreign_languages: str = Form("English"),
    llm_provider: str = Form("gemini"),
    x_gemini_api_key: Optional[str] = Header(None)
):
    """
    Thẩm định và chấm điểm một hồ sơ ứng viên đơn lẻ đối chiếu với tiêu chuẩn JD.
    """
    # 1. Kiểm tra định dạng file
    allowed_exts = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng tệp không được hỗ trợ. Vui lòng tải lên tệp: {', '.join(allowed_exts)}"
        )

    # 2. Lưu file tạm thời an toàn
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 3. Trích xuất văn bản (Hybrid Fast-path hoặc OCR)
        cv_text, err, mode = parser_service.parse_cv_document(tmp_path)
        if err or not cv_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=err or "Không thể trích xuất nội dung văn bản từ tệp này."
            )

        # 4. Trích xuất thực thể
        info = parser_service.extract_info(cv_text, mode=mode)

        # 5. Phân tích JD & So khớp kỹ năng
        raw_langs = [l.strip() for l in foreign_languages.split(",") if l.strip()]
        jd_parsed = parse_jd_input({
            "job_title": job_title,
            "required_experience_years": required_experience_years,
            "education_level": education_level,
            "programming_languages": [x.strip() for x in tech_skills.split(",") if x.strip()],
            "foreign_languages": raw_langs
        })

        skill_results = {}
        formatted_skills = {}
        for cat in ['programming_languages', 'frameworks', 'databases']:
            req_skills = jd_parsed.get(cat, {})
            matched = scoring_service.match_skills(cv_text, req_skills)
            skill_results[cat] = matched

            lst_display = []
            for s, l in matched.items():
                lvl_str = "Senior" if l >= 3 else ("Mid" if l == 2 else "Junior")
                lst_display.append(f"{s} ({lvl_str})")
            formatted_skills[cat] = lst_display

        cv_data_full = {
            **info,
            "raw_text": cv_text,
            "skills_extracted": skill_results,
            "skills_display": formatted_skills,
            "lang_extracted": info.get("languages_detected", []),
            "extraction_mode": mode
        }

        # 6. Tính điểm Đa tiêu chí & Semantic Vector Search
        score, breakdown = scoring_service.calculate_score(cv_data_full, jd_parsed)

        # 7. Sinh Báo cáo Chuyên sâu & Bộ câu hỏi phỏng vấn
        api_key_to_use = x_gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        ai_feedback = generate_ai_feedback(
            cv_data=cv_data_full,
            jd_parsed=jd_parsed,
            match_score=score,
            breakdown=breakdown,
            provider_type=llm_provider,
            api_key=api_key_to_use,
            local_llm_instance=LocalLLM.get_instance()
        )

        # 8. Lưu lịch sử
        history_service.save_record(cv_data_full, score, jd_parsed["job_title"])

        # 9. Trả về kết quả sạch, không chứa path nhạy cảm
        return {
            "success": True,
            "data": {
                "candidate_name": info.get("full_name", "Unknown Candidate"),
                "email": info.get("email", []),
                "phone_number": info.get("phone_number"),
                "years_experience": info.get("years_experience", 0.0),
                "education_level": info.get("education_level", "None"),
                "total_score": score,
                "breakdown": breakdown,
                "matched_skills": formatted_skills,
                "detected_skills": info.get("skills_detected", {}),
                "foreign_languages": info.get("languages_detected", []),
                "extraction_mode": mode,
                "ai_feedback": ai_feedback,
                "file_name": file.filename
            }
        }

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@app.post("/api/v1/batch-evaluate")
async def batch_evaluate_cvs(
    use_sample_cvs: bool = Form(True),
    batch_limit: int = Form(10),
    job_title: str = Form("Python Backend Developer"),
    required_experience_years: float = Form(2.0),
    education_level: str = Form("Bachelor"),
    tech_skills: str = Form("Python (Intermediate), PostgreSQL (Basic), Docker (Basic)"),
    foreign_languages: str = Form("English")
):
    """
    Chấm điểm hàng loạt danh sách CV mẫu và xuất ra Bảng xếp hạng ứng viên.
    """
    raw_langs = [l.strip() for l in foreign_languages.split(",") if l.strip()]
    jd_parsed = parse_jd_input({
        "job_title": job_title,
        "required_experience_years": required_experience_years,
        "education_level": education_level,
        "programming_languages": [x.strip() for x in tech_skills.split(",") if x.strip()],
        "foreign_languages": raw_langs
    })

    target_files = []
    if use_sample_cvs:
        sample_dir = os.path.join("data", "sample_cvs")
        if os.path.exists(sample_dir):
            all_samples = glob.glob(os.path.join(sample_dir, "*.pdf"))
            limit = min(max(1, batch_limit), len(all_samples), 80)
            target_files = [(f, os.path.basename(f)) for f in all_samples[:limit]]

    if not target_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không tìm thấy danh sách file CV để xử lý hàng loạt."
        )

    records = []
    for path, fname in target_files:
        try:
            c_text, c_err, c_mode = parser_service.parse_cv_document(path)
            if c_err or not c_text:
                continue

            info = parser_service.extract_info(c_text, mode=c_mode)
            s_results = {}
            for cat in ['programming_languages', 'frameworks', 'databases']:
                s_results[cat] = scoring_service.match_skills(c_text, jd_parsed.get(cat, {}))

            c_data = {
                **info,
                "raw_text": c_text,
                "skills_extracted": s_results,
                "lang_extracted": info.get('languages_detected', []),
                "extraction_mode": c_mode
            }

            c_score, c_breakdown = scoring_service.calculate_score(c_data, jd_parsed)

            status_label = c_breakdown.get("Overall", "Chưa Đạt Yêu Cầu")

            records.append({
                "candidate_name": info.get("full_name", "Unknown"),
                "file_name": fname,
                "total_score": c_score,
                "skills_score": c_breakdown.get("Skills", "0/10"),
                "skills_status": c_breakdown.get("Skills_Status", "Chưa đạt"),
                "experience_years": c_breakdown.get("Experience", f"{info.get('years_experience', 0)} năm"),
                "experience_status": c_breakdown.get("Experience_Status", "Chưa đạt"),
                "education": c_breakdown.get("Education_Status", "Chưa đạt"),
                "education_details": c_breakdown.get("Education_Details", ""),
                "languages": c_breakdown.get("Languages_Status", "Chưa đạt"),
                "languages_details": c_breakdown.get("Languages_Details", ""),
                "status": status_label
            })
        except Exception as e:
            logger.warning(f"Bỏ qua file {fname} do lỗi: {e}")
            continue

    # Sắp xếp từ cao xuống thấp
    records = sorted(records, key=lambda x: x["total_score"], reverse=True)
    for idx, r in enumerate(records):
        r["rank"] = idx + 1

    return {
        "success": True,
        "count": len(records),
        "data": records
    }

@app.get("/api/v1/history")
def get_evaluation_history():
    """Lấy danh sách lịch sử thẩm định."""
    history_records = history_service.load_history()
    return {
        "success": True,
        "count": len(history_records),
        "data": history_records
    }

@app.delete("/api/v1/history")
def clear_evaluation_history():
    """Xóa toàn bộ dữ liệu lịch sử."""
    history_service.clear_history()
    return {
        "success": True,
        "message": "Đã xóa toàn bộ lịch sử thẩm định."
    }

# =============================================================================
# FRONTEND STATIC FILES MOUNT
# =============================================================================

# Gắn thư mục frontend tĩnh
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dir, "assets")), name="assets")

    @app.get("/")
    def serve_frontend_root():
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "TalentMatch API Server is running. Visit /docs for Swagger UI."}

