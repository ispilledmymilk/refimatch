# Kubernetes

Build the API image from the repository root:

```bash
docker build -f services/api/Dockerfile -t refimatch-api:latest .
```

Load into kind/minikube if needed, then:

```bash
kubectl apply -k k8s/overlays/local
kubectl -n refimatch wait --for=condition=complete job/refimatch-ingest --timeout=300s
kubectl -n refimatch rollout status deployment/refimatch-api
kubectl -n refimatch port-forward svc/refimatch-api 8080:8080
```

The API `initContainer` waits until `rag_documents` has at least one row (populated by `job-ingest`).

Optional Langfuse: set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `secret.yaml` (do not commit real secrets).
