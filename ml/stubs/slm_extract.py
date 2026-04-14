from __future__ import annotations

from typing import Any

# Placeholder for a small on-server or edge model that maps free-form notes
# into structured `LoanScenario` fields (dates, balances, goals).


def extract_scenario_from_text(user_text: str) -> dict[str, Any]:
    return {
        "note": "SLM extraction not enabled; collect structured fields in the client instead.",
        "input_preview": user_text[:200],
    }
