from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from scoring.engine import compare_offers
from scoring.market import MarketAnalysisRequest, analyze_market
from scoring.models import CompareRequest, CompareResult, DemoOffer, LoanScenario, RankingWeights

from app.catalog import load_demo_offers, load_offers_catalog
from app.live_providers import normalize_property_type
from app.market_catalog import load_demo_market

load_dotenv()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="RefiMatch API",
    version="0.1.0",
    description="Refinance comparison API with deterministic scoring and LangGraph explanations.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("REFIMATCH_CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_DEMO_SCENARIO = LoanScenario(
    original_principal=350_000,
    annual_rate=0.0675,
    term_months=360,
    months_paid=48,
    hold_horizon_months=60,
)


def _lender_name(lender_id: str, offers: list[DemoOffer] | None = None) -> str:
    for offer in offers or load_demo_offers():
        if offer.lender_id == lender_id:
            return offer.lender_name
    return lender_id


def _serialize_compare_result(result: CompareResult) -> dict[str, Any]:
    metrics = {k: v.model_dump(mode="json") for k, v in result.metrics_by_lender.items()}
    return {
        "ranked_lender_ids": result.ranked_lender_ids,
        "metrics_by_lender": metrics,
        "baseline_monthly_pi": result.baseline_monthly_pi,
        "current_balance": result.current_balance,
        "raw_table": result.raw_table,
    }


@app.get("/", response_class=HTMLResponse)
@app.get("/demo", response_class=HTMLResponse)
def demo_page() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "refimatch-api"}


@app.get("/v1/catalog/demo-offers")
def demo_offers(state: str | None = None, term_months: int = 360) -> dict[str, Any]:
    catalog = load_offers_catalog(state=state, term_months=term_months)
    return {
        "offers": [o.model_dump(mode="json") for o in catalog["offers"]],
        "market_benchmark": catalog.get("market_benchmark"),
        "data_sources": catalog.get("data_sources", {}),
        "fetched_at": catalog.get("fetched_at"),
        "state": catalog.get("state"),
        "mode": catalog.get("mode"),
    }


@app.get("/v1/market/mortgage-benchmark")
def mortgage_benchmark() -> dict[str, Any]:
    """Freddie Mac national 30-year average via FRED (no API key required)."""
    from app.live_providers import fetch_freddie_mac_30yr_rate

    data = fetch_freddie_mac_30yr_rate()
    if not data:
        raise HTTPException(status_code=503, detail="Freddie Mac / FRED rate unavailable")
    return data


@app.get("/v1/catalog/demo-listings")
def demo_listings() -> dict[str, Any]:
    data = load_demo_market()
    return {
        "market": data["market"].model_dump(mode="json"),
        "subject_property": data["subject_property"].model_dump(mode="json"),
        "listings": [x.model_dump(mode="json") for x in data["listings"]],
        "data_sources": data.get("data_sources", {}),
        "fetched_at": data.get("fetched_at"),
    }


class SubjectPropertyInput(BaseModel):
    """User-entered home details used for comps + appreciation."""

    property_id: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    beds: int | None = Field(default=None, ge=0)
    baths: float | None = Field(default=None, ge=0)
    sqft: int | None = Field(default=None, gt=0)
    year_built: int | None = None
    property_type: str | None = None
    lot_sqft: int | None = None
    hoa_monthly: float | None = Field(default=None, ge=0)
    condition: str | None = None
    purchase_price: float | None = Field(default=None, gt=0)
    purchase_date: str | None = None
    asking_price: float | None = Field(default=None, gt=0)
    features: list[str] | None = None


class MarketAnalyzeBody(BaseModel):
    loan_balance: float | None = Field(default=None, ge=0)
    original_loan_at_purchase: float | None = Field(default=None, ge=0)
    subject: SubjectPropertyInput | None = None
    country: str | None = None
    # Flat fields also accepted for simpler clients
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    beds: int | None = None
    baths: float | None = None
    sqft: int | None = None
    year_built: int | None = None
    property_type: str | None = None
    condition: str | None = None
    purchase_price: float | None = None
    purchase_date: str | None = None
    asking_price: float | None = None


def _subject_overrides_from_body(body: MarketAnalyzeBody | None) -> dict[str, Any] | None:
    if body is None:
        return None
    overrides: dict[str, Any] = {}
    if body.subject is not None:
        raw = body.subject.model_dump(exclude_none=True)
        raw.pop("estimated_value", None)  # computed server-side from comps / HPI
        overrides.update(raw)
    for key in (
        "address",
        "city",
        "state",
        "zip_code",
        "beds",
        "baths",
        "sqft",
        "year_built",
        "property_type",
        "condition",
        "purchase_price",
        "purchase_date",
        "asking_price",
    ):
        val = getattr(body, key, None)
        if val is not None:
            overrides[key] = val
    return overrides or None


def _country_from_body(body: MarketAnalyzeBody | None) -> str | None:
    if body is None:
        return None
    return body.country


