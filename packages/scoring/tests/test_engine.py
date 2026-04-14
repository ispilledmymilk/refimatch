from datetime import date

import pytest
from scoring.engine import (
    amortization_schedule,
    compare_offers,
    monthly_pi,
    remaining_balance,
    scenario_from_purchase,
)
from scoring.models import CompareRequest, DemoOffer, LoanScenario, RankingWeights


def test_remaining_balance_monotonic():
    bal = remaining_balance(400_000, 0.07, 360, 0)
    assert bal == pytest.approx(400_000)
    bal60 = remaining_balance(400_000, 0.07, 360, 60)
    assert bal60 < bal


def test_monthly_pi_reasonable():
    p = monthly_pi(300_000, 0.065, 360)
    assert 1800 < p < 2200


def test_amortization_pays_down():
    df = amortization_schedule(100_000, 0.06, 360, max_months=12)
    assert df.iloc[0]["balance"] < 100_000
    assert df.iloc[-1]["balance"] < df.iloc[0]["balance"]


def test_compare_ranks():
    scenario = LoanScenario(
        original_principal=350_000,
        annual_rate=0.07,
        term_months=360,
        months_paid=48,
        hold_horizon_months=60,
    )
    offers = [
        DemoOffer(
            lender_id="a",
            lender_name="High rate",
            apr=0.069,
            points=0,
            lender_fees=2000,
            term_months=360,
        ),
        DemoOffer(
            lender_id="b",
            lender_name="Lower rate",
            apr=0.059,
            points=0.005,
            lender_fees=3500,
            term_months=360,
        ),
    ]
    req = CompareRequest(scenario=scenario, offers=offers, weights=RankingWeights())
    res = compare_offers(req)
    assert set(res.ranked_lender_ids) == {"a", "b"}
    assert res.metrics_by_lender["b"].new_monthly_pi < res.metrics_by_lender["a"].new_monthly_pi


def test_scenario_from_purchase():
    s = scenario_from_purchase(300_000, 0.065, 360, date(2020, 1, 1), as_of=date(2024, 1, 1))
    assert s.months_paid == 48
