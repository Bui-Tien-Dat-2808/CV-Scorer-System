import os
import re
import cv2
import numpy as np
import fitz  # PyMuPDF
from typing import Tuple, Optional, Dict, Any, List

# --- Import Models & Utils ---
from models.ocr_model import OCRModel
from models.embedding_model import EmbeddingModel
from utils.image_processing import preprocess_column, split_cv_columns
from utils.text_cleaner import clean_ocr_errors_smart, clean_text
from utils.file_loader import load_file_as_images
from core.constants import (
    EDUCATION_LEVELS, LANGUAGES, FRAMEWORKS, DATABASES,
    AI_ML_SKILLS, DEVOPS_TOOLS, SKILL_ALIASES, NAME_IGNORE_KEYWORDS
)
from core.logger import logger
from schemas.models import CandidateProfile

class CVParserService:
    def __init__(self):
        self._ocr = None
        self._embedder = None

    @property
    def ocr(self):
        """Lazy loading OCR Model chỉ khi gặp file scan/ảnh cần OCR."""
        if self._ocr is None:
            self._ocr = OCRModel.get_instance()
        return self._ocr

    @property
    def embedder(self):
        """Lazy loading embedding model để không làm chậm lúc khởi động."""
        if self._embedder is None:
            self._embedder = EmbeddingModel.get_instance()
        return self._embedder

    # =========================================================================
    # 1. HYBRID EXTRACTION ENGINE (Fast-path Digital PDF + Fallback OCR)
    # =========================================================================

    def parse_cv_document(self, file_path: str) -> Tuple[str, Optional[str], str]:
        """
        Trích xuất văn bản từ CV theo cơ chế Hybrid:
        - Nếu là Digital PDF (có sẵn text layer): Trích xuất trong 0.05s với PyMuPDF.
        - Nếu là Scanned PDF hoặc Ảnh: Tự động kích hoạt PaddleOCR.
        - Nếu là DOCX: Đọc trực tiếp qua python-docx.

        Returns:
            (clean_text, error_message, extraction_mode)
        """
        if not os.path.exists(file_path):
            return "", "File không tồn tại.", "unknown"

        file_ext = os.path.splitext(file_path)[1].lower()

        # ---------------------------------------------------------------------
        # Case 1: FILE DOCX
        # ---------------------------------------------------------------------
        if file_ext == ".docx":
            try:
                import docx
                doc = docx.Document(file_path)
                full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                if full_text.strip():
                    logger.info("⚡ Fast-path: Đã trích xuất văn bản từ DOCX.")
                    return clean_text(full_text), None, "digital_docx"
            except Exception as e:
                logger.warning(f"Lỗi đọc file docx: {e}. Thử fallback.")

        # ---------------------------------------------------------------------
        # Case 2: FILE PDF (Kiểm tra xem có text số không)
        # ---------------------------------------------------------------------
        if file_ext == ".pdf":
            try:
                doc = fitz.open(file_path)
                digital_text = ""
                for page in doc:
                    digital_text += page.get_text("text") + "\n"
                doc.close()

                # Đếm số từ trong text trích xuất được
                word_count = len(digital_text.strip().split())

                # Nếu file có trên 40 từ -> Đây là Digital PDF!
                if word_count >= 40:
                    logger.info(f"⚡ Fast-path: Phát hiện Digital PDF ({word_count} từ). Bỏ qua OCR hoàn toàn!")
                    clean_raw = clean_ocr_errors_smart(clean_text(digital_text))
                    return clean_raw, None, "digital_pdf"

                logger.info(f"🔍 PDF dạng scan/ảnh (chỉ có {word_count} từ text số). Chuyển sang PaddleOCR...")
            except Exception as e:
                logger.warning(f"Lỗi khi thử đọc digital PDF: {e}. Chuyển sang OCR...")

        # ---------------------------------------------------------------------
        # Case 3: FALLBACK SANG OCR (Cho PDF scan và file Ảnh thông thường)
        # ---------------------------------------------------------------------
        images = load_file_as_images(file_path)
        if not images:
            return "", "Không thể load file hoặc file rỗng.", "error"

        full_text = ""
        for i, img in enumerate(images):
            logger.info(f"OCR đang xử lý trang {i + 1}/{len(images)}...")
            try:
                page_text = self._process_single_page_numpy(img)
                if page_text:
                    full_text += page_text + "\n"
            except Exception as e:
                logger.error(f"Lỗi OCR trang {i + 1}: {e}")
                continue

        if not full_text.strip():
            return "", "Không trích xuất được nội dung CV (OCR không nhận diện được chữ).", "failed"

        clean_raw = clean_ocr_errors_smart(clean_text(full_text))
        return clean_raw, None, "ocr_fallback"

    def _ocr_image_data(self, image_data):
        """Hàm gọi PaddleOCR trên mảng ảnh numpy."""
        try:
            result = self.ocr.ocr(image_data)
        except Exception as e:
            logger.error(f"OCR engine failed: {e}")
            return ""

        if not result or not result[0]:
            return ""

        lines = []
        for line in result[0]:
            try:
                text = line[1][0]
                score = line[1][1]
                if score > 0.45:
                    lines.append(text)
            except Exception:
                continue

        return "\n".join(lines)

    def _process_single_page_numpy(self, image_numpy):
        """Xử lý chia cột (Layout Analysis) thông minh."""
        if len(image_numpy.shape) == 3:
            gray = cv2.cvtColor(image_numpy, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_numpy

        height, width = gray.shape
        left_check_area = gray[:, :int(width * 0.40)]
        right_check_area = gray[:, int(width * 0.60):]

        mean_left = np.mean(left_check_area)
        mean_right = np.mean(right_check_area)

        DIFFERENCE_THRESHOLD = 75
        is_dark_left = (abs(mean_left - mean_right) > DIFFERENCE_THRESHOLD) and (mean_left < mean_right)
        is_dark_right = (abs(mean_left - mean_right) > DIFFERENCE_THRESHOLD) and (mean_right < mean_left)

        if is_dark_left:
            split = int(width * 0.42)
            left_txt = self._ocr_image_data(preprocess_column(gray[:, :split], True))
            right_txt = self._ocr_image_data(preprocess_column(gray[:, split:], False))
            return left_txt + "\n\n" + right_txt
        elif is_dark_right:
            split = int(width * 0.58)
            left_txt = self._ocr_image_data(preprocess_column(gray[:, :split], False))
            right_txt = self._ocr_image_data(preprocess_column(gray[:, split:], True))
            return left_txt + "\n\n" + right_txt
        else:
            processed = preprocess_column(gray, np.mean(gray) < 100)
            return self._ocr_image_data(processed)

    # =========================================================================
    # 2. INFORMATION EXTRACTION (Entity & Feature Engineering)
    # =========================================================================

    def extract_info(self, text: str, mode: str = "hybrid") -> Dict[str, Any]:
        """Trích xuất toàn diện các thực thể từ văn bản CV."""
        return {
            "full_name": self._find_full_name(text),
            "email": self._extract_emails(text),
            "phone_number": self._find_phone_number(text),
            "years_experience": self._find_years_experience(text),
            "education_level": self._extract_education_level(text),
            "skills_detected": self._extract_all_skills_passive(text),
            "languages_detected": self._extract_foreign_languages(text),
            "extraction_mode": mode
        }

    def _find_full_name(self, text: str) -> str:
        """Nhận diện họ và tên ứng viên từ các dòng đầu CV."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for line in lines[:15]:
            # Bỏ qua dòng có email hoặc số điện thoại
            if '@' in line or re.search(r'\d', line):
                continue

            words = line.split()
            if not (2 <= len(words) <= 5):
                continue

            # Bỏ qua nếu dòng chứa các từ khóa tiêu đề chung
            line_lower = line.lower()
            if any(ignore in line_lower for ignore in NAME_IGNORE_KEYWORDS):
                continue

            # Kiểm tra xem có viết hoa chữ cái đầu hoặc viết hoa toàn bộ không
            if line.isupper() or line.istitle() or any(w[0].isupper() for w in words if w):
                # Làm sạch ký tự lạ
                clean_name = re.sub(r'[^a-zA-ZÀ-ỹ\s]', '', line).strip()
                if clean_name:
                    return clean_name.title()

        return "Unknown Candidate"

    def _extract_emails(self, text: str) -> List[str]:
        if not text:
            return []
        pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.IGNORECASE)
        return list(set(pattern.findall(text)))

    def _find_phone_number(self, text: str) -> Optional[str]:
        patterns = [
            r'\b((\+84|0)[3|5|7|8|9]([\s\.-]?\d{2,4}){2,3})\b',
            r'\b(\(?[1-9]\d{2}\)?[\s\.-]?\d{3}[\s\.-]?\d{4})\b',
            r'\b([1-9]\d{2}[\s\.-]\d{4})\b'
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                phone_str = match.group(0)
                if phone_str.startswith('+'):
                    return '+' + re.sub(r'\D', '', phone_str[1:])
                return re.sub(r'\D', '', phone_str)
        return None

    def _find_years_experience(self, text: str) -> float:
        """Ước tính số năm kinh nghiệm dựa trên cả từ khóa lẫn khoảng thời gian làm việc."""
        found_years = []

        # 1. Tìm cụm từ rõ ràng: ví dụ "3 years experience", "2 năm kinh nghiệm"
        pattern = re.compile(r'(\d{1,2})\+?\s*(year|năm|nam|yr|tháng|month)s?\b', re.IGNORECASE)
        for match in pattern.finditer(text):
            num = float(match.group(1))
            unit = match.group(2).lower()
            if 'tháng' in unit or 'month' in unit:
                found_years.append(round(num / 12.0, 1))
            elif num <= 30:  # Tránh bắt nhầm tuổi (vd: 22 years old)
                found_years.append(num)

        # 2. Phân tích khoảng năm làm việc (vd: 2020 - 2024 hoặc 2021 - Present)
        year_ranges = re.findall(r'\b(201\d|202\d)\s*[-–—toàđến/]+\s*(201\d|202\d|present|nay|hiện tại)\b', text, re.IGNORECASE)
        total_range_years = 0
        current_year = 2026

        for start_str, end_str in year_ranges:
            try:
                start = int(start_str)
                if any(p in end_str.lower() for p in ['present', 'nay', 'hiện tại']):
                    end = current_year
                else:
                    end = int(end_str)
                diff = end - start
                if 0 < diff <= 15:
                    total_range_years = max(total_range_years, diff)
            except Exception:
                continue

        if total_range_years > 0:
            found_years.append(float(total_range_years))

        return max(found_years) if found_years else 0.0

    def _extract_education_level(self, text: str) -> str:
        """Nhận diện bằng cấp (ưu tiên keyword tiếng Anh/Việt trước, semantic fallback sau)."""
        text_lower = text.lower()

        # Từ điển phân cấp bằng cấp trực tiếp
        edu_keywords = {
            'Phd': ['phd', 'doctorate', 'tiến sĩ'],
            'Master': ['master', 'thạc sĩ', 'mba', 'm.sc', 'm.tech'],
            'Bachelor': ['bachelor', 'cử nhân', 'kỹ sư', 'engineer', 'b.sc', 'b.tech', 'đại học', 'university'],
            'Associate': ['associate', 'cao đẳng', 'college', 'vocational']
        }

        for level, keywords in edu_keywords.items():
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                    return level

        # Fallback dùng Embedding nếu văn bản phức tạp
        try:
            lines = [s.strip() for s in text.split('\n') if 4 < len(s.strip()) < 80]
            if lines and self._embedder is not None:
                from sentence_transformers import util
                emb_edu = self.embedder.encode(EDUCATION_LEVELS, convert_to_tensor=True)
                emb_lines = self.embedder.encode(lines[:20], convert_to_tensor=True)
                cos_scores = util.cos_sim(emb_lines, emb_edu)
                max_score = cos_scores.max()
                if max_score > 0.65:
                    idx = (cos_scores == max_score).nonzero(as_tuple=True)[1][0]
                    return EDUCATION_LEVELS[idx.item()].title()
        except Exception as e:
            logger.warning(f"Embedding education fallback failed: {e}")

        return "None"

    def _extract_foreign_languages(self, text: str) -> List[str]:
        """Phát hiện ngoại ngữ kèm chứng chỉ (IELTS, TOEIC, JLPT, HSK)."""
        text_clean = text.replace('\n', '  ')
        results = []
        target_languages = ['English', 'Vietnamese', 'Japanese', 'Korean', 'Chinese', 'French', 'German']

        for lang in target_languages:
            lang_esc = re.escape(lang)
            # Pattern tìm ngôn ngữ kèm chứng chỉ hoặc level gần kề
            pattern = r'\b' + lang_esc + r'.{0,35}?\b(IELTS\s*[\d\.]+|TOEIC\s*\d+|N[1-5]|HSK\s*\d|Native|Fluent|Proficient|Intermediate|Basic|Advanced)\b'
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                results.append(f"{lang} ({match.group(1).title()})")
            elif re.search(r'\b' + lang_esc + r'\b', text_clean, re.IGNORECASE):
                # Bắt tên ngôn ngữ nếu xuất hiện trong ngữ cảnh học tập / kỹ năng
                if any(w in text_clean.lower() for w in ['language', 'ngôn ngữ', 'ngoại ngữ', 'communication']):
                    results.append(lang)

        return list(set(results))

    def _extract_all_skills_passive(self, text: str) -> Dict[str, List[str]]:
        """Quét toàn bộ kỹ năng kỹ thuật có trong CV kèm tra cứu từ đồng nghĩa (Aliases)."""
        found_skills = {}
        text_lower = text.lower()

        def scan_list(category: str, items: List[str]):
            found = set()
            for item in items:
                item_esc = re.escape(item.lower())
                pattern = r'(?:^|\s|[,\.\-\/\(\)])' + item_esc + r'(?:$|\s|[,\.\-\/\(\)])'
                if re.search(pattern, text_lower):
                    # Chuẩn hóa nếu là alias (vd: k8s -> kubernetes)
                    normalized_name = SKILL_ALIASES.get(item.lower(), item).title()
                    found.add(normalized_name)
            if found:
                found_skills[category] = sorted(list(found))

        scan_list('Languages', LANGUAGES)
        scan_list('Frameworks', FRAMEWORKS)
        scan_list('Databases', DATABASES)
        scan_list('AI & Data', AI_ML_SKILLS)
        scan_list('DevOps & Cloud', DEVOPS_TOOLS)

        return found_skills
