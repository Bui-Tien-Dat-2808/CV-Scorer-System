import inspect
import os

import pytest
from fastapi.testclient import TestClient

from backend.main import app, evaluate_single_cv
from core.constants import LANGUAGE_LEVELS
from services.cv_parser_service import LANGUAGE_SYNONYMS
from services.jd_parser_service import parse_language_requirements
from services.scoring_service import ScoringService, language_evidence_level

client = TestClient(app)


@pytest.fixture
def scorer():
    return ScoringService()


def _cv(cv_data: dict, jd_langs, jd_levels) -> dict:
    """Dựng JD đã parse đúng định dạng mà endpoint truyền vào scoring service."""
    names, levels = parse_language_requirements(jd_langs)
    return {
        "full_name": "Test Candidate",
        "years_experience": 3,
        "education_level": "Bachelor",
        "skills_extracted": {
            "programming_languages": {"Python": 2},
            "frameworks": {"FastAPI": 2},
            "databases": {"Postgresql": 1},
        },
        "lang_extracted": cv_data,
        "raw_text": "Python Backend Developer with FastAPI and PostgreSQL.",
        "_jd": {
            "job_title": "Python Developer",
            "required_experience_years": 2,
            "education_level": "Bachelor",
            "programming_languages": {"Python": 2},
            "frameworks": {"FastAPI": 1},
            "databases": {"Postgresql": 1},
            "foreign_languages": names,
            "language_levels": levels,
        },
    }


def _score(scorer, evidence, jd_langs):
    bundle = _cv(evidence, jd_langs, None)
    return scorer.calculate_score(bundle, bundle["_jd"])


# ---------------------------------------------------------------- parse phía JD

def test_empty_requirement_means_language_not_required():
    assert parse_language_requirements("") == ([], {})
    assert parse_language_requirements("   ") == ([], {})
    assert parse_language_requirements(None) == ([], {})


def test_language_without_level_defaults_to_basic():
    names, levels = parse_language_requirements("English")
    assert names == ["English"]
    assert levels == {"English": LANGUAGE_LEVELS["basic"]}


def test_language_levels_parsed_per_language():
    names, levels = parse_language_requirements("English:advanced, Japanese:basic")
    assert names == ["English", "Japanese"]
    assert levels["English"] == LANGUAGE_LEVELS["advanced"]
    assert levels["Japanese"] == LANGUAGE_LEVELS["basic"]


def test_duplicate_language_keeps_first_entry():
    names, levels = parse_language_requirements("English:advanced, English:basic")
    assert names == ["English"]
    assert levels == {"English": LANGUAGE_LEVELS["advanced"]}


def test_unknown_level_is_rejected_not_silently_dropped():
    """Im lặng bỏ qua level sai sẽ biến 'yêu cầu C1' thành 'không yêu cầu' — sai điểm."""
    with pytest.raises(ValueError, match="không hợp lệ"):
        parse_language_requirements("English:fluent")


@pytest.mark.parametrize("level", sorted(LANGUAGE_LEVELS))
def test_every_declared_level_parses(level):
    names, levels = parse_language_requirements(f"English:{level}")
    assert levels["English"] == LANGUAGE_LEVELS[level]


# ---------------------------------------------------------- đọc bằng chứng phía CV

@pytest.mark.parametrize("evidence,expected", [
    ("English (IELTS 8.5)", 4),
    ("English (IELTS 7.0)", 3),
    ("English (IELTS 6.0)", 2),
    ("English (IELTS 3.5)", 1),
    ("English (TOEIC 990)", 4),
    ("English (TOEIC 800)", 3),
    ("English (TOEIC 700)", 2),
    ("English (TOEIC 400)", 1),
    ("English (TOEFL iBT 110)", 4),
    ("English (TOEFL 95)", 3),
])
def test_certificate_scores_map_to_levels(evidence, expected):
    assert language_evidence_level(evidence) == expected


@pytest.mark.parametrize("evidence,expected", [
    ("English (C2)", 4),
    ("English (C1)", 3),
    ("English (B2)", 2),
    ("English (A2)", 1),
    ("Japanese (JLPT N1)", 3),
    ("Japanese (JLPT N2)", 2),
    ("Chinese (HSK 6)", 4),
    ("Chinese (HSK 5)", 3),
    ("Chinese (HSK 3)", 2),
])
def test_cefr_and_asian_certificates_map_to_levels(evidence, expected):
    assert language_evidence_level(evidence) == expected


@pytest.mark.parametrize("evidence,expected", [
    ("English (Native)", 4),
    ("English (Bản ngữ)", 4),
    ("English (Thành thạo)", 3),
    ("English (Fluent)", 3),
    ("English (Trung bình)", 2),
    ("English (Intermediate)", 2),
    ("English (Cơ bản)", 1),
])
def test_written_levels_map_to_levels(evidence, expected):
    assert language_evidence_level(evidence) == expected


def test_bare_language_name_counts_as_basic_evidence():
    """Chỉ ghi 'English' không chứng minh được trình độ cao, nhưng vẫn tính là có dùng."""
    assert language_evidence_level("English") == 1


# ------------------------------------------------------------------- chấm điểm

def test_language_status_passes_when_candidate_meets_required_level(scorer):
    _, breakdown = _score(scorer, ["English (IELTS 7.5)"], "English:advanced")
    assert breakdown["Languages_Status"] == "Đạt"


