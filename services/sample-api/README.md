# sample-api

Owned by **platform**. Created with the platform template (`python -m platformkit.new_service`).

## Onboarding guide

What you get without any setup:

| Standard | Where |
|---|---|
| `/health` for Kubernetes probes, `/metrics` for Prometheus | `app/main.py` |
| Small non-root container image with a health check | `Dockerfile` |
| Kubernetes manifests: own namespace and ServiceAccount (no extra permissions), 2 replicas, probes, CPU and memory limits, read-only file system | `k8s/` |
| Tests (run with `pytest` in this folder) | `tests/`, `pytest.ini` |
| CI: tests, image build, container health check and manifest check run automatically for every folder under `services/` | `.github/workflows/services.yml` |
| Deployment through GitOps: add the service to `gitops/apps/` and Argo CD keeps the cluster in sync with Git | `gitops/` |

Run locally:

```
pip install -r requirements.txt pytest
pytest
python -m app.main
```

Then open http://localhost:8080/health.
