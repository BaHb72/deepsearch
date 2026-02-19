from pathlib import Path


def test_dockerfile_dask_does_not_copy_full_config_directory() -> None:
    dockerfile_path = Path(__file__).resolve().parents[3] / "Dockerfile.dask"
    content = dockerfile_path.read_text(encoding="utf-8")

    assert "COPY packages/core/config/ ./core/config/" not in content
    assert "COPY packages/core/config/*.py ./core/config/" in content
    assert "settings.prod.yaml.example" in content
