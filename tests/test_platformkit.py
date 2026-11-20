"""Tests for the self-service template (platformkit.new_service)."""
import subprocess
import sys

import pytest
import yaml

from platformkit.new_service import TemplateError, main, register_gitops, render


def test_creates_a_complete_service(tmp_path):
    files = {p.relative_to(tmp_path / "orders-api").as_posix() for p in render("orders-api", "data", tmp_path)}
    assert {"app/main.py", "Dockerfile", "README.md", "requirements.txt", "pytest.ini", "tests/test_app.py",
            "k8s/kustomization.yaml", "k8s/deployment.yaml", "k8s/service.yaml", "k8s/serviceaccount.yaml",
            "k8s/namespace.yaml"} <= files


def test_kubernetes_manifests_follow_platform_standards(tmp_path):
    render("orders-api", "data", tmp_path, port=9090, replicas=3)
    dep = yaml.safe_load((tmp_path / "orders-api/k8s/deployment.yaml").read_text())
    pod = dep["spec"]["template"]["spec"]
    c = pod["containers"][0]
    assert dep["spec"]["replicas"] == 3
    assert pod["serviceAccountName"] == "orders-api" and pod["securityContext"]["runAsNonRoot"] is True
    assert c["readinessProbe"]["httpGet"] == {"path": "/health", "port": 9090}
    assert c["resources"]["limits"] and c["resources"]["requests"]
    assert c["securityContext"]["readOnlyRootFilesystem"] is True and c["securityContext"]["capabilities"]["drop"] == ["ALL"]
    sa = yaml.safe_load((tmp_path / "orders-api/k8s/serviceaccount.yaml").read_text())
    assert sa["automountServiceAccountToken"] is False
    kust = yaml.safe_load((tmp_path / "orders-api/k8s/kustomization.yaml").read_text())
    assert kust["namespace"] == "orders-api" and kust["labels"][0]["pairs"]["team"] == "data"


def test_generated_service_passes_its_own_tests(tmp_path):
    render("orders-api", "data", tmp_path)
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=tmp_path / "orders-api", capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 passed" in result.stdout


@pytest.mark.parametrize("name", ["Orders", "a", "1orders", "orders_api", "orders-", "default", "kube-system", "x" * 41])
def test_rejects_bad_or_reserved_names(tmp_path, name):
    with pytest.raises(TemplateError):
        render(name, "data", tmp_path)


@pytest.mark.parametrize("port,replicas", [(80, 2), (70000, 2), (8080, 0), (8080, 9)])
def test_rejects_bad_settings(tmp_path, port, replicas):
    with pytest.raises(TemplateError):
        render("orders-api", "data", tmp_path, port=port, replicas=replicas)


def test_never_overwrites_an_existing_service(tmp_path):
    render("orders-api", "data", tmp_path)
    with pytest.raises(TemplateError, match="already exists"):
        render("orders-api", "data", tmp_path)


def test_gitops_registration_points_argo_cd_at_the_service(tmp_path):
    app = yaml.safe_load(register_gitops("orders-api", "https://github.com/x/y", tmp_path).read_text())
    assert app["kind"] == "Application" and app["spec"]["source"]["path"] == "services/orders-api/k8s"
    assert app["spec"]["syncPolicy"]["automated"] == {"prune": True, "selfHeal": True}


def test_cli_reports_errors_without_a_traceback(tmp_path, capsys):
    assert main(["Bad_Name", "--team", "data", "--out", str(tmp_path)]) == 2
    assert "not a valid name" in capsys.readouterr().err


def test_committed_gitops_apps_are_valid():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for f in sorted((root / "gitops" / "apps").glob("*.yaml")):
        app = yaml.safe_load(f.read_text())
        path = app["spec"]["source"]["path"]
        assert (root / path).is_dir(), f"{f.name} points to missing folder {path}"
        assert app["spec"]["syncPolicy"]["automated"]["selfHeal"] is True
