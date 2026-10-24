import os
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from huggingface_hub import hf_hub_download

from core.config import settings
from core.logger import logger

load_dotenv()

class GeminiProvider:
    """Client giao tiếp với Google Gemini API qua giao thức REST HTTP (không phụ thuộc SDK nặng)."""
    
    DEFAULT_MODEL = "gemini-2.5-flash"
    FALLBACK_MODEL = "gemini-1.5-flash"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.4) -> str:
        """Gửi yêu cầu sinh văn bản tới Gemini API."""
        if not self.is_configured():
            return "⚠️ Chưa cấu hình GEMINI_API_KEY. Vui lòng nhập API Key ở thanh bên hoặc trong file .env."

        # Thử gọi model 2.5-flash trước, nếu lỗi fallback về 1.5-flash
        for model_name in [self.DEFAULT_MODEL, self.FALLBACK_MODEL]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            headers = {"Content-Type": "application/json"}
            
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": 2048
                }
            }

            if system_prompt:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_prompt}]
                }

            try:
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                
                logger.warning(f"Gemini API ({model_name}) error code {response.status_code}: {response.text[:200]}")
            except Exception as e:
                logger.error(f"Lỗi kết nối Gemini API ({model_name}): {e}")

        return "❌ Không thể kết nối tới Google Gemini API. Vui lòng kiểm tra lại API Key và kết nối mạng."

class LocalLLM:
    """Singleton quản lý mô hình Local GGUF (Qwen2.5-7B) chạy offline."""
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            try:
                from llama_cpp import Llama
                logger.info("Đang nạp Local LLM Qwen2.5-7B...")
                model_path = hf_hub_download(repo_id=settings.LLM_REPO_ID, filename=settings.LLM_FILENAME)
                cls._instance = Llama(
                    model_path=model_path,
                    n_ctx=4096,
                    n_gpu_layers=-1,
                    verbose=False
                )
                logger.info("Nạp Local LLM thành công.")
            except ImportError:
                logger.warning("Thư viện llama-cpp-python chưa được cài đặt.")
                return None
            except Exception as e:
                logger.error(f"Lỗi nạp Local LLM: {e}")
                return None
        return cls._instance

class LLMFactory:
    """Factory Router hỗ trợ chuyển đổi linh hoạt giữa Gemini Cloud và Local Model."""
    
    @staticmethod
    def get_provider(provider_type: str = "gemini", api_key: Optional[str] = None):
        if provider_type.lower() == "gemini":
            return GeminiProvider(api_key=api_key)
        else:
            return LocalLLM.get_instance()
