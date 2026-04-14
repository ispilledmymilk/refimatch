from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, model_validator


class LoanScenario(BaseModel):
    """User's current loan and goals."""

    original_principal: float = Field(gt=0, description="Original loan amount")
    annual_rate: float = Field(gt=0, le=0.25, description="Current note rate (e.g. 0.065 for 6.5%)")
    term_months: int = Field(gt=0, le=600)
    months_paid: int = Field(ge=0, description="Payments made on current loan")
    house_purchase_date: date | None = None
    as_of_date: date | None = None
    extra_monthly_payment: float = Field(default=0.0, ge=0)
    hold_horizon_months: int = Field(
        default=60,
        ge=12,
        le=360,
        description="Years to compare total cost",
    )

    @model_validator(mode="after")
    def _dates_and_term(self) -> LoanScenario:
        if self.as_of_date is None:
            object.__setattr__(self, "as_of_date", date.today())
        if self.months_paid > self.term_months:
            raise ValueError("months_paid cannot exceed term_months")
        return self


class DemoOffer(BaseModel):
    lender_id: str = Field(min_length=1)
    lender_name: str
    apr: float = Field(gt=0, le=0.25)
    points: float = Field(
        default=0.0,
        ge=0,
        description="Points as fraction of loan (e.g. 0.01 = 1 point)",
    )
    lender_fees: float = Field(default=0.0, ge=0, description="Flat fees in dollars")
    term_months: int = Field(gt=0, le=600)
    notes: str | None = None


class RankingWeights(BaseModel):
    """Higher weight = more important to minimize that objective."""

    monthly_payment: float = Field(default=0.34, ge=0, le=1)
    total_cost_horizon: float = Field(default=0.33, ge=0, le=1)
    breakeven_months: float = Field(default=0.33, ge=0, le=1)

    @model_validator(mode="after")
    def _normalize(self) -> RankingWeights:
        s = self.monthly_payment + self.total_cost_horizon + self.breakeven_months
        if s <= 0:
            raise ValueError("sum of weights must be > 0")
        object.__setattr__(self, "monthly_payment", self.monthly_payment / s)
        object.__setattr__(self, "total_cost_horizon", self.total_cost_horizon / s)
        object.__setattr__(self, "breakeven_months", self.breakeven_months / s)
        return self


class CompareRequest(BaseModel):
    scenario: LoanScenario
    offers: list[DemoOffer] = Field(min_length=1)
    weights: RankingWeights = Field(default_factory=RankingWeights)


class OfferMetrics(BaseModel):
    lender_id: str
    new_monthly_pi: float
    closing_costs: float
    breakeven_months: float | None
    total_cost_horizon: float
    effective_apr: float


class CompareResult(BaseModel):
    ranked_lender_ids: list[str]
    metrics_by_lender: dict[str, OfferMetrics]
    baseline_monthly_pi: float
    current_balance: float
    raw_table: dict[str, Any]
