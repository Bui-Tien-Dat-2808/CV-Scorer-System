from sentence_transformers import SentenceTransformer
from core.config import settings
from core.logger import logger

class EmbeddingModel:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            logger.info(f"Loading Embedding Model: {settings.EMBEDDING_MODEL_NAME}...")
            cls._instance = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        return cls._instance
