import re
from typing import Dict, Any, Tuple, List

from core.constants import (
    SKILL_LEVEL_MAPPING, EDUCATION_RANKING, SKILL_ALIASES,
    LANGUAGE_LEVELS, LANGUAGE_LEVEL_LABELS
)
from core.logger import logger
from utils.text_cleaner import clean_text

# Tỷ trọng từng tiêu chí khi quy ra điểm tổng hợp thang 10.
SCORING_WEIGHTS = {'skills': 0.6, 'experience': 0.2, 'education': 0.1, 'languages': 0.1}

_CEFR_RANK = {'a1': 1, 'a2': 1, 'b1': 2, 'b2': 2, 'c1': 3, 'c2': 4}

# Ngưỡng quy đổi chứng chỉ sang thang LANGUAGE_LEVELS, so từ band cao xuống thấp.
_CERT_BANDS = [
    (r'ielts\s*([0-9](?:\.[05])?)', [(8.5, 4), (7.0, 3), (5.0, 2)]),
    (r'toeic\s*([0-9]{3,4})', [(945, 4), (785, 3), (600, 2)]),
    (r'toefl(?:\s*ibt)?\s*([0-9]{2,3})', [(105, 4), (94, 3), (60, 2)]),
]
_JLPT_RANK = {'1': 3, '2': 2, '3': 1, '4': 1, '5': 1}
_HSK_RANK = {'6': 4, '5': 3, '4': 2, '3': 2, '2': 1, '1': 1}
_LANGUAGE_KEYWORD_RANK = [
    (r'\bnative\b|bản\s*ngữ', 4),
    (r'fluent|thành\s*thạo|proficient|advanced', 3),
    (r'intermediate|trung\s*bình|\bkhá\b|working', 2),
    (r'basic|cơ\s*bản|sơ\s*cấp|elementary', 1),
]


def language_evidence_level(evidence: str) -> int:
    """
    Suy trình độ ngoại ngữ từ chuỗi CV trích được, ví dụ 'English (IELTS 7.0)' -> 3.

    Trả 1 (basic) khi chỉ thấy tên ngôn ngữ mà không có bằng chứng mức độ: ứng viên
    vẫn được tính là có dùng ngôn ngữ đó, nhưng không đủ cho yêu cầu cao hơn.
    """
    text = (evidence or '').lower()

    for pattern, bands in _CERT_BANDS:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            score = float(match.group(1))
        except ValueError:
            continue
        for threshold, rank in bands:
            if score >= threshold:
                return rank
        return 1

    match = re.search(r'jlpt\s*n?([1-5])', text)
    if match:
        return _JLPT_RANK[match.group(1)]

    match = re.search(r'hsk\s*([1-6])', text)
    if match:
        return _HSK_RANK[match.group(1)]

    match = re.search(r'\b([abc][12])\b', text)
    if match:
        return _CEFR_RANK[match.group(1)]

    for pattern, rank in _LANGUAGE_KEYWORD_RANK:
        if re.search(pattern, text):
            return rank

    return 1

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

        # --- 4. Foreign Language (so cả tên lẫn trình độ, chỉ Đạt / Chưa đạt) ---
        req_langs = jd_requirements_parsed.get('foreign_languages', [])
        req_levels = jd_requirements_parsed.get('language_levels', {})
        found_langs = cv_data.get('lang_extracted', [])

        # Tên chuẩn hoá -> chuỗi bằng chứng gốc, để vừa khớp tên vừa suy được trình độ
        evidence_by_name: Dict[str, str] = {}
        if isinstance(found_langs, dict):
            for key, value in found_langs.items():
                evidence_by_name[str(key).strip().lower()] = f"{key} ({value})" if value else str(key)
        elif isinstance(found_langs, list):
            for item in found_langs:
                if not isinstance(item, str):
                    continue
                base = re.sub(r'\(.*?\)', '', item).strip().lower()
                if base:
                    evidence_by_name[base] = item

        if not req_langs:
            lang_status = "Đạt"
            lang_ratio = 1.0
            lang_detail = "JD không yêu cầu ngoại ngữ"
        else:
            matched = 0
            lines = []
            for req in req_langs:
                req_name = req.strip()
                req_key = req_name.lower()
                required_rank = req_levels.get(req_name, 1)
                found_key = next(
                    (k for k in evidence_by_name if req_key in k or k in req_key),
                    None
                )
                if found_key is None:
                    lines.append(f"{req_name}: không ghi nhận (cần {LANGUAGE_LEVEL_LABELS[required_rank]})")
                    continue

                evidence = evidence_by_name[found_key]
                found_rank = language_evidence_level(evidence)
                if found_rank >= required_rank:
                    matched += 1
                    lines.append(f"{evidence} ≥ {LANGUAGE_LEVEL_LABELS[required_rank]}")
                else:
                    lines.append(f"{evidence} < {LANGUAGE_LEVEL_LABELS[required_rank]}")

            lang_ratio = matched / len(req_langs)
            lang_status = "Đạt" if matched == len(req_langs) else "Chưa đạt"
            lang_detail = "; ".join(lines)

        cand_lang_str = ", ".join(cv_data.get('lang_extracted', [])) if cv_data.get('lang_extracted') else "Chưa ghi nhận"

        breakdown['Languages_Status'] = lang_status
        breakdown['Languages_Details'] = lang_detail
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

