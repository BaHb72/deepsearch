"""Diagnose Dask version alignment between local worker env and Docker scheduler.

Usage:
    uv run --python ./.venv/Scripts/python.exe python tools/validate_dask_version_alignment.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

TARGET_PACKAGES = ("dask", "distributed", "numpy", "pandas")
DEFAULT_SCHEDULER_CONTAINER = "deepsearch-dask-scheduler"
DEFAULT_WORKER_PYPROJECT = Path("docker/pyproject.worker.toml")
DEFAULT_LOCKFILE = Path("uv.lock")


@dataclass
class CommandResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    error: str = ""


def run_command(args: list[str], timeout: int = 10) -> CommandResult:
    try:
        completed = subprocess.run(  # noqa: S603
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return CommandResult(ok=False, error=str(exc))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(ok=False, error=f"timeout: {exc}")

    return CommandResult(
        ok=completed.returncode == 0,
        stdout=completed.stdout.strip(),
        stderr=completed.stderr.strip(),
        error="" if completed.returncode == 0 else f"returncode={completed.returncode}",
    )


def get_local_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in TARGET_PACKAGES:
        try:
            result[name] = version(name)
        except PackageNotFoundError:
            result[name] = None
    return result


def get_lock_versions(lockfile: Path) -> dict[str, str | None]:
    if not lockfile.exists():
        return {}

    try:
        parsed = tomllib.loads(lockfile.read_text(encoding="utf-8"))
    except Exception:
        return {}

    result: dict[str, str | None] = {}
    packages = parsed.get("package", [])
    if not isinstance(packages, list):
        return result

    for item in packages:
        if not isinstance(item, dict):
            continue
        pkg_name = item.get("name")
        if pkg_name in TARGET_PACKAGES:
            pkg_version = item.get("version")
            if isinstance(pkg_version, str):
                result[pkg_name] = pkg_version
    return result


def get_worker_dependency_specs(pyproject_file: Path) -> dict[str, str]:
    if not pyproject_file.exists():
        return {}

    try:
        parsed = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
    except Exception:
        return {}

    project = parsed.get("project", {})
    if not isinstance(project, dict):
        return {}

    deps = project.get("dependencies", [])
    if not isinstance(deps, list):
        return {}

    result: dict[str, str] = {}
    for dep in deps:
        if not isinstance(dep, str):
            continue
        for pkg in TARGET_PACKAGES:
            if (
                dep.startswith(f"{pkg}>=")
                or dep.startswith(f"{pkg}==")
                or dep.startswith(f"{pkg}<")
            ):
                result[pkg] = dep
    return result


def detect_scheduler_container(preferred: str) -> tuple[str | None, str | None]:
    result = run_command(["docker", "ps", "--format", "{{.Names}}"], timeout=8)
    if not result.ok:
        return None, f"docker ps failed: {result.error} {result.stderr}".strip()

    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not names:
        return None, "no running docker containers"

    if preferred in names:
        return preferred, None

    for name in names:
        if "dask" in name and "scheduler" in name:
            return name, None

    return None, "scheduler container not found in running containers"


def get_scheduler_versions(container_name: str) -> tuple[dict[str, str | None], str | None]:
    py_code = (
        "import json\n"
        "from importlib.metadata import PackageNotFoundError, version\n"
        f"pkgs={list(TARGET_PACKAGES)!r}\n"
        "data={}\n"
        "for p in pkgs:\n"
        "    try:\n"
        "        data[p]=version(p)\n"
        "    except PackageNotFoundError:\n"
        "        data[p]=None\n"
        "print(json.dumps(data, ensure_ascii=True))\n"
    )
    cmd = ["docker", "exec", container_name, "python", "-c", py_code]
    result = run_command(cmd, timeout=15)
    if not result.ok:
        return {}, f"docker exec failed: {result.error} {result.stderr}".strip()

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {}, f"invalid scheduler json: {exc}"

    scheduler_versions: dict[str, str | None] = {}
    for pkg in TARGET_PACKAGES:
        value = parsed.get(pkg)
        scheduler_versions[pkg] = value if isinstance(value, str) or value is None else None
    return scheduler_versions, None


def compare_versions(
    local_versions: dict[str, str | None],
    scheduler_versions: dict[str, str | None],
) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    for pkg in TARGET_PACKAGES:
        local_v = local_versions.get(pkg)
        sched_v = scheduler_versions.get(pkg)
        report[pkg] = {
            "local": local_v,
            "scheduler": sched_v,
            "aligned": bool(local_v is not None and sched_v is not None and local_v == sched_v),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scheduler-container",
        default=DEFAULT_SCHEDULER_CONTAINER,
        help="Preferred Docker scheduler container name",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when versions are mismatched or scheduler is unavailable",
    )
    args = parser.parse_args()

    local_versions = get_local_versions()
    lock_versions = get_lock_versions(DEFAULT_LOCKFILE)
    worker_specs = get_worker_dependency_specs(DEFAULT_WORKER_PYPROJECT)

    scheduler_container, container_error = detect_scheduler_container(args.scheduler_container)
    scheduler_versions: dict[str, str | None] = {}
    scheduler_error: str | None = None
    if scheduler_container:
        scheduler_versions, scheduler_error = get_scheduler_versions(scheduler_container)
    else:
        scheduler_error = container_error

    comparison = compare_versions(local_versions, scheduler_versions) if scheduler_versions else {}
    has_mismatch = any(not item.get("aligned", False) for item in comparison.values())
    status = "unchecked"
    if scheduler_versions:
        status = "mismatch" if has_mismatch else "aligned"

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "local_versions": local_versions,
        "scheduler_container": scheduler_container,
        "scheduler_versions": scheduler_versions,
        "scheduler_error": scheduler_error,
        "comparison": comparison,
        "worker_dependency_specs": worker_specs,
        "lock_versions": lock_versions,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.strict and (status != "aligned"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
