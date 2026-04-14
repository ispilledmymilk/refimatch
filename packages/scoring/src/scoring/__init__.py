from typing import TYPE_CHECKING, Any

__all__ = [
    "CompareRequest",
    "CompareResult",
    "DemoOffer",
    "LoanScenario",
    "RankingWeights",
    "compare_offers",
    "scenario_from_purchase",
]

if TYPE_CHECKING:
    from scoring.engine import compare_offers as compare_offers
    from scoring.engine import scenario_from_purchase as scenario_from_purchase
    from scoring.models import (
        CompareRequest,
        CompareResult,
        DemoOffer,
        LoanScenario,
        RankingWeights,
    )


def __getattr__(name: str) -> Any:
    model_names = ("CompareRequest", "CompareResult", "DemoOffer", "LoanScenario", "RankingWeights")
    if name in model_names:
        from scoring import models

        return getattr(models, name)
    if name == "compare_offers":
        from scoring.engine import compare_offers as fn

        return fn
    if name == "scenario_from_purchase":
        from scoring.engine import scenario_from_purchase as fn

        return fn
    raise AttributeError(name)
