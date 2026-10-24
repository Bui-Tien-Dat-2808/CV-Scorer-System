import pytest
from schemas.models import CandidateProfile, JDRequirements, ScoreBreakdown, EvaluationResult

def test_candidate_profile_schema_valid():
    candidate = CandidateProfile(
        full_name="Bui Tien Dat",
        email=["datbui@example.com"],
        phone_number="0912345678",
        years_experience=2.5,
        education_level="Bachelor",
        skills_extracted={"programming_languages": {"Python": 2}},
        skills_display={"programming_languages": ["Python (Mid)"]},
        languages_detected=["English (IELTS 7.0)"],
        raw_text="Sample raw text",
        extraction_mode="digital_pdf"
    )
    assert candidate.full_name == "Bui Tien Dat"
    assert candidate.years_experience == 2.5
    assert candidate.extraction_mode == "digital_pdf"
    assert "Python" in candidate.skills_extracted["programming_languages"]

def test_jd_requirements_schema_valid():
    jd = JDRequirements(
        job_title="AI Engineer",
        required_experience_years=2.0,
        education_level="Bachelor",
        programming_languages={"Python": 2},
        frameworks={"FastAPI": 1, "PyTorch": 2},
        databases={"PostgreSQL": 1},
        foreign_languages=["English"]
    )
    assert jd.job_title == "AI Engineer"
    assert jd.required_experience_years == 2.0
    assert len(jd.frameworks) == 2

def test_score_breakdown_schema():
    breakdown = ScoreBreakdown(
        skills_score=35.0,
        experience_score=25.0,
        semantic_score=12.0,
        education_score=10.0,
        language_score=10.0,
        total_score=92.0,
        details={"Skills": "35/40"}
    )
    assert breakdown.total_score == 92.0
    assert breakdown.skills_score <= 40.0

