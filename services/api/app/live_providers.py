from __future__ import annotations

import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MIRROR_MCP_URL = os.environ.get(
    "REFIMATCH_MIRROR_MCP_URL", "https://www.mirrorrealestate.com/mcp"
)
FRED_API_URL = "https://api.stlouisfed.org/fred"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
AUSTIN_HPI_SERIES = "ATNHPIUS12420Q"
NATIONAL_HPI_SERIES = "USSTHPI"  # FHFA purchase-only US house price index
MORTGAGE30_SERIES = "MORTGAGE30US"
RATEAPI_BASE = os.environ.get("REFIMATCH_RATEAPI_URL", "https://api.rateapi.dev")
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SEC = int(os.environ.get("REFIMATCH_LIVE_CACHE_TTL", "300"))

_RESIDENTIAL_TYPES = {
    "single family",
    "townhouse",
    "condo",
    "apartment",
    "multi-family",
    "farm/ranch",
}


def _cache_get(key: str) -> Any | None:
    hit = _CACHE.get(key)
    if hit is None:
        return None
    ts, val = hit
    if time.time() - ts > _CACHE_TTL_SEC:
        _CACHE.pop(key, None)
        return None
    return val


def _cache_set(key: str, val: Any) -> None:
    _CACHE[key] = (time.time(), val)


def _http_post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> str:
    body = json.dumps(payload).encode("utf-8")
    hdrs = {
        "User-Agent": "RefiMatch/0.1 (demo; +https://github.com/refimatch)",
        **headers,
    }
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def _http_get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "RefiMatch/0.1 (demo; +https://github.com/refimatch)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_sse_payload(raw: str) -> dict[str, Any]:
    for line in raw.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    raise ValueError("No SSE data payload in Mirror MCP response")


def mirror_tool_call(tool: str, arguments: dict[str, Any]) -> Any:
    cache_key = f"mirror:{tool}:{json.dumps(arguments, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    try:
        raw = _http_post_json(MIRROR_MCP_URL, payload, headers)
        envelope = _parse_sse_payload(raw)
        text = envelope["result"]["content"][0]["text"]
        parsed = json.loads(text)
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Mirror Real Estate API error: {e}") from e

    _cache_set(cache_key, parsed)
    return parsed


def slug_to_address(slug: str) -> str:
    """Turn listing slug into a readable address (US or Canada)."""
    parts = slug.split("-")
    # Canadian postal often appears as m5v-2t6 style fragments
    for i in range(len(parts) - 1):
        a, b = parts[i], parts[i + 1]
        if re.match(r"^[a-zA-Z]\d[a-zA-Z]$", a) and re.match(r"^\d[a-zA-Z]\d$", b):
            postal = f"{a.upper()} {b.upper()}"
            # province typically just before postal
            if i >= 1 and len(parts[i - 1]) == 2:
                province = parts[i - 1].upper()
                city = parts[i - 2].capitalize() if i >= 2 else ""
                street = " ".join(p.capitalize() for p in parts[: max(i - 2, 0)])
                return f"{street}, {city}, {province} {postal}".strip(", ")
            break

    for i in range(len(parts) - 1):
        part = parts[i]
        nxt = parts[i + 1]
        if len(part) == 2 and part.isalpha() and nxt.isdigit() and len(nxt) == 5:
            state = part.upper()
            zip_code = nxt
            city = parts[i - 1].capitalize() if i > 0 else ""
            street = " ".join(p.capitalize() for p in parts[: max(i - 1, 0)])
            return f"{street}, {city}, {state} {zip_code}"
    return slug.replace("-", " ").title()


def parse_sqft_from_description(description: str) -> int:
    if not description:
        return 0
    match = re.search(r"Square Feet:\s*([\d,]+)", description, re.I)
    if match:
        return int(match.group(1).replace(",", ""))
    match = re.search(r"([\d,]+)\s*sq\.?\s*ft", description, re.I)
    if match:
        return int(match.group(1).replace(",", ""))
    return 0