@app.post("/v1/market/analyze")
def market_analyze(body: MarketAnalyzeBody | None = None) -> dict[str, Any]:
    overrides = _subject_overrides_from_body(body)
    data = load_demo_market(subject_overrides=overrides, country=_country_from_body(body))
    req = MarketAnalysisRequest(
        subject=data["subject_property"],
        listings=data["listings"],
        market=data["market"],
        loan_balance=body.loan_balance if body else None,
        original_loan_at_purchase=body.original_loan_at_purchase if body else None,
    )
    result = analyze_market(req)
    payload = result.model_dump(mode="json")
    payload["data_sources"] = data.get("data_sources", {})
    payload["fetched_at"] = data.get("fetched_at")
    payload["listings"] = [x.model_dump(mode="json") for x in data["listings"]]
    payload["country"] = data.get("country")
    return payload


@app.post("/v1/market/lookup")
def market_lookup(body: MarketAnalyzeBody | None = None) -> dict[str, Any]:
    """Lookup comps + compute estimated value and appreciation from address / details."""
    overrides = _subject_overrides_from_body(body)
    try:
        data = load_demo_market(subject_overrides=overrides, country=_country_from_body(body))
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if not data["listings"]:
        kind = normalize_property_type(
            (data["subject_property"].property_type if data.get("subject_property") else "")
            or (overrides or {}).get("property_type")
            or "detached"
        )
        raise HTTPException(
            status_code=404,
            detail=f"No {kind.replace('_', ' ')} comps found for this search.",
        )
    req = MarketAnalysisRequest(
        subject=data["subject_property"],
        listings=data["listings"],
        market=data["market"],
        loan_balance=body.loan_balance if body else None,
        original_loan_at_purchase=body.original_loan_at_purchase if body else None,
    )
    analysis = analyze_market(req)
    return {
        "market": data["market"].model_dump(mode="json"),
        "subject_property": data["subject_property"].model_dump(mode="json"),
        "listings": [x.model_dump(mode="json") for x in data["listings"]],
        "appreciation": analysis.appreciation.model_dump(mode="json"),
        "equity": analysis.equity.model_dump(mode="json") if analysis.equity else None,
        "summary": analysis.summary,
        "subject_price_per_sqft": analysis.subject_price_per_sqft,
        "listing_comparisons": [c.model_dump(mode="json") for c in analysis.listing_comparisons],
        "data_sources": data.get("data_sources", {}),
        "fetched_at": data.get("fetched_at"),
        "country": data.get("country"),
    }


@app.post("/v1/compare")
def compare(req: CompareRequest) -> dict[str, Any]:
    try:
        result = compare_offers(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _serialize_compare_result(result)


class ExplainBody(BaseModel):
    compare_result: dict[str, Any]
    user_question: str | None = None


@app.post("/v1/explain")
def explain(body: ExplainBody) -> dict[str, Any]:
    try:
        from refimatch_agent.graph import run_explain_graph
    except ImportError as e:
        raise HTTPException(status_code=500, detail="agent package not installed") from e
    return run_explain_graph(body.compare_result, user_question=body.user_question)


class DemoRunBody(BaseModel):
    user_question: str | None = Field(
        default="Summarize the best refinance option for a homeowner in plain language."
    )


@app.post("/v1/demo/run")
def demo_run(body: DemoRunBody | None = None) -> dict[str, Any]:
    """One-shot endpoint for live demos: compare all catalog offers + generate explanation."""
    try:
        from refimatch_agent.graph import run_explain_graph
    except ImportError as e:
        raise HTTPException(status_code=500, detail="agent package not installed") from e

    offers = load_demo_offers()
    result = compare_offers(
        CompareRequest(scenario=_DEMO_SCENARIO, offers=offers, weights=RankingWeights())
    )
    serialized = _serialize_compare_result(result)
    question = (body.user_question if body else None) or DemoRunBody().user_question
    explanation = run_explain_graph(serialized, user_question=question)
    top = serialized["ranked_lender_ids"][0] if serialized["ranked_lender_ids"] else ""
    market_data = load_demo_market()
    market_result = analyze_market(
        MarketAnalysisRequest(
            subject=market_data["subject_property"],
            listings=market_data["listings"],
            market=market_data["market"],
            loan_balance=serialized["current_balance"],
            original_loan_at_purchase=_DEMO_SCENARIO.original_principal,
        )
    )
    offers_catalog = load_offers_catalog()
    return {
        "headline": f"Best match: {_lender_name(top, offers)}",
        "scenario": _DEMO_SCENARIO.model_dump(mode="json"),
        "compare": serialized,
        "explain": explanation,
        "offers_meta": {
            "data_sources": offers_catalog.get("data_sources", {}),
            "market_benchmark": offers_catalog.get("market_benchmark"),
            "mode": offers_catalog.get("mode"),
            "fetched_at": offers_catalog.get("fetched_at"),
        },
        "market": {
            **market_result.model_dump(mode="json"),
            "data_sources": market_data.get("data_sources", {}),
            "fetched_at": market_data.get("fetched_at"),
        },
    }


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
