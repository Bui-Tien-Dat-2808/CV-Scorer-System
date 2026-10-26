import re
from typing import Dict, Any, Tuple, List

from core.constants import SKILL_LEVEL_MAPPING, EDUCATION_RANKING, SKILL_ALIASES
from core.logger import logger
from utils.text_cleaner import clean_text

# Tỷ trọng từng tiêu chí khi quy ra điểm tổng hợp thang 10.
SCORING_WEIGHTS = {'skills': 0.6, 'experience': 0.2, 'education': 0.1, 'languages': 0.1}

class ScoringService:
    def __init__(self):
        pass

    def get_education_rank(self, edu_text: str) -> int:
        if not edu_text:
            return 0
        for key, rank in EDUCATION_RANKING.items():
            if key.lower() in edu_text.lower():
                return rank
        return 0

    def _detect_level_from_context(self, skill_name: str, cv_text: str, window: int = 70) -> int:
        """
        Quét ngữ cảnh xung quanh vị trí xuất hiện của skill để suy luận Level ứng viên.
        """
        skill_lower = skill_name.lower()
        cv_lower = cv_text.lower()

        # Tìm skill gốc và các biến thể viết tắt (alias)
        target_words = [skill_lower]
        for alias, canonical in SKILL_ALIASES.items():
            if canonical == skill_lower:
                target_words.append(alias)
            elif alias == skill_lower:
                target_words.append(canonical)

        matches = []
        for word in target_words:
            if re.match(r'^[a-zA-Z0-9_]+$', word):
                pattern = r'\b' + re.escape(word) + r'\b'
            else:
                pattern = r'(?:^|\s|[,\.\-\/\(\):;])' + re.escape(word) + r'(?:$|\s|[,\.\-\/\(\):;])'

            for m in re.finditer(pattern, cv_lower):
                matches.append((m.start(), len(word)))

        if not matches:
            return 0

        max_detected_level = 1  # Mặc định level 1 (Junior/Cơ bản) khi tìm thấy tên skill

        for idx, word_len in matches:
            # Giới hạn context trong cùng dòng/mục để tránh bị lem keyword từ dòng khác
            line_start = cv_lower.rfind('\n', 0, idx)
            line_start = 0 if line_start == -1 else line_start + 1

            line_end = cv_lower.find('\n', idx)
            line_end = len(cv_lower) if line_end == -1 else line_end

            start = max(line_start, idx - window)
            end = min(line_end, idx + word_len + window)
            context_snippet = cv_lower[start:end]

            for keyword, level_val in SKILL_LEVEL_MAPPING.items():
                if re.search(r'\b' + re.escape(keyword) + r'\b', context_snippet):
                    if level_val > max_detected_level:
                        max_detected_level = level_val

        return max_detected_level

    def match_skills(self, cv_text: str, jd_req_dict: Dict[str, int]) -> Dict[str, int]:
        """
        So khớp danh sách kỹ năng JD yêu cầu với nội dung CV.
        Hỗ trợ nhận diện cả từ viết tắt/đồng nghĩa (Aliases).
        """
        if not jd_req_dict:
            return {}

        cv_clean = clean_text(cv_text)
        matched_results = {}

        for skill_name in jd_req_dict.keys():
            level = self._detect_level_from_context(skill_name, cv_clean)
            if level > 0:
                matched_results[skill_name] = level

        return matched_results

    def calculate_score(self, cv_data: Dict[str, Any], jd_requirements_parsed: Dict[str, Any]) -> Tuple[float, Dict[str, str]]:
        """
        Quy chuẩn đánh giá và chấm điểm theo yêu cầu điều chỉnh:
        - 1. Kỹ năng chuyên môn: Thang điểm 10 kèm nhận xét Đạt / Chưa đạt (ngưỡng >= 6.0/10).
        - 2. Kinh nghiệm: Ghi rõ kinh nghiệm thực tế, so sánh với JD kèm nhận xét Đạt / Chưa đạt.
        - 3. Trình độ học vấn: Chỉ đánh giá Đạt / Chưa đạt (không chấm điểm số).
        - 4. Ngoại ngữ: Chỉ đánh giá Đạt / Chưa đạt (không chấm điểm số).
        - 5. Loại bỏ hoàn toàn Semantic Fit.
        - Tổng điểm thang 10 = 60% kỹ năng + 20% kinh nghiệm + 10% học vấn + 10% ngoại ngữ.
        """
        breakdown = {}

        # --- 1. Tech skills (Thang điểm 10) ---
        total_skill_points_max = 0
        total_skill_points_candidate = 0
        tech_cats = ['programming_languages', 'frameworks', 'databases']

        for cat in tech_cats:
            req_dict = jd_requirements_parsed.get(cat, {})
            found_dict = cv_data.get('skills_extracted', {}).get(cat, {})

            for skill_name, req_level in req_dict.items():
                total_skill_points_max += req_level
                if skill_name in found_dict:
                    found_level = found_dict[skill_name]
                    if found_level >= req_level:
                        total_skill_points_candidate += req_level
                    else:
                        total_skill_points_candidate += (found_level / req_level) * req_level

        if total_skill_points_max > 0:
            tech_score_10 = (total_skill_points_candidate / total_skill_points_max) * 10.0
        else:
            tech_score_10 = 10.0

        tech_score_10 = round(min(max(tech_score_10, 0.0), 10.0), 1)
        skills_status = "Đạt" if tech_score_10 >= 6.0 else "Chưa đạt"

        breakdown['Skills'] = f"{tech_score_10:.1f}/10"
        breakdown['Skills_Score'] = f"{tech_score_10:.1f}"
        breakdown['Skills_Status'] = skills_status
        breakdown['Skills_Comment'] = f"{tech_score_10:.1f}/10 - {skills_status}"

        # --- 2. Experience Years (So sánh thực tế vs JD, Đạt / Chưa đạt) ---
        req_exp = float(jd_requirements_parsed.get('required_experience_years', 0) or 0)
        cand_exp = float(cv_data.get('years_experience', 0) or 0)

        exp_status = "Đạt" if (cand_exp >= req_exp) else "Chưa đạt"
        exp_ratio = 1.0 if req_exp <= 0 else min(cand_exp / req_exp, 1.0)

        breakdown['Experience'] = f"{cand_exp:g} năm (Yêu cầu: {req_exp:g} năm)"
        breakdown['Experience_Cand'] = f"{cand_exp:g} năm"
        breakdown['Experience_Req'] = f"{req_exp:g} năm"
        breakdown['Experience_Status'] = exp_status
        breakdown['Experience_Details'] = f"{cand_exp:g} năm vs {req_exp:g} năm ({exp_status})"

        # --- 3. Education (Chỉ Đạt / Chưa đạt, không chấm điểm) ---
        req_edu_str = jd_requirements_parsed.get('education_level', 'None')
        found_edu_str = cv_data.get('education_level', 'None')

        req_rank = self.get_education_rank(req_edu_str)
        found_rank = self.get_education_rank(found_edu_str)

        if req_rank == 0:
            edu_status, edu_ratio = "Đạt", 1.0
        elif found_rank >= req_rank:
            edu_status, edu_ratio = "Đạt", 1.0
        else:
            # Có bằng cấp nhưng thấp hơn yêu cầu: cho 50% điểm, chưa đáp ứng thì 0%.
            edu_status = "Chưa đạt"
            edu_ratio = 0.5 if found_rank > 0 else 0.0

        breakdown['Education_Status'] = edu_status
        breakdown['Education_Details'] = f"{found_edu_str} vs {req_edu_str}"
        breakdown['Education'] = f"{found_edu_str} ({edu_status})"

        # --- 4. Foreign Language (Chỉ Đạt / Chưa đạt, không chấm điểm) ---
        req_langs = jd_requirements_parsed.get('foreign_languages', [])
        found_langs = cv_data.get('lang_extracted', [])

        detected_names = []
        if isinstance(found_langs, list):
            for item in found_langs:
                if isinstance(item, str):
                    base_lang = re.sub(r'\(.*?\)', '', item).strip().lower()
                    detected_names.append(base_lang)
        elif isinstance(found_langs, dict):
            detected_names = [k.strip().lower() for k in found_langs.keys()]

        if not req_langs:
            lang_status = "Đạt"
            lang_ratio = 1.0
        else:
            match_count = 0
            for req in req_langs:
                req_lower = req.strip().lower()
                if any(req_lower in d or d in req_lower for d in detected_names):
                    match_count += 1
            lang_ratio = match_count / len(req_langs)
            lang_status = "Đạt" if match_count >= len(req_langs) else "Chưa đạt"

        cand_lang_str = ", ".join(cv_data.get('lang_extracted', [])) if cv_data.get('lang_extracted') else "Chưa ghi nhận"
        req_lang_str = ", ".join(req_langs) if req_langs else "Không yêu cầu"

        breakdown['Languages_Status'] = lang_status
        breakdown['Languages_Details'] = f"{cand_lang_str} (Yêu cầu: {req_lang_str})"
        breakdown['Languages'] = f"{cand_lang_str} ({lang_status})"

        # --- 5. Overall Recommendation (Đánh giá tổng hợp) ---
        all_passed = (skills_status == "Đạt" and exp_status == "Đạt" and edu_status == "Đạt" and lang_status == "Đạt")
        
        if all_passed:
            overall = "Đạt Yêu Cầu"
        elif skills_status == "Đạt" and sum([exp_status == "Chưa đạt", edu_status == "Chưa đạt", lang_status == "Chưa đạt"]) <= 1:
            overall = "Cân Nhắc Phỏng Vấn"
        else:
            overall = "Chưa Đạt Yêu Cầu"

        breakdown['Overall'] = overall

        # Tổng điểm thang 10 phản ánh cả 4 tiêu chí, không chỉ riêng kỹ năng.
        skills_ratio = tech_score_10 / 10.0
        total_score = round(
            10.0 * (
                SCORING_WEIGHTS['skills'] * skills_ratio
                + SCORING_WEIGHTS['experience'] * exp_ratio
                + SCORING_WEIGHTS['education'] * edu_ratio
                + SCORING_WEIGHTS['languages'] * lang_ratio
            ),
            1,
        )
        total_score = min(max(total_score, 0.0), 10.0)

        breakdown['Total_Score'] = f"{total_score:.1f}"
        breakdown['Weights'] = (
            f"Kỹ năng {SCORING_WEIGHTS['skills']:.0%} · Kinh nghiệm {SCORING_WEIGHTS['experience']:.0%} · "
            f"Học vấn {SCORING_WEIGHTS['education']:.0%} · Ngoại ngữ {SCORING_WEIGHTS['languages']:.0%}"
        )

        return total_score, breakdown