def _is_residential_listing(item: dict[str, Any]) -> bool:
    ptype = str(item.get("propertyType", "")).lower()
    beds = int(item.get("beds") or 0)
    if ptype == "other" and beds == 0:
        return False
    if beds <= 0 and ptype not in _RESIDENTIAL_TYPES:
        return False
    price = float(item.get("price") or 0)
    return price >= 50_000


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geocode_address(
    *,
    street: str,
    city: str,
    state: str,
    zip_code: str = "",
    country: str = "United States",
) -> dict[str, float] | None:
    """Geocode via OpenStreetMap Nominatim (free, no key).

    Returns {"lat", "lon", "precision"} where precision is 1.0 (street) or 0.0 (city).
    """
    country_code = "ca" if detect_country(state=state, zip_code=zip_code, country=country) == "Canada" else "us"
    cache_key = f"geo2:{street}|{city}|{state}|{zip_code}|{country_code}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    attempts: list[tuple[float, dict[str, str]]] = []
    if street:
        attempts.append(
            (
                1.0,
                {
                    "street": street,
                    "city": city,
                    "state": state,
                    "postalcode": zip_code,
                    "country": country,
                    "format": "json",
                    "limit": "1",
                    "countrycodes": country_code,
                },
            )
        )
        attempts.append(
            (
                1.0,
                {
                    "q": ", ".join(x for x in [street, city, state, zip_code, country] if x),
                    "format": "json",
                    "limit": "1",
                    "countrycodes": country_code,
                },
            )
        )
    attempts.append(
        (
            0.0,
            {
                "q": ", ".join(x for x in [city, state, zip_code, country] if x),
                "format": "json",
                "limit": "1",
                "countrycodes": country_code,
            },
        )
    )

    out: dict[str, float] | None = None
    for precision, params in attempts:
        url = f"https://nominatim.openstreetmap.org/search?{urllib.parse.urlencode(params)}"
        try:
            text = _http_get_text(url, headers={"Accept": "application/json"})
            rows = json.loads(text)
            if not rows:
                continue
            out = {
                "lat": float(rows[0]["lat"]),
                "lon": float(rows[0]["lon"]),
                "precision": precision,
            }
            # Prefer street-level; skip city fallback when street was requested.
            if precision >= 1.0 or not street:
                break
            # Keep city result only as last resort (loop continues only if street attempts failed)
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError, IndexError):
            continue

    if out is not None:
        _cache_set(cache_key, out)
    return out


def normalize_property_type(property_type: str) -> str:
    """
    Map free-form / Mirror property types onto:
      apartment | townhouse | semi_detached | detached
    """
    t = (property_type or "").lower().replace("_", " ").replace("-", " ")
    t = re.sub(r"\s+", " ", t).strip()

    if any(tok in t for tok in ("semi detached", "semidetached", "semi det")):
        return "semi_detached"
    if any(
        tok in t
        for tok in (
            "townhouse",
            "town house",
            "townhome",
            "row house",
            "rowhouse",
            "att/row",
            "att row",
        )
    ):
        return "townhouse"
    # Condo townhouse already caught above; remaining condo/apt → apartment
    if any(
        tok in t
        for tok in (
            "condo apartment",
            "apartment",
            "condo",
            "condominium",
            "apt",
            "flat",
            "common element",
            "multiplex",
            "multi family",
            "multifamily",
            "plex",
        )
    ):
        return "apartment"
    if any(tok in t for tok in ("detached", "single family", "singlefamily", "house")):
        return "detached"
    # Default: treat unknown residential as detached / house-like
    return "detached"


def listing_kind(property_type: str) -> str:
    """Backward-compatible: apartment vs house (non-apartment)."""
    return "apartment" if normalize_property_type(property_type) == "apartment" else "house"


def property_types_match(subject_type: str, listing_type: str) -> bool:
    """True when listing is the same normalized dwelling type as the subject."""
    return normalize_property_type(subject_type) == normalize_property_type(listing_type)


