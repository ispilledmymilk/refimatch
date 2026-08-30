from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from scoring.models import DemoOffer

from app.live_providers import (
    fetch_freddie_mac_30yr_rate,
    fetch_rateapi_mortgage_rates,
    rateapi_row_to_offer,
)


@lru_cache
def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "demo_offers.json"


def _load_static_offers() -> list[DemoOffer]:
    raw = json.loads(_catalog_path().read_text(encoding="utf-8"))
    return [DemoOffer.model_validate(o) for o in raw["offers"]]


def load_offers_catalog(
    *,
    state: str | None = None,
    term_months: int = 360,
    limit: int = 8,
) -> dict[str, Any]:
    """
    Load refinance offers for comparison.

    Prefer RateAPI (live with key, else keyless demo). Always attach Freddie Mac
    national average when available. Fall back to bundled JSON on failure.
    """
    state = (state or os.environ.get("REFIMATCH_RATE_STATE", "TX")).upper()
    benchmark = fetch_freddie_mac_30yr_rate()
    sources: dict[str, str] = {}
    if benchmark:
        sources["market_average"] = str(benchmark["source"])

    try:
        raw = fetch_rateapi_mortgage_rates(state=state, term_months=term_months, limit=limit)
        mapped: list[DemoOffer] = []
        extras: list[dict[str, Any]] = []
        for row in raw.get("rates", []):
            offer_dict = rateapi_row_to_offer(row)
            if not offer_dict:
                continue
            meta = offer_dict.pop("meta", {})
            offer = DemoOffer.model_validate(offer_dict)
            mapped.append(offer)
            extras.append({"lender_id": offer.lender_id, **meta})

        if not mapped:
            raise RuntimeError("RateAPI returned no mappable mortgage offers")

        # Annotate notes with vs Freddie Mac average when available.
        if benchmark:
            avg = float(benchmark["rate"])
            annotated: list[DemoOffer] = []
            for o in mapped:
                delta_bps = (o.apr - avg) * 10_000
                vs = f"{delta_bps:+.0f} bps vs Freddie Mac 30yr avg"
                note = f"{o.notes} · {vs}" if o.notes else vs
                annotated.append(o.model_copy(update={"notes": note}))
            mapped = annotated

        sources["offers"] = str(raw["source"])
        return {
            "offers": mapped,
            "offer_meta": extras,
            "market_benchmark": benchmark,
            "data_sources": sources,
            "fetched_at": date.today().isoformat(),
            "state": state,
            "mode": raw.get("mode"),
        }
    except Exception:
        offers = _load_static_offers()
        sources["offers"] = "Bundled fallback JSON"
        return {
            "offers": offers,
            "offer_meta": [],
            "market_benchmark": benchmark,
            "data_sources": sources,
            "fetched_at": date.today().isoformat(),
            "state": state,
            "mode": "fallback",
        }


def load_demo_offers() -> list[DemoOffer]:
    """Back-compat helper used by compare/demo endpoints."""
    return load_offers_catalog()["offers"]
