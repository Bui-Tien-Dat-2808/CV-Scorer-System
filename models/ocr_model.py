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
            cls._instance = PaddleOCR(
                lang="en", 
                use_angle_cls=True,
                show_log=False
            )
        return cls._instance