def building_key(address: str) -> str:
    """
    Normalize to a building identity so units in the same building match.

    Examples:
      '1001-455 Sentinel Road' / '455 Sentinel Road' -> '455 sentinel road'
      'Unit 1204, 88 Harbour St' -> '88 harbour st'
    """
    s = (address or "").lower()
    s = re.sub(r"\b(unit|apt|apartment|suite|#)\s*[\w-]+", " ", s)
    # leading condo unit patterns: "1001-455 ..." or "415 701 sheppard"
    s = re.sub(r"^\s*\d{1,4}\s*[-–]\s*", "", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    tokens = s.split()
    # Drop a leading short unit number when followed by a street number
    if len(tokens) >= 2 and tokens[0].isdigit() and tokens[1].isdigit() and len(tokens[0]) <= 4:
        tokens = tokens[1:]
    return " ".join(tokens)


def is_house_listing(item: dict[str, Any]) -> bool:
    return listing_kind(str(item.get("propertyType") or "")) == "house"


def is_apartment_listing(item: dict[str, Any]) -> bool:
    return listing_kind(str(item.get("propertyType") or "")) == "apartment"


def listing_matches_type(item: dict[str, Any], subject_type: str) -> bool:
    return property_types_match(subject_type, str(item.get("propertyType") or ""))


def search_live_listings(
    *,
    city: str,
    country: str = "United States",
    min_sale_price: int = 0,
    max_sale_price: int = 0,
    beds: int = 0,
    page_size: int = 30,
) -> dict[str, Any]:
    return mirror_tool_call(
        "search_listings",
        {
            "city": city,
            "country": country,
            "forSale": True,
            "forRent": False,
            "beds": beds,
            "minSalePrice": min_sale_price,
            "maxSalePrice": max_sale_price,
            "pageSize": min(page_size, 100),
            "pageNumber": 0,
        },
    )


def get_live_listing_detail(slug: str) -> dict[str, Any]:
    detail = mirror_tool_call("get_listing", {"slug": slug})
    if not detail:
        return {}
    sqft = int(detail.get("sqFt") or 0)
    if sqft <= 0:
        sqft = parse_sqft_from_description(str(detail.get("description", "")))
    detail["parsedSqFt"] = sqft
    if not detail.get("address"):
        detail["address"] = slug_to_address(slug)
    try:
        detail["lat"] = float(detail.get("latitude") or 0) or None
        detail["lon"] = float(detail.get("longitude") or 0) or None
    except (TypeError, ValueError):
        detail["lat"] = None
        detail["lon"] = None
    imgs = detail.get("imageUrls") or []
    detail["image_url"] = imgs[0] if imgs else None
    return detail


def _http_get_text(url: str, headers: dict[str, str] | None = None) -> str:
    hdrs = {
        "User-Agent": "RefiMatch/0.1 (demo; +https://github.com/refimatch)",
        **(headers or {}),
    }
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def fetch_fred_csv_observations(series_id: str, limit: int = 40) -> list[dict[str, Any]]:
    """Fetch FRED series via public CSV (no API key required)."""
    cache_key = f"fredcsv:{series_id}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{FRED_CSV_URL}?id={series_id}"
    try:
        text = _http_get_text(url)
    except (urllib.error.URLError, TimeoutError):
        return []

    rows: list[dict[str, Any]] = []
    for line in text.strip().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 2:
            continue
        date_s, value_s = parts[0].strip(), parts[1].strip()
        if value_s in ("", "."):
            continue
        try:
            rows.append({"date": date_s, "value": float(value_s)})
        except ValueError:
            continue

    # CSV is ascending; reverse for newest-first like API path
    rows.reverse()
    obs = rows[:limit]
    _cache_set(cache_key, obs)
    return obs


def fetch_fred_observations(series_id: str, limit: int = 24) -> list[dict[str, Any]]:
    """Prefer API key path; fall back to public CSV (no key)."""
    api_key = os.environ.get("REFIMATCH_FRED_API_KEY", "").strip()
    if api_key:
        cache_key = f"fred:{series_id}:{limit}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        params = (
            f"series_id={series_id}&api_key={api_key}&file_type=json"
            f"&sort_order=desc&limit={limit}"
        )
        url = f"{FRED_API_URL}/series/observations?{params}"
        try:
            data = _http_get_json(url)
            obs = [
                o
                for o in data.get("observations", [])
                if o.get("value") not in (None, ".", "")
            ]
            _cache_set(cache_key, obs)
            return obs
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            pass

    return fetch_fred_csv_observations(series_id, limit=limit)


