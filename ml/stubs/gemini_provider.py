from __future__ import annotations

from typing import Any

# Optional provider hook for Gemini / Google ADK-style integrations.
# Wire this behind the same interface as `langchain_openai.ChatOpenAI` when you
# standardize on Google models (set `GOOGLE_API_KEY` / Vertex env vars).


def build_gemini_chat_model(model: str | None = None) -> Any:
    raise NotImplementedError(
        "Install google-genai (or your chosen SDK) and implement build_gemini_chat_model()."
    )
