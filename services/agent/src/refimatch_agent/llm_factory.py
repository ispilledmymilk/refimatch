from __future__ import annotations

import os
from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI


class _FixedChat(BaseChatModel):
    """Deterministic chat model for CI and local dev."""

    responses: tuple[str, ...] = (
        "Based on the scores, the top offer best matches your stated priorities. "
        "Compare breakeven months if you may move soon, and horizon total cost otherwise.",
    )

    @property
    def _llm_type(self) -> str:
        return "refimatch-fixed-chat"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        text = self.responses[0]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def build_chat_model() -> BaseChatModel:
    if os.environ.get("REFIMATCH_LLM_MOCK", "").lower() in ("1", "true", "yes"):
        return _FixedChat()
    model = os.environ.get("REFIMATCH_CHAT_MODEL", "gpt-4o-mini")
    return cast(BaseChatModel, ChatOpenAI(model=model, temperature=0.2))


def build_messages(system: str, user: str) -> list[BaseMessage]:
    return [SystemMessage(content=system), HumanMessage(content=user)]
