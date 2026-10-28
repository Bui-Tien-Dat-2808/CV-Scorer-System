# services/jd_parser_service.py
import re
from typing import Dict, List, Any
from core.constants import (
    SKILL_LEVEL_MAPPING, SKILL_ALIASES, LANGUAGE_LEVELS,
    LANGUAGES, FRAMEWORKS, DATABASES, AI_ML_SKILLS, DEVOPS_TOOLS
)
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

def categorize_skills(raw_skills: List[str]) -> Dict[str, List[str]]:
    """
    Phân loại danh sách kỹ năng người dùng nhập vào đúng nhóm JD:
    programming_languages, frameworks, databases.
    Công cụ DevOps/AI được xếp vào nhóm databases (cột "Cơ sở dữ liệu & Công cụ" trên UI).
    """
    buckets: Dict[str, List[str]] = {
        "programming_languages": [],
        "frameworks": [],
        "databases": [],
    }

    for item in raw_skills:
        if not isinstance(item, str):
            continue

        skill_name = re.sub(r'\s*\(.*?\)', '', item).strip()
        if not skill_name:
            continue

        key = SKILL_ALIASES.get(skill_name.lower(), skill_name.lower())

        if key in DATABASES:
            buckets["databases"].append(item.strip())
        elif key in LANGUAGES:
            buckets["programming_languages"].append(item.strip())
        elif key in FRAMEWORKS or key in AI_ML_SKILLS:
            buckets["frameworks"].append(item.strip())
        elif key in DEVOPS_TOOLS:
            buckets["databases"].append(item.strip())
        else:
            buckets["frameworks"].append(item.strip())

    return buckets

def parse_language_requirements(raw: str) -> tuple:
    """
    Tách chuỗi "English:advanced, Japanese:basic" thành (["English","Japanese"],
    {"English": 3, "Japanese": 1}) theo thang LANGUAGE_LEVELS.

    Chuỗi rỗng nghĩa là JD không yêu cầu ngoại ngữ -> ([], {}).
    Mức độ không nêu thì coi như 'basic', tức chỉ bắt buộc sự hiện diện của ngôn ngữ.
    """
    names: List[str] = []
    levels: Dict[str, int] = {}
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        language, _, level_token = entry.partition(":")
        language = language.strip()
        if not language:
            continue
        level_token = level_token.strip().lower() or "basic"
        if level_token not in LANGUAGE_LEVELS:
            raise ValueError(
                f"Mức độ ngoại ngữ không hợp lệ: '{level_token}' (ngôn ngữ '{language}'). "
                f"Chấp nhận: {', '.join(LANGUAGE_LEVELS)}"
            )
        if language not in names:
            names.append(language)
            levels[language] = LANGUAGE_LEVELS[level_token]
    return names, levels


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
        language_levels=jd_dict.get('language_levels', {}),
        raw_description=jd_dict.get('raw_description', '')
    )
