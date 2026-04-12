from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from setuptools import find_packages, setup

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for older build envs
    import tomli as tomllib  # type: ignore[no-redef]

BASE_DIR = Path(__file__).resolve().parent


def load_readme() -> str:
    readme_path = BASE_DIR / "README.md"
    return readme_path.read_text(encoding="utf-8")


def load_requirements_and_extras() -> Tuple[List[str], Dict[str, List[str]]]:
    requirements_txt = BASE_DIR / "requirements.txt"
    pyproject_toml = BASE_DIR / "pyproject.toml"

    requirements: List[str] = []
    extras: Dict[str, List[str]] = {}

    if pyproject_toml.exists():
        with pyproject_toml.open("rb") as fh:
            data = tomllib.load(fh)

        project_section = data.get("project", {})
        optional_section = project_section.get("optional-dependencies", {})
        dependency_groups = data.get("dependency-groups", {})

        extras.update(optional_section)
        extras.update(dependency_groups)

        requirements = list(project_section.get("dependencies", []))

    if not requirements and requirements_txt.exists():
        with requirements_txt.open("r", encoding="utf-8") as fh:
            requirements = [
                line.strip() for line in fh if line.strip() and not line.startswith("#")
            ]

    if not requirements:
        raise FileNotFoundError(
            "未能在 pyproject.toml 或 requirements.txt 中找到依赖，请确认项目配置。"
        )

    return requirements, extras


long_description = load_readme()
install_requires, extras_require = load_requirements_and_extras()

setup(
    name="deepsearch",
    version="0.1.0",
    author="DeepSearch Team",
    description="深度行情分析系统",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/deepsearch",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.14",
    ],
    python_requires=">=3.14,<3.15",
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "deepsearch=deepsearch.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "deepsearch": [
            "webui/frontend/dist/**/*",
            "settings/*.yaml",
            "settings/*.yml",
        ],
    },
)
