import pytest
import os
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_frontend_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "TalentMatch Enterprise" in response.text
    assert "navTabs" in response.text

def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "TalentMatch AI Core"

def test_get_sample_cvs():
    response = client.get("/api/v1/sample-cvs")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "files" in data
    assert data["count"] > 0

def test_get_history():
    response = client.get("/api/v1/history")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)

def test_evaluate_single_sample_cv():
    sample_dir = os.path.join("data", "sample_cvs")
    sample_files = [f for f in os.listdir(sample_dir) if f.endswith(".pdf")]
    assert len(sample_files) > 0
    test_pdf_path = os.path.join(sample_dir, sample_files[0])

    with open(test_pdf_path, "rb") as f:
        response = client.post(
            "/api/v1/evaluate",
            files={"file": (sample_files[0], f, "application/pdf")},
            data={
                "job_title": "Python Developer",
                "required_experience_years": 2.0,
                "education_level": "Bachelor",
                "tech_skills": "Python, Docker, SQL",
                "foreign_languages": "English",
                "llm_provider": "gemini"
            }
        )
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    data = result["data"]
    assert "candidate_name" in data
    assert "total_score" in data
    assert "breakdown" in data
    assert "ai_feedback" in data

