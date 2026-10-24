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

