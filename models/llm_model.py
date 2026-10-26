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
            return "⚠️ Chưa cấu hình GEMINI_API_KEY. Vui lòng nhập API Key ở ô cấu hình hoặc trong file .env."

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

    def generate_analysis(self, prompt: str, system_instruction: str = "", temperature: float = 0.4) -> str:
        return self.generate(prompt, system_prompt=system_instruction, temperature=temperature)


class LocalLLM:
    """Singleton quản lý mô hình Local GGUF (Qwen2.5-7B) chạy offline."""
    _instance = None

    def __init__(self):
        self._model = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_loaded(self) -> bool:
        return self._model is not None

    def load_model(self) -> bool:
        if self._model is not None:
            return True
        try:
            from llama_cpp import Llama
            logger.info("Đang nạp Local LLM Qwen2.5-7B...")
            model_path = hf_hub_download(repo_id=settings.LLM_REPO_ID, filename=settings.LLM_FILENAME)
            self._model = Llama(
                model_path=model_path,
                n_ctx=4096,
                n_gpu_layers=-1,
                verbose=False
            )
            logger.info("Nạp Local LLM thành công.")
            return True
        except ImportError:
            logger.warning("Thư viện llama-cpp-python chưa được cài đặt.")
            return False
        except Exception as e:
            logger.error(f"Lỗi nạp Local LLM: {e}")
            return False

    def generate_response(self, prompt: str, system_instruction: str = "") -> str:
        if not self.is_loaded():
            if not self.load_model():
                return "❌ Không thể nạp Local LLM (llama-cpp-python hoặc trọng số GGUF bị thiếu)."
        
        try:
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            
            output = self._model.create_chat_completion(
                messages=messages,
                max_tokens=2048,
                temperature=0.3
            )
            return output["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Lỗi sinh văn bản qua Local LLM: {e}")
            return f"❌ Lỗi suy luận Local LLM: {e}"


class LLMFactory:
    """Factory Router hỗ trợ chuyển đổi linh hoạt giữa Gemini Cloud và Local Model."""
    
    @staticmethod
    def get_provider(provider_type: str = "gemini", api_key: Optional[str] = None):
        if provider_type.lower() == "gemini":
            return GeminiProvider(api_key=api_key)
        else:
            return LocalLLM.get_instance()
