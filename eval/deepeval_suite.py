from __future__ import annotations

import os

import pytest

os.environ.setdefault("REFIMATCH_LLM_MOCK", "1")


def test_explain_graph_returns_text():
    from refimatch_agent.graph import run_explain_graph

    out = run_explain_graph({"ranked_lender_ids": ["a", "b"], "baseline_monthly_pi": 2000.0})
    assert isinstance(out["explanation"], str)
    assert len(out["explanation"]) > 0


@pytest.mark.skipif(
    os.environ.get("DEEPEVAL_LLM_TEST", "").lower() not in ("1", "true", "yes"),
    reason="Set DEEPEVAL_LLM_TEST=1 and OPENAI_API_KEY to run optional LLM assertions.",
)
def test_optional_deepeval_answer_relevancy():
    from deepeval import assert_test
    from deepeval.metrics import AnswerRelevancyMetric
    from deepeval.test_case import LLMTestCase
    from refimatch_agent.graph import run_explain_graph

    payload = {"ranked_lender_ids": ["demo-aurora"], "baseline_monthly_pi": 2100.0}
    out = run_explain_graph(payload)
    metric = AnswerRelevancyMetric(threshold=0.2)
    test_case = LLMTestCase(
        input="Explain the ranking briefly.",
        actual_output=out["explanation"],
        retrieval_context=[c["text"] for c in out.get("citations", [])],
    )
    assert_test(test_case, [metric])
