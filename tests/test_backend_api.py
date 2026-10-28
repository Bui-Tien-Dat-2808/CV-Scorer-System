import os
import re

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_frontend_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "TalentMatch Enterprise" in response.text
    assert "navTabs" in response.text

def test_frontend_served_without_cdn():
    """UI phải chạy offline được: không còn thẻ script/stylesheet nào trỏ tới CDN."""
    response = client.get("/")
    external = re.findall(r'(?:src|href)="(https?://[^"]+)"', response.text)
    # Google Fonts là tài nguyên ngoài duy nhất còn lại, và nó suy giảm về font hệ thống.
    assert [u for u in external if "fonts.g" not in u] == []

REQUIRED_ENGINES = {
    "fastpath_pdf", "ocr_engine", "vector_semantic_search",
    "llm_cloud", "llm_local", "history_storage",
}

def test_health_check_reports_real_engine_state():
    """Health phản ánh trạng thái thật, nên 'degraded' trên máy thiếu API key là kết quả đúng."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "TalentMatch AI Core"
    assert set(data["engines"]) == REQUIRED_ENGINES
    assert data["status"] in {"healthy", "degraded"}
    assert data["engines"]["llm_local"] in {
        "loaded", "available", "missing_llama_cpp", "missing_weights"
    }

    # status phải là hàm của chính các động cơ, không phải giá trị cứng
    missing = [k for k, v in data["engines"].items()
               if str(v).startswith("missing") or v == "read_only"]
    assert (data["status"] == "degraded") == bool(missing)

    # Khoá thật không bao giờ được đi qua health endpoint
    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key:
        assert api_key not in response.text

def test_clear_history_requires_admin_token_when_configured(monkeypatch):
    """Đã đặt APP_ADMIN_TOKEN thì xoá lịch sử phải có token đúng; sai token là 401."""
    from backend import main as backend_main

    cleared = []
    monkeypatch.setattr(backend_main.settings, "ADMIN_TOKEN", "s3cret-token")
    # Spy thay vì xoá thật: lịch sử của người dùng không được đụng tới trong test.
    monkeypatch.setattr(
        backend_main.history_service, "clear_history", lambda: cleared.append(True)
    )

    assert client.delete("/api/v1/history").status_code == 401
    assert client.delete(
        "/api/v1/history", headers={"X-Admin-Token": "wrong"}
    ).status_code == 401
    assert cleared == []

    ok = client.delete("/api/v1/history", headers={"X-Admin-Token": "s3cret-token"})
    assert ok.status_code == 200
    assert cleared == [True]

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

