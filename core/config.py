import os

from dotenv import load_dotenv

# Nạp .env trước khi Settings đọc biến môi trường lúc import module.
load_dotenv()

# Windows DLL Hotfix: PyTorch phải được nạp trước PaddlePaddle để tránh xung đột shm.dll / OpenMP
try:
    import torch
except Exception:
    pass

class Settings:
    # Model Repos
    LLM_REPO_ID = "bartowski/Qwen2.5-7B-Instruct-GGUF"
    LLM_FILENAME = "Qwen2.5-7B-Instruct-Q4_K_M.gguf"
    EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-base"
    TOP_K_CANDIDATES = 5
    SUPPORTED_CV_FORMATS = [".pdf", ".docx"]
    # Thresholds
    SKILL_MATCH_THRESHOLD = 0.85
    EDUCATION_THRESHOLD = 0.65
    USE_OCR_FALLBACK = True        # nếu file không trích được text thì dùng OCR
    OCR_LANG = "en"                # ngôn ngữ cho OCR
    OCR_DPI = 200                  # DPI khi convert pdf->image
    OCR_MAX_PAGES = 50             # giới hạn số trang
    # Paths
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    MODEL_CACHE_DIR = os.path.join(ROOT_DIR, "data", "models_cache")

    # Bảo mật & miền truy cập
    # Origin được phép gọi cross-origin, phân tách bằng dấu phẩy. Rỗng = chỉ phục vụ cùng nguồn.
    CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()]
    # Token bảo vệ thao tác xoá lịch sử. Chưa đặt = xoá công khai (chỉ nên để khi dev).
    ADMIN_TOKEN = os.getenv("APP_ADMIN_TOKEN", "").strip()

settings = Settings()