def fetch_freddie_mac_30yr_rate() -> dict[str, Any] | None:
    """National average 30-year FRM from Freddie Mac PMMS via FRED (no key)."""
    obs = fetch_fred_observations(MORTGAGE30_SERIES, limit=8)
    if not obs:
        return None
    latest = obs[0]
    prior = obs[1] if len(obs) > 1 else None
    rate_pct = float(latest["value"])
    out: dict[str, Any] = {
        "series_id": MORTGAGE30_SERIES,
        "as_of": latest["date"],
        "rate_pct": rate_pct,
        "rate": rate_pct / 100.0,
        "source": "Freddie Mac PMMS via FRED (MORTGAGE30US)",
    }
    if prior:
        out["week_change_pct_points"] = rate_pct - float(prior["value"])
    return out


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "lender"


def rateapi_row_to_offer(row: dict[str, Any], *, balance_hint: float = 350_000) -> dict[str, Any] | None:
    """Map a RateAPI rate row into DemoOffer-compatible fields."""
    if str(row.get("product_type", "")).lower() != "mortgage":
        return None
    apr_pct = row.get("apr")
    if apr_pct is None:
        apr_pct = row.get("rate")
    if apr_pct is None:
        return None
    try:
        apr = float(apr_pct) / 100.0
    except (TypeError, ValueError):
        return None
    if not (0 < apr <= 0.25):
        return None

    term = int(row.get("term_months") or 360)
    # RateAPI points are discount points (0.25 = quarter point), not loan fraction.
    points_raw = float(row.get("points") or 0)
    points_frac = max(points_raw, 0.0) / 100.0

    lender = str(row.get("lender") or "Unknown Lender")
    product = str(row.get("display_name") or row.get("product_name") or "Mortgage")
    program = str(row.get("loan_program") or "conventional")
    state = str(row.get("state") or "")
    lender_id = f"rateapi-{_slugify(lender)}-{term}-{_slugify(program)}"

    # Typical CU origination/closing estimate when flat fees aren't published.
    base_fee = float(os.environ.get("REFIMATCH_DEFAULT_LENDER_FEES", "2495"))
    lender_fees = base_fee + (points_frac * balance_hint * 0.15)

    as_of = row.get("as_of") or ""
    demo_flag = bool(row.get("demo"))
    notes_bits = [
        product,
        program.upper() if program else None,
        f"{state}" if state else None,
        f"as of {as_of[:10]}" if as_of else None,
        "RateAPI demo sample" if demo_flag else "Live credit union rate (RateAPI)",
    ]
    notes = " · ".join(x for x in notes_bits if x)

    return {
        "lender_id": lender_id,
        "lender_name": lender,
        "apr": apr,
        "points": points_frac,
        "lender_fees": round(lender_fees, 2),
        "term_months": term,
        "notes": notes,
        "meta": {
            "product_name": product,
            "loan_program": program,
            "state": state,
            "rate_pct": float(row.get("rate") or apr_pct),
            "apr_pct": float(apr_pct),
            "as_of": as_of,
            "demo": demo_flag,
            "source": "rateapi",
        },
    }


