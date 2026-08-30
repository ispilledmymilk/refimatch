from __future__ import annotations

import json
import statistics
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from scoring.market import MarketAreaStats, PropertyListing, SubjectProperty

from app.live_providers import (
    building_key,
    condition_value_multiplier,
    detect_country,
    estimate_value_from_fred_hpi,
    fetch_fred_observations,
    geocode_address,
    get_live_listing_detail,
    haversine_km,
    hpi_series_for_location,
    listing_matches_type,
    normalize_property_type,
    parse_address,
    search_live_listings,
    slug_to_address,
)

LIVE_SOURCES = {
    "listings": "Mirror Real Estate (mirrorrealestate.com)",
}

# House comps: search within this radius of the subject address.
HOUSE_RADIUS_KM = 5.0
# Apartment comps: same building always + nearby units within this radius.
APT_NEARBY_RADIUS_KM = 5.0


@lru_cache
def _market_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "demo_market.json"


def load_market_config() -> dict[str, Any]:
    return json.loads(_market_config_path().read_text(encoding="utf-8"))


def default_subject() -> SubjectProperty:
    return SubjectProperty.model_validate(load_market_config()["subject_property"])


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _build_listing(
    item: dict[str, Any],
    detail: dict[str, Any] | None,
    *,
    default_city: str,
    default_state: str,
    default_zip: str,
    distance_km: float | None = None,
    same_building: bool = False,
) -> PropertyListing | None:
    slug = str(item.get("slug") or "")
    price = float(item.get("price") or 0)
    beds = int(item.get("beds") or 0)
    if price <= 0 or beds <= 0:
        return None

    baths = float(item.get("baths") or 0)
    sqft = int((detail or {}).get("parsedSqFt") or 0)
    if sqft <= 0:
        sqft = max(beds * 450, 1200)

    address = str((detail or {}).get("address") or slug_to_address(slug))
    parsed = parse_address(address)
    ptype_raw = str(item.get("propertyType") or "single_family")
    ptype = normalize_property_type(ptype_raw)
    year = 0
    yb = (detail or {}).get("yearBuilt")
    if yb and str(yb).isdigit():
        year = int(yb)
    if year <= 0:
        year = 2005

    zip_code = parsed.get("zip_code") or default_zip
    if address.split() and address.split()[-1].isdigit():
        zip_code = address.split()[-1]

    features = [ptype_raw]
    if same_building:
        features.append("Same building")
    if distance_km is not None:
        features.append(f"{distance_km:.1f} km away")

    miles = (distance_km * 0.621371) if distance_km is not None else 0.0
    image_url = (detail or {}).get("image_url")

    return PropertyListing(
        listing_id=slug,
        address=address,
        city=str(item.get("city") or parsed.get("city") or default_city),
        state=parsed.get("state") or default_state,
        zip_code=zip_code or default_zip,
        beds=beds,
        baths=baths,
        sqft=sqft,
        year_built=year,
        property_type=ptype,
        asking_price=price,
        days_on_market=0,
        status="active",
        distance_miles=round(miles, 2),
        condition="good",
        features=features,
        image_url=image_url,
        same_building=same_building,
        distance_km=round(distance_km, 2) if distance_km is not None else None,
    )


def merge_subject_overrides(
    base: SubjectProperty,
    overrides: dict[str, Any] | None,
) -> SubjectProperty:
    """Apply user-entered fields; parse free-form address into city/state/zip."""
    if not overrides:
        return base

    data = base.model_dump(mode="json")
    for key, value in overrides.items():
        if value is None or value == "":
            continue
        if key in data or key in SubjectProperty.model_fields:
            data[key] = value

    # Prefer structured address parse when street/city provided together
    street = str(data.get("address") or "")
    if overrides.get("address") and (
        "," in street or (not overrides.get("city") and not data.get("city"))
    ):
        parsed = parse_address(street)
        if parsed.get("address"):
            data["address"] = parsed["address"]
        if parsed.get("city") and not overrides.get("city"):
            data["city"] = parsed["city"]
        if parsed.get("state") and not overrides.get("state"):
            data["state"] = parsed["state"]
        if parsed.get("zip_code") and not overrides.get("zip_code"):
            data["zip_code"] = parsed["zip_code"]
        if parsed.get("country") and not overrides.get("country"):
            # country is not on SubjectProperty model — handled at lookup time
            pass

    if not data.get("property_id"):
        data["property_id"] = "user-home"

    # Never trust client-supplied estimates — seed from purchase price until comps/HPI run.
    if data.get("purchase_price"):
        data["estimated_value"] = float(data["purchase_price"])
    elif not data.get("estimated_value"):
        data["estimated_value"] = 1.0

    if data.get("property_type"):
        data["property_type"] = normalize_property_type(str(data["property_type"]))

    return SubjectProperty.model_validate(data)


