from __future__ import annotations

from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from .config import settings
from .tracing import apply_langsmith_env, make_run_config, parse_tags

T = TypeVar("T", bound=BaseModel)

try:
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover - optional until dependencies are installed
    ChatOpenAI = None


class LLMClient:
    def __init__(self) -> None:
        self._model = None
        self._ensure_model()

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        if ChatOpenAI is None or not settings.openai_api_key or not settings.enable_llm_enrichment:
            return
        apply_langsmith_env(
            enabled=settings.langsmith_tracing,
            api_key=settings.langsmith_api_key,
            project=settings.langsmith_project,
            endpoint=settings.langsmith_endpoint,
        )
        try:
            self._model = ChatOpenAI(
                model=settings.openai_model,
                temperature=settings.temperature,
                api_key=settings.openai_api_key,
                timeout=20,
                max_retries=0,
            ).with_config(
                make_run_config(
                    run_name="investment_pipeline.chat_openai",
                    tags=parse_tags(
                        settings.langsmith_tags,
                        "investment-pipeline",
                        "llm",
                    ),
                )
            )
        except Exception:
            self._model = None

    @property
    def available(self) -> bool:
        self._ensure_model()
        return self._model is not None

    def invoke_structured(self, prompt: str, schema: Type[T]) -> Optional[T]:
        self._ensure_model()
        if not self._model:
            return None
        try:
            structured_model = self._model.with_structured_output(schema)
            return structured_model.invoke(prompt)
        except Exception:
            return None

    def invoke_text(self, prompt: str) -> Optional[str]:
        self._ensure_model()
        if not self._model:
            return None
        try:
            response = self._model.invoke(prompt)
            return getattr(response, "content", None)
        except Exception:
            return None


llm_client = LLMClient()
