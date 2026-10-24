import os
import json
from datetime import datetime
from typing import List, Dict, Any
from core.config import settings

class HistoryService:
    def __init__(self, storage_file: str = "history.json"):
        # Đảm bảo thư mục data tồn tại
        self.data_dir = os.path.join(settings.ROOT_DIR, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.file_path = os.path.join(self.data_dir, storage_file)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def load_history(self) -> List[Dict[str, Any]]:
        """Đọc toàn bộ lịch sử từ file JSON"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return sorted(data, key=lambda x: x.get('timestamp', ''), reverse=True)
        except Exception as e:
            print(f"Error loading history: {e}")
            return []

    def save_record(self, cv_data: Dict, match_score: float, job_title: str):
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

        record = {
            "id": int(datetime.now().timestamp()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "candidate_name": cv_data.get("full_name", "Unknown"),
            "email": cv_data.get("email", []),
            "job_title": job_title,
            "total_score": match_score,
            "education": cv_data.get("education_level", "N/A"),
            "experience_years": cv_data.get("years_experience", 0),
            "summary_skills": skills_list[:5]
        }

        history = self.load_history()
        history.append(record)
        
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")

    def clear_history(self):
        """Xóa toàn bộ lịch sử"""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