def _load_static_fallback(subject: SubjectProperty | None = None) -> dict[str, Any]:
    cfg = load_market_config()
    market = MarketAreaStats.model_validate(cfg["market"])
    subj = subject or SubjectProperty.model_validate(cfg["subject_property"])
    kind = normalize_property_type(subj.property_type)
    subj = subj.model_copy(update={"property_type": kind})
    # Retarget market labels to the user's city when provided
    market = market.model_copy(
        update={
            "area_name": f"{subj.city}, {subj.state}",
            "city": subj.city,
            "state": subj.state,
            "zip_code": subj.zip_code,
        }
    )
    listings = [
        PropertyListing.model_validate(x) for x in cfg.get("listings_fallback", [])
    ]
    typed = [
        l.model_copy(update={"property_type": normalize_property_type(l.property_type)})
        for l in listings
        if normalize_property_type(l.property_type) == kind
    ]
    listings = typed
    return {
        "market": market,
        "subject_property": subj,
        "listings": listings,
        "data_sources": {
            "listings": "Bundled fallback JSON",
            "appreciation": "Configured estimate",
            "property_kind": kind,
        },
        "fetched_at": date.today().isoformat(),
    }


def load_demo_market(
    subject_overrides: dict[str, Any] | None = None,
    country: str | None = None,
) -> dict[str, Any]:
    base = default_subject()
    subject = merge_subject_overrides(base, subject_overrides)
    country_name = detect_country(
        state=subject.state,
        zip_code=subject.zip_code,
        country=country or "",
    )
    try:
        return fetch_live_market(subject=subject, country=country_name)
    except Exception as live_err:
        fallback = _load_static_fallback(subject)
        if fallback["listings"]:
            return fallback
        # Don't return wrong-type comps — surface the live error instead.
        raise RuntimeError(str(live_err)) from live_err


