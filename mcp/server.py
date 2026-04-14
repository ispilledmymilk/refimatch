from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "scoring" / "src"))

from scoring.engine import compare_offers  # noqa: E402
from scoring.models import CompareRequest  # noqa: E402

mcp = FastMCP("refimatch")


def _catalog_path() -> Path:
    override = os.environ.get("REFIMATCH_CATALOG_PATH")
    if override:
        return Path(override)
    return ROOT / "services" / "api" / "data" / "demo_offers.json"


@mcp.tool()
def list_demo_offers() -> str:
    """Return the curated demo lender catalog JSON."""
    return _catalog_path().read_text(encoding="utf-8")


@mcp.tool()
def compare_mortgages(compare_request_json: str) -> str:
    """
    Run deterministic refinance comparison. Argument must be JSON matching CompareRequest:
    scenario, offers[], optional weights.
    """
    req = CompareRequest.model_validate_json(compare_request_json)
    result = compare_offers(req)
    return result.model_dump_json()


@mcp.tool()
def explain_stub(compare_result_json: str) -> str:
    """Placeholder: full explanation runs in the API LangGraph service."""
    payload = json.loads(compare_result_json)
    top = (payload.get("ranked_lender_ids") or [None])[0]
    return json.dumps(
        {
            "note": "Use POST /v1/explain on the RefiMatch API for LangGraph+RAG explanations.",
            "top_lender_id": top,
        }
    )


if __name__ == "__main__":
    mcp.run()
