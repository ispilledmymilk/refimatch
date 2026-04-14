from __future__ import annotations

import math
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from scoring.models import CompareRequest, CompareResult, DemoOffer, LoanScenario, OfferMetrics


def _monthly_rate(annual_rate: float) -> float:
    return annual_rate / 12.0


def remaining_balance(
    original_principal: float,
    annual_rate: float,
    term_months: int,
    months_paid: int,
) -> float:
    """Standard amortizing loan remaining balance after k payments."""
    if months_paid <= 0:
        return float(original_principal)
    if months_paid >= term_months:
        return 0.0
    r = _monthly_rate(annual_rate)
    if r == 0:
        return original_principal * (1 - months_paid / term_months)
    factor = (1 + r) ** term_months
    paid_factor = (1 + r) ** months_paid
    return float(original_principal * (factor - paid_factor) / (factor - 1))


def monthly_pi(principal: float, annual_rate: float, term_months: int) -> float:
    r = _monthly_rate(annual_rate)
    if term_months <= 0:
        return 0.0
    if r == 0:
        return float(principal / term_months)
    factor = (1 + r) ** term_months
    return float(principal * r * factor / (factor - 1))


def amortization_schedule(
    principal: float,
    annual_rate: float,
    term_months: int,
    max_months: int | None = None,
) -> pd.DataFrame:
    """Return month-by-month balance, interest, principal."""
    r = _monthly_rate(annual_rate)
    pay = monthly_pi(principal, annual_rate, term_months)
    n = term_months if max_months is None else min(term_months, max_months)
    rows = []
    bal = float(principal)
    for m in range(1, n + 1):
        if bal <= 0:
            break
        interest = bal * r
        principal_paid = min(pay - interest, bal)
        bal = max(bal - principal_paid, 0.0)
        rows.append(
            {
                "month": m,
                "payment": pay,
                "interest": interest,
                "principal": principal_paid,
                "balance": bal,
            }
        )
    return pd.DataFrame(rows)


def total_paid_over_horizon(
    principal: float,
    annual_rate: float,
    term_months: int,
    horizon_months: int,
) -> float:
    df = amortization_schedule(principal, annual_rate, term_months, max_months=horizon_months)
    if df.empty:
        return 0.0
    return float(df["payment"].sum())


def _closing_costs(balance: float, offer: DemoOffer) -> float:
    return float(offer.lender_fees + offer.points * balance)


def _breakeven_months(
    old_payment: float,
    new_payment: float,
    closing_costs: float,
) -> float | None:
    savings = old_payment - new_payment
    if savings <= 0 or closing_costs <= 0:
        return None if savings <= 0 else 0.0
    return float(closing_costs / savings)


def _score_vector(
    payments: np.ndarray,
    totals: np.ndarray,
    breakevens: np.ndarray,
    weights: tuple[float, float, float],
) -> np.ndarray:
    """Lower is better for each metric; convert to higher score."""

    def norm_inv(x: np.ndarray) -> np.ndarray:
        finite = np.isfinite(x)
        if not finite.any():
            return np.zeros_like(x)
        xmin = float(np.nanmin(x[finite]))
        xmax = float(np.nanmax(x[finite]))
        if math.isclose(xmin, xmax):
            return np.where(finite, 1.0, 0.0)
        rng = xmax - xmin
        inv = (xmax - x) / rng
        inv = np.clip(inv, 0.0, 1.0)
        inv = np.where(finite, inv, 0.0)
        return inv

    pay_s = norm_inv(payments)
    tot_s = norm_inv(totals)
    # breakeven: lower months is better; NaN breakeven -> worst
    finite_be = breakevens[np.isfinite(breakevens)]
    worst = float(np.nanmax(finite_be)) * 2 if finite_be.size else 9999.0
    be_clean = np.where(np.isfinite(breakevens), breakevens, worst)
    be_s = norm_inv(be_clean)
    w_pay, w_tot, w_be = weights
    return w_pay * pay_s + w_tot * tot_s + w_be * be_s


def compare_offers(req: CompareRequest) -> CompareResult:
    s = req.scenario
    balance = remaining_balance(
        s.original_principal,
        s.annual_rate,
        s.term_months,
        s.months_paid,
    )
    baseline_pi = monthly_pi(balance, s.annual_rate, max(1, s.term_months - s.months_paid))

    metrics: dict[str, OfferMetrics] = {}
    payments: list[float] = []
    totals: list[float] = []
    breakevens: list[float] = []

    raw_offers: list[dict[str, Any]] = []

    for off in req.offers:
        new_pi = monthly_pi(balance, off.apr, off.term_months)
        closing = _closing_costs(balance, off)
        be = _breakeven_months(baseline_pi, new_pi, closing)
        horizon_total = total_paid_over_horizon(
            balance,
            off.apr,
            off.term_months,
            s.hold_horizon_months,
        )
        horizon_total += closing

        # naive effective APR: solve not needed for ranking; use note APR as proxy label
        eff = off.apr

        m = OfferMetrics(
            lender_id=off.lender_id,
            new_monthly_pi=new_pi,
            closing_costs=closing,
            breakeven_months=be,
            total_cost_horizon=horizon_total,
            effective_apr=eff,
        )
        metrics[off.lender_id] = m
        payments.append(new_pi)
        totals.append(horizon_total)
        breakevens.append(be if be is not None else float("nan"))

        preview_months = min(12, off.term_months)
        sched_head = amortization_schedule(
            balance,
            off.apr,
            off.term_months,
            max_months=preview_months,
        )
        raw_offers.append(
            {
                "lender_id": off.lender_id,
                "lender_name": off.lender_name,
                "apr": off.apr,
                "new_monthly_pi": new_pi,
                "closing_costs": closing,
                "breakeven_months": be,
                "total_cost_horizon": horizon_total,
                "schedule_preview": sched_head.to_dict(orient="records"),
            }
        )

    pay_arr = np.array(payments, dtype=float)
    tot_arr = np.array(totals, dtype=float)
    be_arr = np.array(breakevens, dtype=float)
    w = req.weights
    scores = _score_vector(
        pay_arr,
        tot_arr,
        be_arr,
        (w.monthly_payment, w.total_cost_horizon, w.breakeven_months),
    )
    order = list(np.argsort(-scores))
    ranked = [req.offers[i].lender_id for i in order]

    raw_table = {
        "scenario": s.model_dump(mode="json"),
        "baseline_monthly_pi": baseline_pi,
        "current_balance": balance,
        "offers": raw_offers,
        "weights": w.model_dump(),
        "composite_scores": {
            req.offers[i].lender_id: float(scores[i]) for i in range(len(req.offers))
        },
    }

    return CompareResult(
        ranked_lender_ids=ranked,
        metrics_by_lender=metrics,
        baseline_monthly_pi=baseline_pi,
        current_balance=balance,
        raw_table=raw_table,
    )


def scenario_from_purchase(
    original_principal: float,
    annual_rate: float,
    term_months: int,
    purchase_date: date,
    as_of: date | None = None,
) -> LoanScenario:
    as_of = as_of or date.today()
    months = (as_of.year - purchase_date.year) * 12 + (as_of.month - purchase_date.month)
    months = max(0, min(months, term_months))
    return LoanScenario(
        original_principal=original_principal,
        annual_rate=annual_rate,
        term_months=term_months,
        months_paid=months,
        house_purchase_date=purchase_date,
        as_of_date=as_of,
    )
