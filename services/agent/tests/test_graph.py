import os

from refimatch_agent.graph import run_explain_graph


def test_explain_graph_mock_llm():
    os.environ["REFIMATCH_LLM_MOCK"] = "1"
    payload = {
        "ranked_lender_ids": ["b", "a"],
        "baseline_monthly_pi": 2200,
        "current_balance": 330000,
    }
    out = run_explain_graph(payload, user_question="Why?")
    assert "explanation" in out
    assert out["explanation"]
    assert isinstance(out["citations"], list)
