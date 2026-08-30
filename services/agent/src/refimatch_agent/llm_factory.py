from __future__ import annotations

import os
import re
from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI


def _demo_narrative(user_text: str) -> str:
    top_id = None
    match = re.search(r'"ranked_lender_ids"\s*:\s*\[\s*"([^"]+)"', user_text)
    if match:
        top_id = match.group(1)
    baseline = re.search(r'"baseline_monthly_pi"\s*:\s*([0-9.]+)', user_text)
    baseline_str = f"${float(baseline.group(1)):,.0f}/mo" if baseline else "your current payment"

    label = (top_id or "the top offer").replace("rateapi-", "").replace("demo-", "").replace("-", " ").title()
    if top_id and "aurora" in top_id:
        label = "Aurora Community Bank"
    elif top_id and "river" in top_id:
        label = "River Valley Credit Union"
    elif top_id and "summit" in top_id:
        label = "Summit Home Lending"
    else:
        # Prefer lender_name from raw_table when present
        name_match = re.search(
            rf'"lender_id"\s*:\s*"{re.escape(top_id or "")}"[\s\S]*?"lender_name"\s*:\s*"([^"]+)"',
            user_text,
        )
        if not name_match:
            name_match = re.search(r'"lender_name"\s*:\s*"([^"]+)"', user_text)
        if name_match:
            label = name_match.group(1)

    return (
        f"{label} ranks first for your weighted goals. "
        f"Compared with a baseline near {baseline_str}, the winning offer balances "
        f"monthly payment, total cost over your horizon, and breakeven timing. "
        f"If you might move soon, weigh breakeven months more heavily; if you plan to stay, "
        f"horizon total cost matters more. (Demo narrative — numbers come from the scoring engine.)"
    )


class _FixedChat(BaseChatModel):
    """Deterministic chat model for demos and CI."""

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
        user_text = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_text = str(msg.content)
                break
        text = _demo_narrative(user_text)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def build_chat_model() -> BaseChatModel:
    if os.environ.get("REFIMATCH_LLM_MOCK", "").lower() in ("1", "true", "yes"):
        return _FixedChat()
    model = os.environ.get("REFIMATCH_CHAT_MODEL", "gpt-4o-mini")
    return cast(BaseChatModel, ChatOpenAI(model=model, temperature=0.2))


def build_messages(system: str, user: str) -> list[BaseMessage]:
    return [SystemMessage(content=system), HumanMessage(content=user)]
