from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from scoring.models import DemoOffer


@lru_cache
def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "demo_offers.json"


def load_demo_offers() -> list[DemoOffer]:
    raw = json.loads(_catalog_path().read_text(encoding="utf-8"))
    return [DemoOffer.model_validate(o) for o in raw["offers"]]
