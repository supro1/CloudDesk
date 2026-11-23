from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from backend.app.core.config import Settings

_ROOT = Path(__file__).resolve().parents[2]


def test_container_images_are_non_root_and_have_health_checks() -> None:
    backend = (_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    frontend = (_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    next_config = (_ROOT / "frontend" / "next.config.ts").read_text(encoding="utf-8")
    frontend_health = _ROOT / "frontend" / "app" / "api" / "health" / "route.ts"
    root_dockerignore = (_ROOT / ".dockerignore").read_text(encoding="utf-8")
    frontend_dockerignore = (
        _ROOT / "frontend" / ".dockerignore"
    ).read_text(encoding="utf-8")

    assert backend.count("\nFROM ") >= 1
    assert "USER app" in backend
    assert "/health/live" in backend
    assert "USER app" in frontend
    assert "HEALTHCHECK" in frontend and "/api/health" in frontend
    assert frontend_health.is_file()
    assert 'output: "standalone"' in next_config
    assert "data" in root_dockerignore
    assert ".env" in root_dockerignore
    assert "node_modules" in frontend_dockerignore
    assert ".next" in frontend_dockerignore


def test_compose_keeps_stateful_services_private_and_orders_bootstrap() -> None:
    compose = yaml.safe_load(
        (_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]
    assert set(services) == {
        "backend",
        "frontend",
        "knowledge-ingest",
        "qdrant",
        "redis",
    }

    backend = services["backend"]
    assert backend["ports"] == ["127.0.0.1:8000:8000"]
    assert backend["depends_on"]["redis"]["condition"] == "service_healthy"
    assert backend["depends_on"]["qdrant"]["condition"] == "service_healthy"
    assert "backend-data:/app/data" in backend["volumes"]
    assert not services["qdrant"].get("ports")
    assert not services["redis"].get("ports")
    assert (
        services["frontend"]["depends_on"]["knowledge-ingest"]["condition"]
        == "service_completed_successfully"
    )
    assert "backend-data:/app/data" in services["knowledge-ingest"]["volumes"]
    assert services["qdrant"]["build"]["context"] == "deployment/docker/qdrant"
    qdrant_dockerfile = (
        _ROOT / "deployment" / "docker" / "qdrant" / "Dockerfile"
    ).read_text(encoding="utf-8")
    assert "USER qdrant" in qdrant_dockerfile
    assert "apt-get install" in qdrant_dockerfile
    assert services["frontend"]["build"]["args"]["NEXT_PUBLIC_API_URL"] == (
        "${NEXT_PUBLIC_API_URL:-http://localhost:8000}"
    )


def test_environment_example_covers_settings_and_git_ignores_local_state() -> None:
    example = (_ROOT / ".env.example").read_text(encoding="utf-8")
    environment_names = {
        line.partition("=")[0]
        for line in example.splitlines()
        if line and not line.lstrip().startswith("#") and "=" in line
    }
    missing = {
        name.upper()
        for name in Settings.model_fields
        if name.upper() not in environment_names
    }
    assert not missing, f".env.example is missing settings: {sorted(missing)}"

    ignored = (_ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".env", "data/", "*.db", ".terraform/", "*.tfstate.*", "*.tfvars", "tfplan"):
        assert pattern in ignored

    tracked = subprocess.run(
        ["git", "ls-files", "--cached"],
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    committed_env_files = [
        path
        for path in tracked
        if Path(path).name == ".env"
        or (Path(path).name.startswith(".env.") and Path(path).name != ".env.example")
    ]
    assert not committed_env_files, f"Real environment files are tracked: {committed_env_files}"


def test_cloud_roots_are_scaffolded_without_committed_runtime_secrets() -> None:
    expected_resources = {
        "aws": ("aws_ecr_repository", "aws_cloudwatch_log_group"),
        "azure": ("azurerm_container_registry", "azurerm_log_analytics_workspace"),
        "gcp": ("google_artifact_registry_repository",),
    }
    for cloud, resources in expected_resources.items():
        root = _ROOT / "deployment" / cloud
        config = "\n".join(
            path.read_text(encoding="utf-8")
            for path in root.glob("*.tf")
        )
        assert config.strip(), f"Terraform root {cloud} has no configuration"
        assert all(resource in config for resource in resources)
        assert (root / "backend.hcl.example").is_file()
        assert (root / "environments" / "dev" / "terraform.tfvars.example").is_file()

    workflow = yaml.safe_load(
        (_ROOT / ".github" / "workflows" / "terraform-validate.yml").read_text(
            encoding="utf-8"
        )
    )
    assert workflow["jobs"]["validate"]["strategy"]["matrix"]["cloud"] == [
        "aws",
        "azure",
        "gcp",
    ]


def test_ci_workflows_cover_tests_images_and_security_scans() -> None:
    workflows = _ROOT / ".github" / "workflows"
    test_workflow = yaml.safe_load(
        (workflows / "test.yml").read_text(encoding="utf-8")
    )
    docker_workflow = yaml.safe_load(
        (workflows / "docker-build.yml").read_text(encoding="utf-8")
    )
    security_workflow = yaml.safe_load(
        (workflows / "security.yml").read_text(encoding="utf-8")
    )

    assert set(test_workflow["jobs"]) == {"backend", "frontend"}
    image_builds = [
        step
        for step in docker_workflow["jobs"]["build"]["steps"]
        if step.get("uses", "").startswith("docker/build-push-action@")
    ]
    assert len(image_builds) == 3
    assert set(security_workflow["jobs"]) == {
        "secrets-and-dependencies",
        "terraform-scan",
    }