def fetch_live_market(
    subject: SubjectProperty | None = None,
    country: str | None = None,
) -> dict[str, Any]:
    cfg = load_market_config()
    search = cfg.get("search", {})
    subject = subject or SubjectProperty.model_validate(cfg["subject_property"])

    city = subject.city or search.get("city", "Austin")
    country = detect_country(
        state=subject.state,
        zip_code=subject.zip_code,
        country=country or "",
    )
    kind = normalize_property_type(subject.property_type)
    # Seed estimate from purchase price only — never require user-entered value.
    anchor = float(subject.purchase_price or subject.estimated_value or 400_000)
    min_price = int(max(anchor * 0.55, 50_000))
    max_price = int(anchor * 1.55)
    # Apartments: looser bed filter so same-building units still match
    if kind == "apartment":
        min_beds = 0
    else:
        min_beds = max(0, int(subject.beds) - 1) if subject.beds else int(search.get("min_beds", 3))
    page_size = int(search.get("page_size", 50))
    detail_limit = int(search.get("detail_limit", 12))

    geo = geocode_address(
        street=subject.address,
        city=subject.city,
        state=subject.state,
        zip_code=subject.zip_code,
        country=country,
    )
    # City-level Nominatim hits are too coarse for a 5 km radius filter.
    if geo is not None and float(geo.get("precision", 1.0)) < 1.0:
        geo = None
    subject_bkey = building_key(subject.address)
    street_geocoded = geo is not None

    raw = search_live_listings(
        city=city,
        country=country,
        min_sale_price=min_price,
        max_sale_price=max_price,
        beds=min_beds,
        page_size=page_size,
    )
    candidates = [x for x in raw.get("listings", []) if _is_residential(x)]

    typed = [c for c in candidates if listing_matches_type(c, kind)]
    # Always keep the user's dwelling type — never mix detached into apartment comps, etc.
    candidates = typed

    candidates.sort(
        key=lambda x: (
            abs(int(x.get("beds") or 0) - subject.beds),
            abs(float(x.get("price") or 0) - anchor),
        )
    )

    if not candidates:
        # Widen price/beds once, still same type only.
        raw = search_live_listings(
            city=city,
            country=country,
            min_sale_price=int(max(anchor * 0.35, 50_000)),
            max_sale_price=int(anchor * 2.0),
            beds=0,
            page_size=max(page_size, 80),
        )
        candidates = [
            x
            for x in raw.get("listings", [])
            if _is_residential(x) and listing_matches_type(x, kind)
        ]
        candidates.sort(
            key=lambda x: (
                abs(int(x.get("beds") or 0) - subject.beds),
                abs(float(x.get("price") or 0) - anchor),
            )
        )

    if not candidates:
        raise RuntimeError(
            f"No live {kind.replace('_', ' ')} listings found in {city}. "
            "Try another city or property type."
        )

    # Pull details first so we can resolve subject coords + apply geo / building filters.
    inspect_n = min(len(candidates), max(detail_limit * 3, 24))
    detailed: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for item in candidates[:inspect_n]:
        slug = str(item.get("slug") or "")
        try:
            detail = get_live_listing_detail(slug)
        except RuntimeError:
            detail = {}
        detailed.append((item, detail or {}))

    # Demo / new-build streets often miss OSM — borrow coords from a same-zip listing.
    if geo is None:
        zip_hint = (subject.zip_code or "").strip()
        for _item, detail in detailed:
            lat, lon = detail.get("lat"), detail.get("lon")
            if lat is None or lon is None:
                continue
            addr = str(detail.get("address") or "")
            if zip_hint and zip_hint in addr:
                geo = {"lat": float(lat), "lon": float(lon)}
                street_geocoded = False
                break
        if geo is None:
            for _item, detail in detailed:
                lat, lon = detail.get("lat"), detail.get("lon")
                if lat is not None and lon is not None:
                    geo = {"lat": float(lat), "lon": float(lon)}
                    street_geocoded = False
                    break

    scored: list[tuple[float, float, PropertyListing]] = []

    def _score_candidates(*, enforce_radius: bool) -> list[tuple[float, float, PropertyListing]]:
        out: list[tuple[float, float, PropertyListing]] = []
        for item, detail in detailed:
            address = str(detail.get("address") or slug_to_address(str(item.get("slug") or "")))
            same_bldg = bool(
                kind == "apartment"
                and subject_bkey
                and building_key(address) == subject_bkey
            )

            lat = detail.get("lat")
            lon = detail.get("lon")
            dist_km: float | None = None
            if geo and lat is not None and lon is not None:
                try:
                    dist_km = haversine_km(geo["lat"], geo["lon"], float(lat), float(lon))
                except (TypeError, ValueError):
                    dist_km = None

            if enforce_radius:
                if kind == "apartment":
                    if not same_bldg:
                        if dist_km is not None and dist_km > APT_NEARBY_RADIUS_KM:
                            continue
                        if dist_km is None and geo is not None:
                            continue
                else:
                    if dist_km is not None and dist_km > HOUSE_RADIUS_KM:
                        continue
                    if dist_km is None and geo is not None:
                        continue

            built = _build_listing(
                item,
                detail,
                default_city=subject.city,
                default_state=subject.state,
                default_zip=subject.zip_code,
                distance_km=dist_km,
                same_building=same_bldg,
            )
            if not built:
                continue
            rank_dist = dist_km if dist_km is not None else 999.0
            out.append((0.0 if same_bldg else 1.0, rank_dist, built))
        out.sort(key=lambda t: (t[0], t[1]))
        return out

    scored = _score_candidates(enforce_radius=True)
    radius_relaxed = False
    if not scored:
        # Same type still matters more than radius when the 5 km pool is empty.
        scored = _score_candidates(enforce_radius=False)
        radius_relaxed = bool(scored)

    listings = [t[2] for t in scored[:detail_limit]]

    if geo and kind != "apartment" and not radius_relaxed:
        within = [l for l in listings if l.distance_km is not None and l.distance_km <= HOUSE_RADIUS_KM]
        if within:
            listings = within
    if kind == "apartment" and not radius_relaxed:
        preferred = [
            l
            for l in listings
            if l.same_building
            or (l.distance_km is not None and l.distance_km <= APT_NEARBY_RADIUS_KM)
        ]
        if preferred:
            listings = preferred

    if not listings:
        raise RuntimeError(f"No live {kind.replace('_', ' ')} listings returned — try another city or type.")

    prices = [l.asking_price for l in listings]
    ppsfs = [l.price_per_sqft for l in listings if l.sqft > 0]
    median_price = _median(prices)
    median_ppsf = _median(ppsfs) if ppsfs else 0.0

    # Prefer same-building $/sqft for condo estimates when available.
    if kind == "apartment":
        bldg_ppsfs = [l.price_per_sqft for l in listings if l.same_building and l.sqft > 0]
        if bldg_ppsfs:
            median_ppsf = _median(bldg_ppsfs)

    series_id, series_label = hpi_series_for_location(
        city=subject.city, state=subject.state, country=country
    )
    est_from_hpi = None
    yoy_hpi = None
    if series_id:
        hpi_obs = fetch_fred_observations(series_id, limit=40)
        est_from_hpi, yoy_hpi = estimate_value_from_fred_hpi(
            subject.purchase_price,
            subject.purchase_date.isoformat(),
            hpi_obs,
        )
    else:
        hpi_obs = []

    # Canada (and missing HPI): lean on nearby comps $/sqft
    if est_from_hpi is None and median_ppsf > 0 and subject.sqft > 0:
        estimated_value = median_ppsf * subject.sqft
        series_label = f"Nearby comps in {city}, {country} (Mirror Real Estate)"
    else:
        estimated_value = est_from_hpi or float(subject.purchase_price)
        if median_price > 0 and subject.sqft > 0 and median_ppsf > 0:
            comps_value = median_ppsf * subject.sqft
            estimated_value = 0.7 * estimated_value + 0.3 * comps_value

    estimated_value *= condition_value_multiplier(subject.condition)
    yoy = yoy_hpi if yoy_hpi is not None else float(cfg.get("market", {}).get("yoy_appreciation_pct", 0.04))

    subject = subject.model_copy(
        update={
            "estimated_value": round(estimated_value, 2),
            "asking_price": subject.asking_price,
            "property_type": kind,
        }
    )

    radius_note = (
        f"same building + {APT_NEARBY_RADIUS_KM:g} km"
        if kind == "apartment"
        else f"{HOUSE_RADIUS_KM:g} km"
    )
    if radius_relaxed:
        radius_note = f"{kind.replace('_', ' ')} city-wide (few within {HOUSE_RADIUS_KM:g} km)"
    market = MarketAreaStats(
        area_name=f"{city}, {subject.state} ({radius_note})",
        city=city,
        state=subject.state,
        zip_code=subject.zip_code,
        median_list_price=round(median_price, 2),
        median_price_per_sqft=round(median_ppsf, 2) if median_ppsf else 1.0,
        avg_days_on_market=float(cfg.get("market", {}).get("avg_days_on_market", 26)),
        active_listings_count=int(raw.get("totalHits") or len(listings)),
        yoy_appreciation_pct=float(yoy),
        months_of_inventory=float(cfg.get("market", {}).get("months_of_inventory", 2.8)),
    )

    sources = {
        "listings": f"Mirror Real Estate ({country})",
        "appreciation": series_label,
        "country": country,
        "search_radius": radius_note,
        "property_kind": kind,
        "geocoded": bool(geo),
        "street_geocoded": street_geocoded,
        "radius_relaxed": radius_relaxed,
    }
    if hpi_obs:
        sources["appreciation"] = series_label

    return {
        "market": market,
        "subject_property": subject,
        "listings": listings,
        "data_sources": sources,
        "fetched_at": date.today().isoformat(),
        "country": country,
    }


def _is_residential(item: dict[str, Any]) -> bool:
    beds = int(item.get("beds") or 0)
    ptype = str(item.get("propertyType", "")).lower()
    if ptype == "other" and beds == 0:
        return False
    if beds <= 0:
        return False
    price = float(item.get("price") or 0)
    return price >= 50_000
