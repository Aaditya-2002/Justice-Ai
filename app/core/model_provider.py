from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class ModelProvider(ABC):
    """Abstract base class for model providers."""

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        context: Optional[str] = None,
        skills: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        """Generate a response from the model.

        Args:
            prompt: The user's prompt or question.
            conversation_history: List of previous messages in the conversation.
            context: Retrieved context from RAG (optional).
            skills: List of available skills (optional).
            **kwargs: Additional provider-specific parameters.

        Returns:
            The generated response as a string.
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of the provider."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the name of the model."""
        pass


class MockModelProvider(ModelProvider):
    """A mock model provider for testing and development."""

    def __init__(self, response: str = "This is a mock response."):
        self._response = response

    async def generate_response(
        self,
        prompt: str,
        conversation_history: List[Dict[str, str]],
        context: Optional[str] = None,
        skills: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        """Return a mock response."""
        # In a real implementation, we would use the prompt, history, context, and skills.
        # For now, we return a fixed response.
        return self._response

    def get_provider_name(self) -> str:
        return "mock"

    def get_model_name(self) -> str:
        return "mock-model"


class ModelProviderFactory:
    """Factory to create model providers based on configuration."""

    @staticmethod
    def create_provider(provider_name: str, **kwargs) -> ModelProvider:
        if provider_name == "mock":
            return MockModelProvider(**kwargs)
        else:
            # In the future, we can add other providers like OpenAI, Ollama, etc.
            raise ValueError(f"Unknown provider: {provider_name}")
