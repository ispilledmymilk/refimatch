from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class MarketAreaStats(BaseModel):
    area_name: str
    city: str
    state: str
    zip_code: str
    median_list_price: float = Field(gt=0)
    median_price_per_sqft: float = Field(gt=0)
    avg_days_on_market: float = Field(ge=0)
    active_listings_count: int = Field(ge=0)
    yoy_appreciation_pct: float
    months_of_inventory: float = Field(ge=0)


class SubjectProperty(BaseModel):
    property_id: str
    address: str
    city: str
    state: str
    zip_code: str
    beds: int = Field(ge=0)
    baths: float = Field(ge=0)
    sqft: int = Field(gt=0)
    year_built: int
    property_type: str = "single_family"
    lot_sqft: int | None = None
    hoa_monthly: float = Field(default=0.0, ge=0)
    condition: Literal["fair", "good", "excellent"] = "good"
    purchase_price: float = Field(gt=0)
    purchase_date: date
    estimated_value: float = Field(gt=0)
    asking_price: float | None = Field(default=None, gt=0)
    last_sale_date: date | None = None
    tax_assessed_value: float | None = Field(default=None, gt=0)
    features: list[str] = Field(default_factory=list)


class PropertyListing(BaseModel):
    listing_id: str
    address: str
    city: str
    state: str
    zip_code: str
    beds: int = Field(ge=0)
    baths: float = Field(ge=0)
    sqft: int = Field(gt=0)
    year_built: int
    property_type: str = "single_family"
    asking_price: float = Field(gt=0)
    days_on_market: int = Field(ge=0)
    status: Literal["active", "pending", "sold"] = "active"
    distance_miles: float = Field(ge=0)
    condition: Literal["fair", "good", "excellent"] = "good"
    features: list[str] = Field(default_factory=list)
    image_url: str | None = None
    same_building: bool = False
    distance_km: float | None = None

    @property
    def price_per_sqft(self) -> float:
        return self.asking_price / self.sqft


class ListingComparison(BaseModel):
    listing_id: str
    address: str
    asking_price: float
    price_per_sqft: float
    beds: int
    baths: float
    sqft: int
    days_on_market: int
    distance_miles: float
    condition: str
    vs_subject_price_delta: float
    vs_subject_price_pct: float
    vs_subject_sqft_delta: int
    vs_subject_ppsf_delta: float


class AppreciationMetrics(BaseModel):
    purchase_price: float
    estimated_value: float
    asking_price: float | None
    appreciation_dollars: float
    appreciation_pct: float
    annualized_appreciation_pct: float
    years_held: float
    yoy_area_appreciation_pct: float
    vs_area_median_value_delta: float
    vs_area_median_value_pct: float


class EquityMetrics(BaseModel):
    estimated_value: float
    loan_balance: float
    equity_dollars: float
    ltv_pct: float
    equity_gain_since_purchase: float


class MarketAnalysisRequest(BaseModel):
    subject: SubjectProperty
    listings: list[PropertyListing] = Field(min_length=1)
    market: MarketAreaStats
    loan_balance: float | None = Field(default=None, ge=0)
    original_loan_at_purchase: float | None = Field(default=None, ge=0)
    as_of_date: date | None = None


class MarketAnalysisResult(BaseModel):
    subject: SubjectProperty
    market: MarketAreaStats
    appreciation: AppreciationMetrics
    equity: EquityMetrics | None
    subject_price_per_sqft: float
    listing_comparisons: list[ListingComparison]
    ranked_listing_ids_by_price: list[str]
    ranked_listing_ids_by_ppsf: list[str]
    summary: dict[str, Any]


def _years_between(start: date, end: date) -> float:
    return max((end - start).days / 365.25, 1 / 365.25)


def _annualized_return(start_value: float, end_value: float, years: float) -> float:
    if start_value <= 0 or years <= 0:
        return 0.0
    return (end_value / start_value) ** (1.0 / years) - 1.0


