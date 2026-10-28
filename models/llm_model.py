import os
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from huggingface_hub import hf_hub_download

from core.config import settings
from core.logger import logger

load_dotenv()


class LLMProviderError(RuntimeError):
    """Lỗi của động cơ LLM. Ném để tầng service fallback, thay vì trả chuỗi lỗi thô về UI."""


class GeminiNotConfiguredError(LLMProviderError):
    pass


class GeminiAPIError(LLMProviderError):
    pass


class LocalLLMError(LLMProviderError):
    pass


# Status trả về bởi Google, dịch sang lý do người dùng làm được gì đó.
# Chỉ dùng mã trạng thái — không bao giờ đưa message/API key/body vào UI.
GEMINI_STATUS_HINTS = {
    "PERMISSION_DENIED": "khoá không hợp lệ hoặc chưa được bật cho project",
    "UNAUTHENTICATED": "khoá không hợp lệ",
    "RESOURCE_EXHAUSTED": "đã vượt hạn mức của free tier",
    "NOT_FOUND": "tên mô hình không tồn tại",
    "INVALID_ARGUMENT": "yêu cầu không hợp lệ",
    "FAILED_PRECONDITION": "tài khoản/khu vực chưa được cấp quyền dùng API",
    "UNAVAILABLE": "dịch vụ Google đang gián đoạn",
}


class GeminiProvider:
    """Client giao tiếp với Google Gemini API qua giao thức REST HTTP (không phụ thuộc SDK nặng)."""
    
    DEFAULT_MODEL = "gemini-3.6-flash"
    # Key API tạo từ 2026 không còn gọi được dòng gemini-2.5-* (Google trả 404
    # "no longer available to new users"). Hai model dưới đây đã kiểm chứng trực tiếp.
    FALLBACK_MODEL = "gemini-3.5-flash-lite"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _extract_text(body: Dict[str, Any]) -> tuple:
        """Trả (text, finish_reason). Text nằm ở nhiều part nên phải nối hết."""
        candidates = body.get("candidates", [])
        if not candidates:
            return "", body.get("promptFeedback", {}).get("blockReason", "không có candidate")
        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", []) or []
        text = "".join(p.get("text", "") for p in parts).strip()
        return text, candidate.get("finishReason", "")

    @staticmethod
    def _describe_http_error(response) -> str:
        """Mô tả ngắn gọn từ mã trạng thái + status chuẩn của Google, không lộ chi tiết thô."""
        status = ""
        try:
            status = str(response.json().get("error", {}).get("status", ""))
        except Exception:
            pass
        hint = GEMINI_STATUS_HINTS.get(status, "")
        label = f"HTTP {response.status_code}"
        if status:
            label += f" {status}"
        return f"{label} ({hint})" if hint else label

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.4) -> str:
        """Gửi yêu cầu sinh văn bản tới Gemini API; thử lần lượt model chính rồi model dự phòng."""
        if not self.is_configured():
            raise GeminiNotConfiguredError("chưa cấu hình GEMINI_API_KEY.")

        reasons = []
        for model_name in (self.DEFAULT_MODEL, self.FALLBACK_MODEL):
            # API key đặt trong header x-goog-api-key để không lộ trong URL/log.
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}

            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": temperature,
                    # maxOutputTokens tính cả token "suy nghĩ" của dòng Gemini 2.5:
                    # đặt hẹp là mô hình trả về parts rỗng và báo cáo mất hút.
                    "maxOutputTokens": 8192
                }
            }

            if system_prompt:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_prompt}]
                }

            try:
                response = requests.post(url, json=payload, headers=headers, timeout=90)
            except requests.RequestException as e:
                reasons.append(f"{model_name}: không kết nối được Gemini API ({type(e).__name__})")
                logger.error(f"Lỗi kết nối Gemini API ({model_name}): {e}")
                continue

            if response.status_code == 200:
                text, finish = self._extract_text(response.json())
                if text:
                    return text
                reasons.append(f"{model_name}: trả về nội dung rỗng ({finish or 'không rõ'})")
                logger.warning(f"Gemini {model_name} trả về nội dung rỗng, finishReason={finish}")
                continue

            reasons.append(f"{model_name}: {self._describe_http_error(response)}")
            logger.warning(f"Gemini API {model_name} lỗi: HTTP {response.status_code} {response.text[:300]}")

        raise GeminiAPIError("; ".join(reasons))

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

    @classmethod
    def weights_cached(cls) -> bool:
        """Trọng số GGUF đã nằm trên đĩa chưa. Health dùng cái này thay vì nạp model thật."""
        try:
            from huggingface_hub import try_to_load_from_cache
            cached = try_to_load_from_cache(settings.LLM_REPO_ID, settings.LLM_FILENAME)
        except Exception:
            return False
        return isinstance(cached, str)

    def load_model(self) -> bool:
        """Nạp GGUF. Ném LocalLLMError nêu ngắn gọn lý do để UI nói đúng bệnh."""
        if self._model is not None:
            return True

        try:
            from llama_cpp import Llama
        except ImportError as e:
            raise LocalLLMError("thiếu thư viện llama-cpp-python") from e

        logger.info("Đang nạp Local LLM Qwen2.5-7B (lần đầu sẽ tải ~4.7GB trọng số)...")
        try:
            model_path = hf_hub_download(repo_id=settings.LLM_REPO_ID, filename=settings.LLM_FILENAME)
        except Exception as e:
            raise LocalLLMError(
                "không tải được trọng số GGUF từ Hugging Face "
                f"({type(e).__name__}: kiểm tra mạng/dung lượng đĩa)"
            ) from e

        try:
            self._model = Llama(
                model_path=model_path,
                n_ctx=4096,
                n_gpu_layers=-1,
                verbose=False
            )
        except Exception as e:
            raise LocalLLMError(f"llama.cpp không nạp được mô hình ({type(e).__name__})") from e

        logger.info("Nạp Local LLM thành công.")
        return True

    def generate_response(self, prompt: str, system_instruction: str = "") -> str:
        if not self.is_loaded():
            self.load_model()
        
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
            raise LocalLLMError(f"llama.cpp lỗi khi suy luận ({type(e).__name__})") from e


class LLMFactory:
    """Factory Router hỗ trợ chuyển đổi linh hoạt giữa Gemini Cloud và Local Model."""
    
    @staticmethod
    def get_provider(provider_type: str = "gemini", api_key: Optional[str] = None):
        if provider_type.lower() == "gemini":
            return GeminiProvider(api_key=api_key)
        else:
            return LocalLLM.get_instance()
