import pytest
from services.cv_parser_service import CVParserService
from services.jd_parser_service import _parse_skill_list_to_dict

@pytest.fixture
def parser():
    return CVParserService()

def test_find_full_name_filters_headers(parser):
    cv_text = """
    CURRICULUM VITAE
    SENIOR PYTHON DEVELOPER
    Nguyen Van An
    Email: an.nguyen@gmail.com
    Phone: 0987654321
    Summary: 5 years experience in building web apps.
    """
    name = parser._find_full_name(cv_text)
    assert name == "Nguyen Van An"

def test_find_years_experience_from_keyword(parser):
    text1 = "I have 3 years experience as a software engineer."
    assert parser._find_years_experience(text1) == 3.0

def test_find_years_experience_from_date_range(parser):
    text2 = "Backend Developer at FPT Software (2021 - 2024)"
    assert parser._find_years_experience(text2) >= 3.0

def test_extract_emails(parser):
    text = "Contact me at candidate@example.com or backup_email123@work.vn"
    emails = parser._extract_emails(text)
    assert "candidate@example.com" in emails
    assert "backup_email123@work.vn" in emails

def test_extract_foreign_languages(parser):
    text = "Languages: English (IELTS 7.5), Japanese (N3), Vietnamese Native."
    langs = parser._extract_foreign_languages(text)
    assert any("English" in l for l in langs)
    assert any("Japanese" in l for l in langs)

def test_alias_normalization():
    raw_list = ["Python (Senior)", "K8s (Basic)", "Postgres (Good)", "JS (Mid)"]
    parsed = _parse_skill_list_to_dict(raw_list)
    assert "Python" in parsed and parsed["Python"] == 3
    assert "Kubernetes" in parsed and parsed["Kubernetes"] == 1
    assert "Postgresql" in parsed and parsed["Postgresql"] == 2
    assert "Javascript" in parsed and parsed["Javascript"] == 2

