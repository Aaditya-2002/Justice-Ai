from abc import ABC, abstractmethod
from typing import List, Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    async def get_embedding(self, text: str) -> List[float]:
        import hashlib
        hash_obj = hashlib.md5(text.encode())
        hash_hex = hash_obj.hexdigest()
        random_list = []
        for i in range(0, len(hash_hex), 2):
            hex_pair = hash_hex[i:i+2]
            val = int(hex_pair, 16) / 255.0 * 2 - 1
            random_list.append(val)
        if len(random_list) < settings.EMBEDDING_DIMENSIONS:
            repeats = (settings.EMBEDDING_DIMENSIONS + len(random_list) - 1) // len(random_list)
            random_list = random_list * repeats
        return random_list[:settings.EMBEDDING_DIMENSIONS]


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model_name = settings.EMBEDDING_MODEL_NAME
            self.model = SentenceTransformer(self.model_name)
            # Get the actual embedding dimension from the model
            self.embedding_dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Initialized SentenceTransformer model: {self.model_name} with dimension {self.embedding_dimension}")
        except Exception as e:
            logger.error(f"Failed to initialize SentenceTransformer model: {e}")
            logger.info("Falling back to MockEmbeddingProvider")
            # Fallback to mock provider
            self.mock_provider = MockEmbeddingProvider()

    async def get_embedding(self, text: str) -> List[float]:
        if hasattr(self, 'mock_provider'):
            return await self.mock_provider.get_embedding(text)
        try:
            embedding = self.model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Fallback to mock provider if not already set
            if not hasattr(self, 'mock_provider'):
                self.mock_provider = MockEmbeddingProvider()
            return await self.mock_provider.get_embedding(text)