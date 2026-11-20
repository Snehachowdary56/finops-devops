"""Create a new service from the platform template.

    python -m platformkit.new_service orders-api --team data
    python -m platformkit.new_service orders-api --team data --gitops   # also register it with Argo CD

Every generated service follows the same standards (health and metrics endpoints, non-root image,
least-privilege ServiceAccount, probes, resource limits, tests), so teams get a working, compliant
service in one command instead of copying files by hand.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).resolve().parent / "templates" / "service"
NAME = re.compile(r"^[a-z]([-a-z0-9]{1,38}[a-z0-9])$")       # Kubernetes DNS-1123 label, 3-40 characters
RESERVED = {"default", "kube-system", "kube-public", "argocd", "finops"}


class TemplateError(ValueError):
    pass


def validate(name: str, team: str, port: int, replicas: int) -> None:
    if not NAME.match(name):
        raise TemplateError(f"'{name}' is not a valid name: use 3-40 lower-case letters, digits and dashes, starting with a letter")
    if name in RESERVED:
        raise TemplateError(f"'{name}' is reserved")
    if not NAME.match(team):
        raise TemplateError(f"'{team}' is not a valid team name")
    if not 1024 <= port <= 65535:
        raise TemplateError("port must be between 1024 and 65535 (non-root containers cannot bind lower ports)")
    if not 1 <= replicas <= 5:
        raise TemplateError("replicas must be between 1 and 5")


def render(name: str, team: str, out_dir: Path, port: int = 8080, replicas: int = 2, image: str | None = None) -> list[Path]:
    validate(name, team, port, replicas)
    target = out_dir / name
    if target.exists():
        raise TemplateError(f"{target} already exists; refusing to overwrite it")
    values = {"name": name, "team": team, "port": port, "replicas": replicas,
              "namespace": name, "image": image or f"{name}:local"}
    written = []
    for src in sorted(TEMPLATE.rglob("*.tmpl")):
        dest = target / src.relative_to(TEMPLATE).with_suffix("")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(Template(src.read_text()).substitute(values))
        written.append(dest)
    return written


def register_gitops(name: str, repo_url: str, apps_dir: Path) -> Path:
    """Adds an Argo CD Application for the service, so the app-of-apps picks it up from Git."""
    app = apps_dir / f"{name}.yaml"
    app.write_text(Template((ROOT / "gitops" / "application.yaml.tmpl").read_text()).substitute(
        name=name, repo_url=repo_url, path=f"services/{name}/k8s"))
    return app


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Create a new service from the platform template")
    p.add_argument("name")
    p.add_argument("--team", required=True)
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--replicas", type=int, default=2)
    p.add_argument("--out", type=Path, default=ROOT / "services")
    p.add_argument("--gitops", action="store_true", help="also add an Argo CD Application in gitops/apps/")
    p.add_argument("--repo-url", default="https://github.com/Snehachowdary56/finops-devops")
    a = p.parse_args(argv)
    try:
        files = render(a.name, a.team, a.out, a.port, a.replicas)
    except TemplateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"Created {a.name} ({len(files)} files) in {a.out / a.name}")
    if a.gitops:
        print(f"Registered with Argo CD: {register_gitops(a.name, a.repo_url, ROOT / 'gitops' / 'apps')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
