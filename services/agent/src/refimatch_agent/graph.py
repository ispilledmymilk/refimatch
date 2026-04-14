from __future__ import annotations

import json
import os
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from refimatch_agent.langfuse_util import try_build_langfuse_handler
from refimatch_agent.llm_factory import build_chat_model, build_messages
from refimatch_agent.retrieval import MemoryRetriever, PgRetriever, get_retriever


class ExplainState(TypedDict, total=False):
    compare_payload: dict[str, Any]
    user_question: str
    chunks: list[dict[str, Any]]
    explanation: str


def _retrieve(state: ExplainState, retriever: MemoryRetriever | PgRetriever) -> ExplainState:
    q = state.get("user_question") or "Why is this refinance offer ranked highest?"
    hits = retriever.search(q, k=int(os.environ.get("REFIMATCH_RAG_TOP_K", "4")))
    state["chunks"] = [{"id": h.id, "text": h.text, "score": h.score} for h in hits]
    return state


def _generate(state: ExplainState) -> ExplainState:
    model = build_chat_model()
    handler = try_build_langfuse_handler()

    system = (
        "You explain mortgage refinance comparisons. Use ONLY facts present in the JSON "
        "payload and retrieved snippets. If numbers conflict, trust the JSON payload. "
        "Keep the answer under 180 words."
    )
    payload = json.dumps(state.get("compare_payload", {}), indent=2)[:12000]
    chunks = json.dumps(state.get("chunks", []), indent=2)[:8000]
    q = state.get("user_question", "")
    user = (
        f"Question: {q}\n\n"
        f"Compare payload:\n{payload}\n\n"
        f"Retrieved snippets:\n{chunks}"
    )
    msgs = build_messages(system, user)
    if handler is not None:
        out = model.invoke(msgs, config={"callbacks": [handler]})
    else:
        out = model.invoke(msgs)
    state["explanation"] = getattr(out, "content", str(out))
    return state


def build_explain_graph(retriever: MemoryRetriever | PgRetriever | None = None) -> Any:
    r = retriever or get_retriever()

    g = StateGraph(ExplainState)
    g.add_node("retrieve", lambda s: _retrieve(dict(s), r))
    g.add_node("generate", _generate)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile()


def run_explain_graph(
    compare_payload: dict[str, Any],
    user_question: str | None = None,
    retriever: MemoryRetriever | PgRetriever | None = None,
) -> dict[str, Any]:
    app = build_explain_graph(retriever=retriever)
    final = app.invoke(
        {
            "compare_payload": compare_payload,
            "user_question": user_question or "Summarize why the top offer ranks first.",
        }
    )
    return {
        "explanation": final.get("explanation", ""),
        "citations": final.get("chunks", []),
    }
