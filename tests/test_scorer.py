import pytest
from services.scoring_service import ScoringService

@pytest.fixture
def scorer():
    return ScoringService()

def test_education_rank(scorer):
    assert scorer.get_education_rank("Phd in Computer Science") == 4
    assert scorer.get_education_rank("Master of Science") == 3
    assert scorer.get_education_rank("Bachelor of Engineering") == 2
    assert scorer.get_education_rank("Associate Degree") == 1
    assert scorer.get_education_rank("High School") == 0
    assert scorer.get_education_rank(None) == 0

def test_skill_level_context_detection(scorer):
    cv_text = """
    Technical Skills:
    - Python: 4 years experience, strong background, senior level backend developer.
    - Docker: basic knowledge, familiar with containerization.
    """
    python_level = scorer._detect_level_from_context("Python", cv_text)
    docker_level = scorer._detect_level_from_context("Docker", cv_text)

    assert python_level == 3  # Senior
    assert docker_level == 1  # Basic / Familiar

def test_calculate_score_bounded(scorer):
    cv_data = {
        "full_name": "Test Candidate",
        "years_experience": 3,
        "education_level": "Bachelor",
        "skills_extracted": {
            "programming_languages": {"Python": 2},
            "frameworks": {"FastAPI": 2},
            "databases": {"Postgresql": 1}
        },
        "lang_extracted": ["English (Fluent)"],
        "raw_text": "Experienced Python Backend Developer working with FastAPI and PostgreSQL."
    }
    jd_req = {
        "job_title": "Python Developer",
        "required_experience_years": 2,
        "education_level": "Bachelor",
        "programming_languages": {"Python": 2},
        "frameworks": {"FastAPI": 1},
        "databases": {"Postgresql": 1},
        "foreign_languages": ["English"]
    }

    score, breakdown = scorer.calculate_score(cv_data, jd_req)
    assert 0 <= score <= 10.0
    assert "Skills" in breakdown
    assert "Experience" in breakdown
    assert "Education_Status" in breakdown
    assert "Languages_Status" in breakdown
    assert breakdown["Skills_Status"] == "Đạt"
    assert breakdown["Experience_Status"] == "Đạt"
    assert breakdown["Education_Status"] == "Đạt"
    assert breakdown["Languages_Status"] == "Đạt"
    assert "Semantic Fit" not in breakdown



def test_composite_score_uses_all_criteria(scorer):
    """Điểm tổng hợp phải nhỏ hơn điểm kỹ năng khi các tiêu chí khác chưa đạt."""
    cv_data = {
        "full_name": "Test Candidate",
        "years_experience": 0,
        "education_level": "None",
        "skills_extracted": {
            "programming_languages": {"Python": 2},
            "frameworks": {},
            "databases": {}
        },
        "lang_extracted": [],
        "raw_text": "Python developer."
    }
    jd_req = {
        "job_title": "Python Developer",
        "required_experience_years": 4,
        "education_level": "Bachelor",
        "programming_languages": {"Python": 2},
        "frameworks": {},
        "databases": {},
        "foreign_languages": ["English"]
    }

    score, breakdown = scorer.calculate_score(cv_data, jd_req)
    skills_score = float(breakdown["Skills_Score"])

    # 60% skills + 20% exp (0/4) + 10% edu (0) + 10% lang (0)
    assert skills_score == 10.0
    assert score == pytest.approx(6.0, abs=0.1)
    assert breakdown["Total_Score"] == f"{score:.1f}"
    assert "60%" in breakdown["Weights"]
    assert breakdown["Experience_Status"] == "Chưa đạt"
    assert breakdown["Overall"] == "Chưa Đạt Yêu Cầu"


def test_composite_score_partial_experience_credit(scorer):
    cv_data = {
        "years_experience": 1,
        "education_level": "Bachelor",
        "skills_extracted": {"programming_languages": {}, "frameworks": {}, "databases": {}},
        "lang_extracted": ["English (IELTS 6.0)"],
        "raw_text": ""
    }
    jd_req = {
        "required_experience_years": 2,
        "education_level": "Bachelor",
        "programming_languages": {},
        "frameworks": {},
        "databases": {},
        "foreign_languages": []
    }

    score, breakdown = scorer.calculate_score(cv_data, jd_req)
    # skills 10/10 (không yêu cầu) + exp 50% + edu đạt + lang đạt = 6 + 1 + 1 + 1
    assert score == pytest.approx(9.0, abs=0.1)
    assert breakdown["Experience_Status"] == "Chưa đạt"
