# RefiMatch

**RefiMatch** helps homeowners compare refinance offers with transparent math, and estimate home value using live comps and market appreciation — via a browser demo, a SwiftUI iOS app, and a FastAPI backend.

Educational / decision-support only. **Not financial, legal, or tax advice.**

---

## What it does

### 1. Refinance comparison
Given a current loan and a set of lender offers, RefiMatch:

1. Computes remaining balance and today’s monthly P&I (amortization).
2. Prices each refinance offer (new payment, closing costs, points).
3. Estimates **breakeven months** and **total cost** over a hold horizon.
4. Ranks offers with **user-weighted** priorities (lower payment vs lower total cost vs faster breakeven).
5. Optionally narrates the ranking with a **LangGraph** agent grounded in scores + RAG snippets (mock LLM works without an API key).

### 2. Comps & appreciation
On a separate web tab (and related API), the user enters an address and property details (**apartment / townhouse / semi-detached / detached**). RefiMatch:

1. Geocodes the address and pulls live listings (Mirror Real Estate).
2. Filters comps to the **same property type**.
3. Uses a **5 km** radius for houses; for apartments, **same building + nearby** units.
4. Estimates current value from comps $/sqft and (where available) FHFA HPI via FRED.
5. Returns appreciation $, %, annualized return — the user does **not** enter estimated value; the system computes it.

Supports **US and Canada** (province/postal detection; Canadian appreciation leans on comps when metro HPI isn’t available).

---

## Architecture

```
┌─────────────────┐     ┌──────────────────────────────┐
│  Web demo       │────▶│  FastAPI (services/api)      │
│  static HTML/JS │     │  /v1/compare /explain        │
└─────────────────┘     │  /v1/market/lookup|analyze   │
┌─────────────────┐     │  /v1/catalog/*  /v1/demo/run │
│  SwiftUI iOS    │────▶│                              │
└─────────────────┘     └───────────┬──────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
     packages/scoring        services/agent         Live providers
     (Pandas/NumPy)          (LangGraph + RAG)      (Mirror, FRED,
     amortization +          mock or OpenAI         RateAPI, Nominatim)
     market models
```

| Path | Role |
|------|------|
| [`ios/RefiMatch`](ios/RefiMatch) | SwiftUI client (iOS 17+) |
| [`packages/scoring`](packages/scoring) | Deterministic refinance + market math |
| [`services/api`](services/api) | HTTP API + static web demo |
| [`services/agent`](services/agent) | LangGraph explanations |
| [`rag`](rag) | Markdown corpus + vector ingestion |
| [`mcp`](mcp) | MCP stdio tools mirroring scoring/catalog |
| [`k8s`](k8s) | Kubernetes manifests |
| [`eval`](eval) | Promptfoo / DeepEval suites |

**Design principle:** ranking and dollar figures come from code you can audit. The LLM (when enabled) explains those numbers; it does not invent rates or payments.

---

## Hosted demo (recommended for presentations)

Deploy the API + web UI to **Render** (free tier) from GitHub:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ispilledmymilk/refimatch)

Or in the [Render dashboard](https://dashboard.render.com/): **New → Blueprint** → select this repo (`render.yaml`).

After deploy, open the service URL (e.g. `https://refimatch-demo.onrender.com`):

- `/` — interactive web demo (Refinance + Comps tabs)
- `/docs` — OpenAPI / Swagger
- `/health` — liveness

> Free Render instances **spin down** after idle time; the first request after a pause can take ~30–60s.

Optional env in the Render dashboard:

| Variable | Purpose |
|----------|---------|
| `REFIMATCH_RATEAPI_KEY` | Live credit-union mortgage rates ([rateapi.dev](https://api.rateapi.dev/keys)) |
| `REFIMATCH_LLM_MOCK=1` | Default — no OpenAI key needed |
| `OPENAI_API_KEY` | Real explanations when mock is off |

See also **[docs/DEMO.md](docs/DEMO.md)** for a 3-minute talk track.

---

## Local quick start

```bash
cd services/api
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e ../../packages/scoring -e ../agent -r requirements.txt
export PYTHONPATH=. REFIMATCH_LLM_MOCK=1 REFIMATCH_RAG_BACKEND=memory
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open **http://127.0.0.1:8080**.

Or: `./scripts/start-demo.sh` from the repo root (if present).

### Docker

```bash
docker build -f services/api/Dockerfile -t refimatch-api:latest .
docker run --rm -p 8080:8080 refimatch-api:latest
```

### Kubernetes

```bash
kubectl apply -k k8s/overlays/local
kubectl -n refimatch port-forward svc/refimatch-api 8080:8080
```

### iOS

1. Open `ios/RefiMatch/Package.swift` in Xcode.
2. Run on iPhone Simulator (iOS 17+).
3. Settings → API base URL `http://127.0.0.1:8080` (or your hosted URL).

---

## Key API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Web demo |
| `GET` | `/v1/catalog/demo-offers` | Lender offers (+ optional RateAPI / Freddie Mac benchmark) |
| `POST` | `/v1/compare` | Score & rank offers |
| `POST` | `/v1/explain` | LangGraph narrative |
| `POST` | `/v1/demo/run` | One-shot compare + explain |
| `POST` | `/v1/market/lookup` | Comps + estimated value + appreciation |
| `POST` | `/v1/market/analyze` | Full market analysis (optional equity / LTV) |
| `GET` | `/health` | Health check |

---

## Live data sources

| Data | Source | Notes |
|------|--------|-------|
| Listings / comps | [Mirror Real Estate](https://www.mirrorrealestate.com) MCP | No key; coverage varies by city |
| Appreciation (US) | FHFA HPI via FRED CSV | e.g. Austin metro or national |
| Appreciation (CA) | Comp $/sqft blend | No free CREA HPI in this stack |
| Geocoding | OpenStreetMap Nominatim | For 5 km radius |
| Lender rates | RateAPI demo → live with key | Falls back to bundled JSON |
| 30-yr national avg | Freddie Mac PMMS via FRED | Shown on refinance tab |

---

## Web demo UX

- **Refinance** — loan inputs, priority sliders, offer checkboxes, ranking, payment chart, AI summary.
- **Comps & Appreciation** — Zoocasa-inspired search UI; property type; estimated value and listing cards as results (not inputs).

---

## Environment reference

See [`services/api/.env.example`](services/api/.env.example).

Common flags:

```bash
export REFIMATCH_LLM_MOCK=1
export REFIMATCH_RAG_BACKEND=memory   # or pgvector + DATABASE_URL
export REFIMATCH_RATEAPI_KEY=...      # optional
export REFIMATCH_RATE_STATE=TX
export REFIMATCH_CORS_ORIGINS=*
```

---

## Disclaimer

This is a prototype for education and demos. Lender offers may be synthetic or third-party samples. Listing data can be incomplete. Always verify with licensed professionals and official lenders before making financial decisions.