def analyze_market(req: MarketAnalysisRequest) -> MarketAnalysisResult:
    as_of = req.as_of_date or date.today()
    subject = req.subject
    years_held = _years_between(subject.purchase_date, as_of)

    appreciation_dollars = subject.estimated_value - subject.purchase_price
    appreciation_pct = appreciation_dollars / subject.purchase_price
    annualized = _annualized_return(subject.purchase_price, subject.estimated_value, years_held)
    subject_ppsf = subject.estimated_value / subject.sqft
    vs_median_delta = subject.estimated_value - req.market.median_list_price
    vs_median_pct = vs_median_delta / req.market.median_list_price

    appreciation = AppreciationMetrics(
        purchase_price=subject.purchase_price,
        estimated_value=subject.estimated_value,
        asking_price=subject.asking_price,
        appreciation_dollars=appreciation_dollars,
        appreciation_pct=appreciation_pct,
        annualized_appreciation_pct=annualized,
        years_held=years_held,
        yoy_area_appreciation_pct=req.market.yoy_appreciation_pct,
        vs_area_median_value_delta=vs_median_delta,
        vs_area_median_value_pct=vs_median_pct,
    )

    equity: EquityMetrics | None = None
    if req.loan_balance is not None:
        equity_dollars = subject.estimated_value - req.loan_balance
        original_loan = req.original_loan_at_purchase or subject.purchase_price * 0.8235
        equity_at_purchase = subject.purchase_price - original_loan
        equity = EquityMetrics(
            estimated_value=subject.estimated_value,
            loan_balance=req.loan_balance,
            equity_dollars=equity_dollars,
            ltv_pct=req.loan_balance / subject.estimated_value,
            equity_gain_since_purchase=equity_dollars - equity_at_purchase,
        )

    comparisons: list[ListingComparison] = []
    for listing in req.listings:
        ppsf = listing.price_per_sqft
        price_delta = listing.asking_price - subject.estimated_value
        comparisons.append(
            ListingComparison(
                listing_id=listing.listing_id,
                address=listing.address,
                asking_price=listing.asking_price,
                price_per_sqft=ppsf,
                beds=listing.beds,
                baths=listing.baths,
                sqft=listing.sqft,
                days_on_market=listing.days_on_market,
                distance_miles=listing.distance_miles,
                condition=listing.condition,
                vs_subject_price_delta=price_delta,
                vs_subject_price_pct=price_delta / subject.estimated_value,
                vs_subject_sqft_delta=listing.sqft - subject.sqft,
                vs_subject_ppsf_delta=ppsf - subject_ppsf,
            )
        )

    by_price = sorted(comparisons, key=lambda c: c.asking_price)
    by_ppsf = sorted(comparisons, key=lambda c: c.price_per_sqft)

    cheaper_count = sum(1 for c in comparisons if c.asking_price < subject.estimated_value)
    subject_rank_price = cheaper_count + 1

    summary = {
        "headline": (
            f"Home appreciated {appreciation_pct * 100:.1f}% "
            f"(+${appreciation_dollars:,.0f} since purchase)"
            if appreciation_dollars >= 0
            else f"Home value change: ${appreciation_dollars:,.0f} since purchase"
        ),
        "subject_rank_by_price": f"{subject_rank_price} of {len(comparisons) + 1} (including your home)",
        "cheaper_listings_nearby": cheaper_count,
        "subject_vs_median_listing": (
            f"{abs(vs_median_pct) * 100:.1f}% {'above' if vs_median_pct >= 0 else 'below'} area median"
        ),
        "subject_price_per_sqft": round(subject_ppsf, 2),
        "area_median_price_per_sqft": req.market.median_price_per_sqft,
        "avg_comp_days_on_market": round(
            sum(c.days_on_market for c in comparisons) / len(comparisons), 1
        ),
    }
    if subject.asking_price:
        ask_vs_estimate = subject.asking_price - subject.estimated_value
        summary["asking_vs_estimate"] = (
            f"Asking {subject.asking_price:,.0f} is {ask_vs_estimate:+,.0f} vs estimate"
        )
    if equity:
        summary["equity_headline"] = (
            f"Estimated equity {equity.equity_dollars:,.0f} (LTV {equity.ltv_pct * 100:.1f}%)"
        )

    return MarketAnalysisResult(
        subject=subject,
        market=req.market,
        appreciation=appreciation,
        equity=equity,
        subject_price_per_sqft=subject_ppsf,
        listing_comparisons=comparisons,
        ranked_listing_ids_by_price=[c.listing_id for c in by_price],
        ranked_listing_ids_by_ppsf=[c.listing_id for c in by_ppsf],
        summary=summary,
    )
