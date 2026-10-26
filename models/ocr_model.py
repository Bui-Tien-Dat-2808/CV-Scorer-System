# ==============================================================================
# WINDOWS HOTFIX: Nạp PyTorch trước PaddlePaddle để tránh xung đột shm.dll
# ==============================================================================
try:
    import torch
except Exception:
    pass

import logging
import paddle
from paddleocr import PaddleOCR

try:
    from paddle.base.libpaddle import AnalysisConfig
    if not hasattr(AnalysisConfig, 'set_optimization_level'):
        AnalysisConfig.set_optimization_level = lambda self, x: None
except (ImportError, AttributeError, Exception) as e:
    logging.warning(f"Không thể áp dụng bản vá Windows cho Paddle: {e}")

class OCRModel:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            ocr_kwargs = {
                "lang": "en", 
                "use_angle_cls": True,
            }
            try:
                cls._instance = PaddleOCR(**ocr_kwargs, show_log=False)
            except (TypeError, ValueError):
                cls._instance = PaddleOCR(**ocr_kwargs)
        return cls._instance
