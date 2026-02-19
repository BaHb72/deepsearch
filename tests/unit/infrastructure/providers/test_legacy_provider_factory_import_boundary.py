import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
ALLOWED_IMPORTERS = {
    "packages/core/infrastructure/providers/integration/compat.py",
}
SCAN_ROOTS = (
    REPO_ROOT / "packages" / "core",
    REPO_ROOT / "apps" / "api",
)


def _imports_legacy_provider_module(source_file: Path) -> bool:
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "apps.api.api.providers":
            imported_symbols = {alias.name for alias in node.names}
            if "*" in imported_symbols or "DataProviderFactory" in imported_symbols:
                return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_name = alias.name
                if imported_name == "apps.api.api.providers":
                    return True
                if imported_name.startswith("apps.api.api.providers."):
                    return True
    return False


def test_legacy_provider_factory_import_only_exists_in_compat_boundary() -> None:
    violations: list[str] = []

    for root in SCAN_ROOTS:
        for source_file in root.rglob("*.py"):
            relative_path = source_file.relative_to(REPO_ROOT).as_posix()
            if relative_path in ALLOWED_IMPORTERS:
                continue
            if _imports_legacy_provider_module(source_file):
                violations.append(relative_path)

    assert not violations, (
        "检测到非兼容边界文件仍直接 import apps.api.api.providers: "
        + ", ".join(sorted(violations))
    )
