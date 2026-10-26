import pytest
import models.llm_model as llm_model
from models.llm_model import GeminiProvider, GeminiNotConfiguredError, GeminiAPIError, LocalLLMError
from services.llm_service import generate_ai_feedback, CLOUD_UNAVAILABLE_NOTICE


@pytest.fixture(autouse=True)
def no_cloud_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


CV_DATA = {"full_name": "A", "years_experience": 1, "raw_text": "Python developer"}
JD = {"job_title": "Python Dev", "required_experience_years": 1}


class FakeLocalLLM:
    def __init__(self, loaded=True, text="LOCAL REPORT", raises=None):
        self._loaded = loaded
        self.text = text
        self.raises = raises

    def is_loaded(self):
        return self._loaded

    def generate_response(self, prompt, system_instruction=""):
        if self.raises:
            raise self.raises
        return self.text


def test_missing_key_raises_instead_of_returning_error_string(monkeypatch):
    monkeypatch.setattr(llm_model.GeminiProvider, "api_key", "", raising=False)
    provider = GeminiProvider(api_key="")
    with pytest.raises(GeminiNotConfiguredError):
        provider.generate("hello")


def test_api_key_sent_in_header_not_url(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        text = "{}"

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(llm_model.requests, "post", fake_post)
    provider = GeminiProvider(api_key="SECRET-KEY")
    assert provider.generate("hello") == "OK"
    assert "SECRET-KEY" not in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "SECRET-KEY"


def test_gemini_api_error_after_trying_fallback_models(monkeypatch):
    tried = []

    class FailResponse:
        status_code = 503
        text = "unavailable"

    def fake_post(url, json=None, headers=None, timeout=None):
        tried.append(url.split("/models/")[1].split(":")[0])
        return FailResponse()

    monkeypatch.setattr(llm_model.requests, "post", fake_post)
    provider = GeminiProvider(api_key="SECRET-KEY")
    with pytest.raises(GeminiAPIError):
        provider.generate("hello")
    assert tried == [GeminiProvider.DEFAULT_MODEL, GeminiProvider.FALLBACK_MODEL]


def test_fallback_to_loaded_local_llm(monkeypatch):
    monkeypatch.setattr(GeminiProvider, "generate", lambda self, *a, **k: (_ for _ in ()).throw(GeminiAPIError("boom")))
    out = generate_ai_feedback(
        CV_DATA, JD, 5.0, {}, provider_type="gemini", api_key="",
        local_llm_instance=FakeLocalLLM(loaded=True),
    )
    assert out == "LOCAL REPORT"


def test_cloud_failure_without_local_returns_friendly_notice():
    out = generate_ai_feedback(
        CV_DATA, JD, 5.0, {}, provider_type="gemini", api_key="",
        local_llm_instance=FakeLocalLLM(loaded=False),
    )
    assert out == CLOUD_UNAVAILABLE_NOTICE
    assert "boom" not in out and "Traceback" not in out and "Error" not in out


def test_local_provider_failure_returns_friendly_notice():
    out = generate_ai_feedback(
        CV_DATA, JD, 5.0, {}, provider_type="local",
        local_llm_instance=FakeLocalLLM(raises=LocalLLMError("weights missing")),
    )
    assert "tạm hoãn" in out
    assert "weights missing" not in out
