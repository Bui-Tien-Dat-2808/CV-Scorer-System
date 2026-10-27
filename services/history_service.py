import os
import json
import uuid
import tempfile
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.config import settings
from core.logger import logger

class HistoryService:
    def __init__(self, storage_file: str = "history.json"):
        # Đảm bảo thư mục data tồn tại
        self.data_dir = os.path.join(settings.ROOT_DIR, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.file_path = os.path.join(self.data_dir, storage_file)
        # Một quy trình lưu file duy nhất (FastAPI) nên khoá tiến trình là đủ;
        # ghi nhiều tiến trình cùng lúc vẫn cần cơ sở dữ liệu hoặc khoá file.
        self._lock = threading.Lock()
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.file_path):
            self._write_history([])

    def _write_history(self, history: List[Dict[str, Any]]):
        """Ghi file tạm rồi os.replace: tiến trình khác không bao giờ đọc phải file đang viết dở."""
        fd, tmp_path = tempfile.mkstemp(prefix=".history-", suffix=".tmp", dir=self.data_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.file_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    def load_history(self) -> List[Dict[str, Any]]:
        """Đọc toàn bộ lịch sử từ file JSON"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return sorted(data, key=lambda x: x.get('timestamp', ''), reverse=True)
        except Exception as e:
            logger.error(f"Lỗi đọc lịch sử đánh giá: {e}")
            return []

    def save_record(self, cv_data: Dict, match_score: float, job_title: str,
                    breakdown: Optional[Dict[str, str]] = None):
        """Lưu một bản ghi đánh giá mới"""
        # Trích xuất danh sách tên kỹ năng thực tế thay vì tên categories
        skills_list = []
        if "skills_display" in cv_data and cv_data["skills_display"]:
            for cat_skills in cv_data["skills_display"].values():
                if isinstance(cat_skills, list):
                    skills_list.extend(cat_skills)
        elif "skills_extracted" in cv_data and cv_data["skills_extracted"]:
            for cat_skills in cv_data["skills_extracted"].values():
                if isinstance(cat_skills, dict):
                    skills_list.extend(cat_skills.keys())

        breakdown = breakdown or {}

        record = {
            "id": uuid.uuid4().hex,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "candidate_name": cv_data.get("full_name", "Unknown"),
            "email": cv_data.get("email", []),
            "job_title": job_title,
            "total_score": match_score,
            "skills_score": breakdown.get("Skills_Score", f"{match_score:.1f}"),
            "overall_status": breakdown.get("Overall", ""),
            "education_level": cv_data.get("education_level", "N/A"),
            "experience_years": cv_data.get("years_experience", 0),
            "summary_skills": skills_list[:5]
        }

        with self._lock:
            history = self.load_history()
            history.append(record)
            try:
                self._write_history(history)
            except Exception as e:
                logger.error(f"Lỗi lưu lịch sử đánh giá: {e}")

    def clear_history(self):
        """Xóa toàn bộ lịch sử"""
        with self._lock:
            self._write_history([])
