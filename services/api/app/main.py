from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from scoring.engine import compare_offers
from scoring.models import CompareRequest, CompareResult, DemoOffer, LoanScenario, RankingWeights

from app.catalog import load_demo_offers

load_dotenv()

app = FastAPI(title="RefiMatch API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("REFIMATCH_CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/catalog/demo-offers")
def demo_offers() -> dict[str, Any]:
    offers = load_demo_offers()
    return {"offers": [o.model_dump(mode="json") for o in offers]}


@app.post("/v1/compare")
def compare(req: CompareRequest) -> dict[str, Any]:
    try:
        result = compare_offers(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _serialize_compare_result(result)


def _serialize_compare_result(result: CompareResult) -> dict[str, Any]:
    metrics = {k: v.model_dump(mode="json") for k, v in result.metrics_by_lender.items()}
    return {
        "ranked_lender_ids": result.ranked_lender_ids,
        "metrics_by_lender": metrics,
        "baseline_monthly_pi": result.baseline_monthly_pi,
        "current_balance": result.current_balance,
        "raw_table": result.raw_table,
    }


class ExplainBody(BaseModel):
    compare_result: dict[str, Any]
    user_question: str | None = None


@app.post("/v1/explain")
def explain(body: ExplainBody) -> dict[str, Any]:
    try:
        from refimatch_agent.graph import run_explain_graph
    except ImportError as e:
        raise HTTPException(status_code=500, detail="agent package not installed") from e
    out = run_explain_graph(body.compare_result, user_question=body.user_question)
    return out


class CompareCatalogBody(BaseModel):
    scenario: LoanScenario
    lender_ids: list[str] = Field(min_length=1)
    weights: RankingWeights | None = None


@app.post("/v1/compare/catalog-selection")
def compare_catalog_selection(body: CompareCatalogBody) -> dict[str, Any]:
    catalog = {o.lender_id: o for o in load_demo_offers()}
    offers: list[DemoOffer] = []
    missing: list[str] = []
    for lid in body.lender_ids:
        o = catalog.get(lid)
        if o is None:
            missing.append(lid)
        else:
            offers.append(o)
    if missing:
        raise HTTPException(status_code=400, detail={"unknown_lender_ids": missing})
    req = CompareRequest(
        scenario=body.scenario,
        offers=offers,
        weights=body.weights or RankingWeights(),
    )
    return _serialize_compare_result(compare_offers(req))
