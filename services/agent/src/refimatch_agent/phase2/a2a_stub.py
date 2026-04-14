from __future__ import annotations

"""
Agent-to-agent boundary sketch.

If you split "intake" and "compliance explainer" into two Deployments, expose a
small JSON-over-HTTP contract and call it from a LangGraph tool node.
"""


def compliance_agent_ping() -> dict[str, str]:
    return {"status": "not_configured"}
