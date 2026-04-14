# RefiMatch

iOS client + Kubernetes-first backend that compares **demo** refinance offers using a deterministic **Pandas/NumPy** scoring engine, optional **LangGraph** explanations with **RAG** citations, **MCP** tools, and **Langfuse** tracing.

## Disclaimer

Educational / decision-support only. Not financial, legal, or tax advice. Demo lender data is synthetic.

## Repository layout

| Path | Purpose |
|------|---------|
| [`ios/RefiMatch`](ios/RefiMatch) | SwiftUI app (Swift Package, iOS 17+) |
| [`packages/scoring`](packages/scoring) | Amortization, breakeven, weighted ranking |
| [`services/api`](services/api) | FastAPI: catalog, compare, explain |
| [`services/agent`](services/agent) | LangGraph + retrieval + optional LLM |
| [`rag`](rag) | Markdown sources + ingestion to pgvector |
| [`mcp`](mcp) | MCP stdio server (tools mirror scoring/catalog) |
| [`k8s`](k8s) | Kubernetes manifests |
| [`eval`](eval) | Promptfoo + DeepEval suites |
| [`ml`](ml) | Phase-2 stubs (ranker / fine-tuning hooks) |

## Local backend (Python)

```bash
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e ../../packages/scoring -e ../agent -r requirements.txt
export REFIMATCH_LLM_MOCK=1
export DATABASE_URL=postgresql://refimatch:refimatch@localhost:5432/refimatch
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Without Postgres, set `REFIMATCH_RAG_BACKEND=memory` (default) so retrieval uses bundled vectors.

## Docker image (API)

From repo root:

```bash
docker build -f services/api/Dockerfile -t refimatch-api:latest .
```

## Kubernetes

```bash
kubectl apply -k k8s/overlays/local
```

Port-forward API:

```bash
kubectl -n refimatch port-forward svc/refimatch-api 8080:8080
```

## iOS app

Open `ios/RefiMatch` in Xcode (File → Open → `Package.swift`) or:

```bash
cd ios/RefiMatch && xcodebuild -scheme RefiMatchApp -destination 'platform=iOS Simulator,name=iPhone 16' build
```

Set the API base URL in the app settings screen (defaults to `http://127.0.0.1:8080`).

## Evaluations

```bash
cd eval && pip install -r requirements.txt
pytest ../services/agent/tests ../packages/scoring/tests deepeval_suite.py -q
npx --yes promptfoo@latest eval -c promptfooconfig.yaml
```

## MCP server

```bash
cd mcp && pip install -r requirements.txt
python server.py
```

Connect from an MCP host using stdio transport.
