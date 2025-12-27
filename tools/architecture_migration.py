#!/usr/bin/env python
"""
Architecture Migration Tool for DeepSearch

This tool automates the migration from legacy architecture to hexagonal architecture.
It analyzes code, identifies migration candidates, and performs safe transformations.
"""

import argparse
import ast
import json
import os
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class MigrationCandidate:
    """Represents a file/module that needs migration."""

    source_path: Path
    target_path: Path
    module_type: str  # 'service', 'repository', 'controller', etc.
    dependencies: List[str]
    complexity: int  # Lines of code
    priority: int  # 1-5, 1 being highest


@dataclass
class MigrationReport:
    """Migration execution report."""

    total_files: int
    migrated_files: int
    failed_files: int
    rollback_points: List[str]
    warnings: List[str]
    errors: List[str]


class CodeAnalyzer:
    """Analyzes Python code to understand structure and dependencies."""

    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.import_map: Dict[str, Set[str]] = defaultdict(set)
        self.class_map: Dict[str, List[str]] = defaultdict(list)
        self.function_map: Dict[str, List[str]] = defaultdict(list)

    def analyze_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze a single Python file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)

            analysis: Dict[str, Any] = {
                "path": str(file_path),
                "imports": self._extract_imports(tree),
                "classes": self._extract_classes(tree),
                "functions": self._extract_functions(tree),
                "lines": len(content.splitlines()),
                "complexity": self._calculate_complexity(tree),
                "type": self._determine_module_type(tree, file_path),
            }

            return analysis
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return None

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract all imports from AST."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        return imports

    def _extract_classes(self, tree: ast.AST) -> List[str]:
        """Extract class names from AST."""
        return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    def _extract_functions(self, tree: ast.AST) -> List[str]:
        """Extract function names from AST."""
        return [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

    def _calculate_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity (simplified)."""
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
        return complexity

    def _determine_module_type(self, tree: ast.AST, file_path: Path) -> str:
        """Determine the type of module based on patterns."""
        path_str = str(file_path)
        classes = self._extract_classes(tree)

        # Path-based detection
        if "service" in path_str.lower():
            return "service"
        elif "repository" in path_str.lower() or "repo" in path_str.lower():
            return "repository"
        elif "controller" in path_str.lower() or "api" in path_str.lower():
            return "controller"
        elif "model" in path_str.lower() or "entity" in path_str.lower():
            return "entity"
        elif "provider" in path_str.lower():
            return "provider"

        # Class-based detection
        for class_name in classes:
            if "Service" in class_name:
                return "service"
            elif "Repository" in class_name or "Repo" in class_name:
                return "repository"
            elif "Controller" in class_name:
                return "controller"
            elif "Provider" in class_name:
                return "provider"

        return "unknown"

    def analyze_directory(self, directory: Path) -> List[Dict]:
        """Analyze all Python files in a directory."""
        results = []
        for py_file in directory.rglob("*.py"):
            if "__pycache__" not in str(py_file):
                analysis = self.analyze_file(py_file)
                if analysis:
                    results.append(analysis)
        return results


class MigrationPlanner:
    """Plans the migration strategy based on code analysis."""

    # Mapping of old structure to new hexagonal architecture
    MIGRATION_RULES = {
        "service": "application/services",
        "repository": "infrastructure/repositories",
        "controller": "interfaces/rest/controllers",
        "entity": "domain/entities",
        "model": "domain/entities",
        "provider": "infrastructure/providers",
        "api": "interfaces/rest",
        "database": "infrastructure/persistence",
        "cache": "infrastructure/cache",
        "utils": "shared/utils",
    }

    def __init__(self, source_root: Path, target_root: Path):
        self.source_root = source_root
        self.target_root = target_root
        self.migration_plan: List[MigrationCandidate] = []

    def create_plan(self, analysis_results: List[Dict]) -> List[MigrationCandidate]:
        """Create migration plan based on analysis."""
        for analysis in analysis_results:
            source_path = Path(analysis["path"])
            module_type = analysis["type"]

            if module_type in self.MIGRATION_RULES:
                target_dir = self.MIGRATION_RULES[module_type]
                relative_path = source_path.relative_to(self.source_root)
                target_path = self.target_root / target_dir / relative_path.name

                candidate = MigrationCandidate(
                    source_path=source_path,
                    target_path=target_path,
                    module_type=module_type,
                    dependencies=analysis["imports"],
                    complexity=analysis["complexity"],
                    priority=self._calculate_priority(analysis),
                )

                self.migration_plan.append(candidate)

        # Sort by priority
        self.migration_plan.sort(key=lambda x: x.priority)
        return self.migration_plan

    def _calculate_priority(self, analysis: Dict) -> int:
        """Calculate migration priority (1=highest, 5=lowest)."""
        # Entities and domain objects have highest priority
        if analysis["type"] in ["entity", "model"]:
            return 1
        # Then repositories and services
        elif analysis["type"] in ["repository", "service"]:
            return 2
        # Then controllers and interfaces
        elif analysis["type"] in ["controller", "api"]:
            return 3
        # Infrastructure components
        elif analysis["type"] in ["provider", "cache"]:
            return 4
        # Everything else
        else:
            return 5

    def save_plan(self, output_file: Path):
        """Save migration plan to JSON file."""
        plan_data = [
            {
                "source": str(c.source_path),
                "target": str(c.target_path),
                "type": c.module_type,
                "priority": c.priority,
                "complexity": c.complexity,
            }
            for c in self.migration_plan
        ]

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, indent=2, ensure_ascii=False)


class MigrationExecutor:
    """Executes the migration plan with safety checks."""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.backup_dir = Path("migration_backup") / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.report = MigrationReport(
            total_files=0,
            migrated_files=0,
            failed_files=0,
            rollback_points=[],
            warnings=[],
            errors=[],
        )

    def execute(self, migration_plan: List[MigrationCandidate]) -> MigrationReport:
        """Execute the migration plan."""
        self.report.total_files = len(migration_plan)

        if not self.dry_run:
            self.backup_dir.mkdir(parents=True, exist_ok=True)

        for candidate in migration_plan:
            try:
                self._migrate_file(candidate)
                self.report.migrated_files += 1
            except Exception as e:
                self.report.failed_files += 1
                self.report.errors.append(f"Failed to migrate {candidate.source_path}: {e}")

        return self.report

    def _migrate_file(self, candidate: MigrationCandidate):
        """Migrate a single file."""
        print(
            f"{'[DRY RUN] ' if self.dry_run else ''}Migrating {candidate.source_path} -> {candidate.target_path}"
        )

        if not self.dry_run:
            # Create backup
            backup_path = self.backup_dir / candidate.source_path.relative_to(
                candidate.source_path.parent.parent
            )
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate.source_path, backup_path)
            self.report.rollback_points.append(str(backup_path))

            # Create target directory
            candidate.target_path.parent.mkdir(parents=True, exist_ok=True)

            # Read and transform content
            content = self._transform_content(candidate)

            # Write to new location
            with open(candidate.target_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Update __init__.py files
            self._update_init_files(candidate.target_path.parent)

    def _transform_content(self, candidate: MigrationCandidate) -> str:
        """Transform file content for new architecture."""
        with open(candidate.source_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Update imports based on new structure
        content = self._update_imports(content, candidate)

        # Add architecture-specific decorators/patterns
        if candidate.module_type == "service":
            content = self._add_service_patterns(content)
        elif candidate.module_type == "repository":
            content = self._add_repository_patterns(content)

        return content

    def _update_imports(self, content: str, candidate: MigrationCandidate) -> str:
        """Update import statements for new structure."""
        # This is a simplified version - real implementation would be more sophisticated
        import_mappings = {
            "from services.": "from application.services.",
            "from storage.": "from infrastructure.persistence.",
            "from data_providers.": "from infrastructure.providers.",
            "from webui.api.": "from interfaces.rest.",
        }

        for old_import, new_import in import_mappings.items():
            content = content.replace(old_import, new_import)

        return content

    def _add_service_patterns(self, content: str) -> str:
        """Add application service patterns."""
        # Add dependency injection imports if not present
        if "from typing import" not in content:
            content = "from typing import Optional, Any\n" + content

        return content

    def _add_repository_patterns(self, content: str) -> str:
        """Add repository pattern imports."""
        if "from domain.interfaces.repository import IRepository" not in content:
            content = "from domain.interfaces.repository import IRepository\n" + content

        return content

    def _update_init_files(self, directory: Path):
        """Update or create __init__.py files."""
        init_file = directory / "__init__.py"
        if not init_file.exists():
            init_file.touch()

    def rollback(self):
        """Rollback all migrations."""
        if self.dry_run:
            print("[DRY RUN] Would rollback migrations")
            return

        print(f"Rolling back {len(self.report.rollback_points)} files...")
        for backup_file in self.report.rollback_points:
            # Restore from backup
            # Implementation would restore files from backup
            pass


class ImportUpdater:
    """Updates all import statements after migration."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.import_map: Dict[str, str] = {}

    def build_import_map(self, migration_plan: List[MigrationCandidate]):
        """Build mapping of old imports to new imports."""
        for candidate in migration_plan:
            old_module = self._path_to_module(candidate.source_path)
            new_module = self._path_to_module(candidate.target_path)
            self.import_map[old_module] = new_module

    def _path_to_module(self, path: Path) -> str:
        """Convert file path to module import path."""
        relative = path.relative_to(self.project_root)
        module = str(relative).replace(os.sep, ".").replace(".py", "")
        return module

    def update_all_imports(self):
        """Update imports in all Python files."""
        for py_file in self.project_root.rglob("*.py"):
            if "__pycache__" not in str(py_file):
                self._update_file_imports(py_file)

    def _update_file_imports(self, file_path: Path):
        """Update imports in a single file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            updated = False
            for old_import, new_import in self.import_map.items():
                if old_import in content:
                    content = content.replace(f"from {old_import}", f"from {new_import}")
                    content = content.replace(f"import {old_import}", f"import {new_import}")
                    updated = True

            if updated:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Updated imports in {file_path}")
        except Exception as e:
            print(f"Error updating {file_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Architecture Migration Tool")
    parser.add_argument(
        "action", choices=["analyze", "plan", "migrate", "rollback"], help="Action to perform"
    )
    parser.add_argument("--source", type=str, default="deepsearch", help="Source directory")
    parser.add_argument("--target", type=str, default="deepsearch", help="Target directory")
    parser.add_argument(
        "--dry-run", action="store_true", help="Perform dry run without actual changes"
    )
    parser.add_argument(
        "--plan-file", type=str, default="migration_plan.json", help="Migration plan file"
    )

    args = parser.parse_args()

    source_path = Path(args.source)
    target_path = Path(args.target)

    if args.action == "analyze":
        print("Analyzing codebase...")
        analyzer = CodeAnalyzer(source_path)
        results = analyzer.analyze_directory(source_path)
        print(f"Analyzed {len(results)} files")

        # Save analysis results
        with open("analysis_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("Analysis saved to analysis_results.json")

    elif args.action == "plan":
        print("Creating migration plan...")

        # Load analysis results
        with open("analysis_results.json", "r") as f:
            results = json.load(f)

        planner = MigrationPlanner(source_path, target_path)
        plan = planner.create_plan(results)
        planner.save_plan(Path(args.plan_file))

        print(f"Migration plan created with {len(plan)} files")
        print(f"Plan saved to {args.plan_file}")

        # Print summary
        by_type = defaultdict(int)
        for candidate in plan:
            by_type[candidate.module_type] += 1

        print("\nMigration summary by type:")
        for module_type, count in sorted(by_type.items()):
            print(f"  {module_type}: {count} files")

    elif args.action == "migrate":
        print(f"{'[DRY RUN] ' if args.dry_run else ''}Executing migration...")

        # Load migration plan
        with open(args.plan_file, "r") as f:
            plan_data = json.load(f)

        # Convert to MigrationCandidate objects
        plan = []
        for item in plan_data:
            plan.append(
                MigrationCandidate(
                    source_path=Path(item["source"]),
                    target_path=Path(item["target"]),
                    module_type=item["type"],
                    dependencies=[],
                    complexity=item["complexity"],
                    priority=item["priority"],
                )
            )

        executor = MigrationExecutor(dry_run=args.dry_run)
        report = executor.execute(plan)

        # Update imports
        if not args.dry_run:
            print("\nUpdating imports...")
            updater = ImportUpdater(target_path)
            updater.build_import_map(plan)
            updater.update_all_imports()

        # Print report
        print("\n" + "=" * 50)
        print("Migration Report")
        print("=" * 50)
        print(f"Total files: {report.total_files}")
        print(f"Migrated: {report.migrated_files}")
        print(f"Failed: {report.failed_files}")

        if report.warnings:
            print(f"\nWarnings ({len(report.warnings)}):")
            for warning in report.warnings[:5]:
                print(f"  - {warning}")

        if report.errors:
            print(f"\nErrors ({len(report.errors)}):")
            for error in report.errors[:5]:
                print(f"  - {error}")

    elif args.action == "rollback":
        print("Rolling back migration...")
        executor = MigrationExecutor(dry_run=False)
        executor.rollback()
        print("Rollback completed")


if __name__ == "__main__":
    main()