def fetch_rateapi_mortgage_rates(
    *,
    state: str | None = None,
    term_months: int | None = 360,
    limit: int = 12,
) -> dict[str, Any]:
    """
    Fetch mortgage rates from RateAPI.

    - With REFIMATCH_RATEAPI_KEY: live credit-union book
    - Without key: keyless /v1/demo/rates sample (same response shape)
    """
    api_key = os.environ.get("REFIMATCH_RATEAPI_KEY", "").strip()
    state = (state or os.environ.get("REFIMATCH_RATE_STATE", "TX")).upper()
    cache_key = f"rateapi:{bool(api_key)}:{state}:{term_months}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if api_key:
        # Live query — filter mortgages for the user's state.
        q = [f"product_type=mortgage", f"state={state}", f"limit={limit}", "sort=apr_asc"]
        if term_months:
            q.append(f"term_months={term_months}")
        url = f"{RATEAPI_BASE}/v1/rates?{'&'.join(q)}"
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        try:
            text = _http_get_text(url, headers=headers)
            data = json.loads(text)
            mode = "live"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            raise RuntimeError(f"RateAPI live error: {e}") from e
    else:
        url = f"{RATEAPI_BASE}/v1/demo/rates"
        try:
            data = _http_get_json(url)
            mode = "demo"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            raise RuntimeError(f"RateAPI demo error: {e}") from e

    rates = [r for r in data.get("rates", []) if str(r.get("product_type", "")).lower() == "mortgage"]
    if mode == "live":
        if term_months:
            preferred = [r for r in rates if int(r.get("term_months") or 0) == term_months]
            rates = preferred or rates
        if state:
            in_state = [r for r in rates if str(r.get("state", "")).upper() == state]
            rates = in_state or rates
    else:
        # Demo book is small — keep all mortgages so the UI has a real comparison set.
        # Prefer 30yr first for ranking stability.
        rates = sorted(
            rates,
            key=lambda r: (0 if int(r.get("term_months") or 0) == 360 else 1, float(r.get("apr") or 99)),
        )

    rates = rates[:limit]
    out = {
        "mode": mode,
        "state": state,
        "as_of": data.get("as_of"),
        "rates": rates,
        "source": (
            "RateAPI live credit-union rates"
            if mode == "live"
            else "RateAPI keyless demo sample (set REFIMATCH_RATEAPI_KEY for live)"
        ),
        "notice": data.get("notice"),
    }
    _cache_set(cache_key, out)
    return out


def fred_hpi_at_or_before(observations: list[dict[str, Any]], target: str) -> float | None:
    """Return HPI value at or before target date YYYY-MM-DD (observations desc sorted)."""
    for obs in reversed(observations):
        if obs["date"] <= target:
            try:
                return float(obs["value"])
            except ValueError:
                continue
    return None


_CA_PROVINCES = {
    "ON", "BC", "QC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "NT", "YT", "NU",
}
_US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
    "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
    "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
    "WI","WY","DC",
}


def detect_country(*, state: str = "", zip_code: str = "", country: str = "") -> str:
    """Return 'Canada' or 'United States' from province/state, postal code, or explicit country."""
    c = (country or "").strip().lower()
    if c in ("canada", "ca", "can"):
        return "Canada"
    if c in ("united states", "usa", "us", "united states of america"):
        return "United States"
    st = (state or "").strip().upper()
    if st in _CA_PROVINCES:
        return "Canada"
    if st in _US_STATES:
        return "United States"
    z = (zip_code or "").strip().upper().replace(" ", "")
    if re.match(r"^[A-Z]\d[A-Z]\d[A-Z]\d$", z):
        return "Canada"
    if re.match(r"^\d{5}(-\d{4})?$", z):
        return "United States"
    return "United States"