def test_language_status_fails_when_candidate_below_required_level(scorer):
    _, breakdown = _score(scorer, ["English (IELTS 6.0)"], "English:advanced")
    assert breakdown["Languages_Status"] == "Chưa đạt"
    assert "<" in breakdown["Languages_Details"]


def test_same_certificate_passes_a_lower_requirement(scorer):
    """IELTS 6.0 trượt yêu cầu C1 nhưng phải đạt yêu cầu B1-B2 — chỉ mức độ mới đổi kết quả."""
    _, breakdown = _score(scorer, ["English (IELTS 6.0)"], "English:intermediate")
    assert breakdown["Languages_Status"] == "Đạt"


def test_missing_language_fails_even_at_basic_requirement(scorer):
    _, breakdown = _score(scorer, [], "English:basic")
    assert breakdown["Languages_Status"] == "Chưa đạt"
    assert "không ghi nhận" in breakdown["Languages_Details"]


def test_not_requiring_language_scores_full_ratio(scorer):
    score_with, bd_with = _score(scorer, [], "")
    score_missing, bd_missing = _score(scorer, [], "English:advanced")
    assert bd_with["Languages_Status"] == "Đạt"
    assert "không yêu cầu" in bd_with["Languages_Details"]
    # Không yêu cầu thì ứng viên không bị trừ 10% trọng số ngoại ngữ.
    assert score_with > score_missing


def test_multiple_languages_all_must_match(scorer):
    evidence = ["English (IELTS 8.0)", "Japanese (JLPT N2)"]
    _, both_ok = _score(scorer, evidence, "English:advanced,Japanese:intermediate")
    assert both_ok["Languages_Status"] == "Đạt"

    _, one_bad = _score(scorer, evidence, "English:advanced,Japanese:advanced")
    assert one_bad["Languages_Status"] == "Chưa đạt"
    # Một trong hai đạt -> ratio 0.5, nên điểm cao hơn trường hợp trượt hết.
    score_one_bad, _ = _score(scorer, evidence, "English:advanced,Japanese:advanced")
    score_none, _ = _score(scorer, [], "English:advanced,Japanese:advanced")
    assert score_one_bad > score_none


def test_language_names_from_cv_are_matched_case_insensitively(scorer):
    _, breakdown = _score(scorer, ["english (IELTS 8.0)"], "English:advanced")
    assert breakdown["Languages_Status"] == "Đạt"


# ------------------------------------------------- UI/endpoint không còn nhận key

def test_ui_has_no_api_key_input():
    response = client.get("/")
    assert "geminiApiKey" not in response.text
    assert "apiKeyGroup" not in response.text


def test_evaluate_endpoint_has_no_client_key_parameter():
    """Key chỉ được phép đến từ môi trường server; tham số header phải biến mất hẳn."""
    params = inspect.signature(evaluate_single_cv).parameters
    assert "x_gemini_api_key" not in params
    assert not any("api_key" in name.lower() for name in params)


def test_ui_offers_language_toggle_and_rows():
    response = client.get("/")
    assert 'name="langRequired"' in response.text
    assert 'id="langReqRows"' in response.text
    assert 'id="addLangReqBtn"' in response.text
    assert "NGOẠI NGỮ BẮT BUỘC" not in response.text


def test_ui_language_options_cover_every_language_the_parser_detects():
    """Dropdown dựng bằng JS phải liệt kê đủ tập ngôn ngữ mà cv_parser nhận diện được."""
    with open(os.path.join("frontend", "assets", "js", "app.js"), encoding="utf-8") as f:
        script = f.read()
    block = script.split("const LANGUAGE_OPTIONS = [")[1].split("];")[0]
    for language in LANGUAGE_SYNONYMS:
        assert f'"{language}"' in block, f"Thiếu {language} trong LANGUAGE_OPTIONS"



def _post_evaluate(monkeypatch, foreign_languages):
    """Gọi endpoint với bước sinh báo cáo AI đã stub: test này nói về ngoại ngữ, không về LLM."""
    monkeypatch.setattr("backend.main.generate_ai_feedback", lambda **kwargs: "stub")
    sample_dir = os.path.join("data", "sample_cvs")
    sample_files = [f for f in os.listdir(sample_dir) if f.endswith(".pdf")]
    assert sample_files, "Cần ít nhất một CV mẫu trong data/sample_cvs"

    with open(os.path.join(sample_dir, sample_files[0]), "rb") as f:
        return client.post(
            "/api/v1/evaluate",
            files={"file": (sample_files[0], f, "application/pdf")},
            data={"foreign_languages": foreign_languages},
        )


def test_evaluate_rejects_unknown_language_level_with_400(monkeypatch):
    """Level không hiểu được phải trả lỗi rõ ràng, không âm thầm hạ xuống 'không yêu cầu'."""
    response = _post_evaluate(monkeypatch, "English:fluent")
    assert response.status_code == 400
    assert "không hợp lệ" in response.json()["detail"]


def test_evaluate_accepts_empty_language_requirement(monkeypatch):
    """FastAPI coi field form rỗng == field bị bỏ trống và thay bằng default.

    Default của foreign_languages vì thế bắt buộc phải là '' — nếu để 'English:basic'
    thì chọn 'Không yêu cầu' trên UI vẫn bị ép tiếng Anh.
    """
    response = _post_evaluate(monkeypatch, "")
    assert response.status_code == 200
    breakdown = response.json()["data"]["breakdown"]
    assert breakdown["Languages_Status"] == "Đạt"
    assert "không yêu cầu" in breakdown["Languages_Details"]
