# services/jd_parser_service.py
import re
from typing import Dict, List, Any
from core.constants import SKILL_LEVEL_MAPPING, SKILL_ALIASES
from schemas.models import JDRequirements

def _parse_skill_list_to_dict(skill_list: List[str]) -> Dict[str, int]:
    """
    Chuyển list ["Python (Senior)", "Docker"] thành {"Python": 3, "Docker": 1}.
    Tự động chuẩn hóa từ đồng nghĩa (Aliases).
    """
    result = {}
    if not skill_list:
        return result

    for item in skill_list:
        if not isinstance(item, str):
            continue

        # 1. Tách tên kỹ năng (Loại bỏ phần trong ngoặc)
        raw_skill_name = re.sub(r'\s*\(.*?\)', '', item).strip()
        if not raw_skill_name:
            continue

        # Chuẩn hóa alias (vd: k8s -> Kubernetes, js -> JavaScript)
        canonical_name = SKILL_ALIASES.get(raw_skill_name.lower(), raw_skill_name).title()

        # 2. Tìm Level trong ngoặc đơn (Mặc định 1: Junior)
        level_score = 1
        match = re.search(r'\((.*?)\)', item)
        if match:
            level_text = match.group(1).lower()
            for key, score in SKILL_LEVEL_MAPPING.items():
                if key.lower() in level_text:
                    level_score = score
                    break

        result[canonical_name] = level_score

    return result

def parse_jd_input(jd_raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chuẩn hóa dữ liệu JD đầu vào từ UI/API thành dictionary chuẩn.
    """
    parsed_jd = jd_raw_data.copy()
    tech_categories = ['programming_languages', 'frameworks', 'databases']

    for category in tech_categories:
        raw_list = jd_raw_data.get(category, [])
        if raw_list:
            parsed_jd[category] = _parse_skill_list_to_dict(raw_list)
        else:
            parsed_jd[category] = {}

    if 'education_level' in parsed_jd and parsed_jd['education_level']:
        parsed_jd['education_level'] = parsed_jd['education_level'].strip().title()

    return parsed_jd

def to_jd_schema(jd_dict: Dict[str, Any]) -> JDRequirements:
    """Chuyển đổi dictionary thành Pydantic model JDRequirements."""
    return JDRequirements(
        job_title=jd_dict.get('job_title', 'Software Engineer'),
        required_experience_years=float(jd_dict.get('required_experience_years', 0)),
        education_level=jd_dict.get('education_level', 'Bachelor'),
        programming_languages=jd_dict.get('programming_languages', {}),
        frameworks=jd_dict.get('frameworks', {}),
        databases=jd_dict.get('databases', {}),
        foreign_languages=jd_dict.get('foreign_languages', []),
        raw_description=jd_dict.get('raw_description', '')
    )