def parse_address(text: str) -> dict[str, str]:
    """
    Parse a free-form US or Canadian address into street/city/state/zip.

    Examples:
      1842 Maple Ridge Dr, Austin, TX 78704
      100 King St W, Toronto, ON M5X 1A9
      Toronto, ON M5V 2T6
    """
    raw = " ".join((text or "").strip().split())
    out = {"address": raw, "city": "", "state": "", "zip_code": "", "country": ""}
    if not raw:
        return out

    # Canadian postal code
    ca_zip = re.search(r"\b([A-Za-z]\d[A-Za-z])\s?(\d[A-Za-z]\d)\b", raw)
    if ca_zip:
        out["zip_code"] = f"{ca_zip.group(1).upper()} {ca_zip.group(2).upper()}"
    else:
        us_zip = re.search(r"\b(\d{5})(?:-\d{4})?\b", raw)
        if us_zip:
            out["zip_code"] = us_zip.group(1)

    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) >= 3:
        out["address"] = parts[0]
        out["city"] = parts[1]
        tail = parts[-1]
        sm = re.search(r"\b([A-Za-z]{2})\b", tail)
        if sm:
            out["state"] = sm.group(1).upper()
    elif len(parts) == 2:
        left, right = parts[0], parts[1]
        sm = re.search(r"\b([A-Za-z]{2})\b", right)
        if sm and (detect_country(state=sm.group(1), zip_code=out["zip_code"]) == "Canada"
                   or left[0:1].isalpha() and not left[0:1].isdigit()):
            # "Toronto, ON M5V 2T6" or city-only left
            if re.match(r"^\d", left):
                out["address"] = left
                tokens = right.split()
                # unlikely
                out["city"] = left
            else:
                out["city"] = left
                out["address"] = left
            out["state"] = sm.group(1).upper()
        else:
            out["address"] = left
            tokens = right.split()
            if tokens:
                out["city"] = tokens[0].title()
            if sm:
                out["state"] = sm.group(1).upper()
    elif len(parts) == 1:
        tokens = parts[0].split()
        # strip postal / zip from end
        while tokens:
            joined = " ".join(tokens[-2:]) if len(tokens) >= 2 else tokens[-1]
            if re.match(r"^[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d$", joined.replace(" ", " ")):
                tokens = tokens[:-2] if len(tokens) >= 2 else tokens[:-1]
                continue
            if tokens[-1].isdigit() and len(tokens[-1]) == 5:
                tokens = tokens[:-1]
                continue
            break
        if tokens and len(tokens[-1]) == 2 and tokens[-1].isalpha():
            out["state"] = tokens[-1].upper()
            tokens = tokens[:-1]
        if tokens:
            if len(tokens) >= 2 and tokens[0][0].isdigit():
                out["city"] = tokens[-1]
                out["address"] = " ".join(tokens[:-1])
            else:
                out["city"] = " ".join(tokens)
                out["address"] = out["city"]

    if out["city"]:
        out["city"] = out["city"].strip().title()
    out["country"] = detect_country(state=out["state"], zip_code=out["zip_code"])
    return out


# Back-compat alias
def parse_us_address(text: str) -> dict[str, str]:
    return parse_address(text)


def hpi_series_for_location(*, city: str, state: str, country: str = "") -> tuple[str | None, str]:
    """Return (FRED series id or None, human label) for appreciation."""
    country_name = detect_country(state=state, country=country)
    if country_name == "Canada":
        # No free FRED metro HPI for Canada — comps + StatCan NHPI stub label.
        return None, "Nearby comps + Statistics Canada NHPI context (Canada)"

    city_l = (city or "").lower()
    state_u = (state or "").upper()
    if state_u == "TX" and ("austin" in city_l or "round rock" in city_l or "georgetown" in city_l):
        return AUSTIN_HPI_SERIES, "FRED / FHFA Austin-Round Rock HPI"
    return NATIONAL_HPI_SERIES, "FRED / FHFA US House Price Index"


def condition_value_multiplier(condition: str) -> float:
    c = (condition or "good").lower()
    if c == "fair":
        return 0.95
    if c == "excellent":
        return 1.04
    return 1.0


def estimate_value_from_fred_hpi(
    purchase_price: float,
    purchase_date: str,
    observations: list[dict[str, Any]],
) -> tuple[float | None, float | None]:
    """Return (estimated_value, yoy_appreciation_pct) using Austin FHFA HPI."""
    if not observations:
        return None, None
    latest_val = float(observations[0]["value"])
    purchase_val = fred_hpi_at_or_before(observations, purchase_date)
    if purchase_val is None or purchase_val <= 0:
        return None, None
    estimated = purchase_price * (latest_val / purchase_val)
    yoy = None
    if len(observations) >= 5:
        try:
            year_ago = float(observations[4]["value"])
            yoy = (latest_val / year_ago) - 1.0
        except (ValueError, IndexError):
            yoy = None
    return estimated, yoy
