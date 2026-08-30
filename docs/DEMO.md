# RefiMatch — 3-minute demo script

## Hosted (easiest for an audience)

1. Deploy once via Render Blueprint:  
   https://render.com/deploy?repo=https://github.com/ispilledmymilk/refimatch  
2. Share the service URL (cold start ~30–60s on free tier).
3. Open `/` for the web UI; `/docs` for the API.

No laptop terminal required after deploy.

---

## Before the audience arrives (local)

### 1. Start the API (Terminal 1)

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ../../packages/scoring -e ../agent -r requirements.txt
export PYTHONPATH=.
export REFIMATCH_LLM_MOCK=1
export REFIMATCH_RAG_BACKEND=memory
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Verify:

- http://127.0.0.1:8080 — interactive web demo
- http://127.0.0.1:8080/docs — Swagger UI
- http://127.0.0.1:8080/health — `{"status":"ok"}`

### 2. iOS app (optional)

1. Open `ios/RefiMatch/Package.swift` in Xcode.
2. Run on **iPhone Simulator** (iOS 17+).
3. Settings → API URL `http://127.0.0.1:8080` (or your Render URL).

---

## Demo flow (what to say)

| Step | Action | Talking point |
|------|--------|----------------|
| 0 | Open the web app | “Browser demo — refinance and comps in one place.” |
| 1 | **Refinance** tab — loan + sliders | “Auditable Pandas/NumPy scoring; user weights the tradeoffs.” |
| 2 | **One-tap demo** | “Scoring + LangGraph explanation in one API call.” |
| 3 | Best match + chart | “Ranking is deterministic; the chart shows payment differences.” |
| 4 | AI summary + sources | “LLM narrates scores + RAG snippets — doesn’t invent rates.” |
| 5 | **Comps & Appreciation** tab | “Same product loop for home value.” |
| 6 | Pick type (detached / townhouse / …) + Lookup | “Same-type comps; houses within 5 km; apartments include same building.” |
| 7 | Show estimated value + appreciation | “Value is computed — not typed in by the user.” |
| 8 | `/docs` | “REST API ready for iOS / agents / MCP.” |

---

## Backup plans

| Problem | Fix |
|---------|-----|
| Render slow / sleeping | Wait for cold start, or run locally |
| iOS “Offline” | API up; Simulator URL; LAN IP for device |
| No OpenAI key | Keep `REFIMATCH_LLM_MOCK=1` |
| No apartment comps in Austin | Switch to Toronto or Detached / Townhouse |
| Python install errors | Prefer 3.11–3.13 |

---

## Keywords

SwiftUI · FastAPI · Pandas/NumPy · LangGraph · RAG · MCP · comps · FHFA/FRED · RateAPI · Kubernetes · Render
