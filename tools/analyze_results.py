#!/usr/bin/env python
"""
Analyze architecture migration results and create action plan.
"""
import json
from collections import defaultdict
from pathlib import Path


def analyze_results():
    """Analyze the code analysis results."""
    with open("analysis_results.json", "r") as f:
        data = json.load(f)

    # Statistics by type
    type_stats = defaultdict(int)
    complexity_by_type = defaultdict(list)
    files_by_type = defaultdict(list)

    for item in data:
        file_type = item.get("type", "unknown")
        type_stats[file_type] += 1
        complexity_by_type[file_type].append(item.get("complexity", 0))
        files_by_type[file_type].append(item.get("path", ""))

    print("=" * 60)
    print("CODE ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total files analyzed: {len(data)}")
    print()

    print("Module Distribution:")
    print("-" * 40)
    for module_type, count in sorted(type_stats.items(), key=lambda x: -x[1]):
        avg_complexity = sum(complexity_by_type[module_type]) / count if count > 0 else 0
        print(f"  {module_type:20} {count:4} files (avg complexity: {avg_complexity:.1f})")

    # Identify high-priority migration candidates
    print("\n" + "=" * 60)
    print("MIGRATION CANDIDATES (Priority Order)")
    print("=" * 60)

    # Priority 1: Entities and Models (domain layer)
    print("\nPriority 1: Domain Layer (Foundation)")
    print("-" * 40)
    domain_types = ["entity", "model"]
    for t in domain_types:
        if t in files_by_type:
            print(f"  {t}: {len(files_by_type[t])} files")
            for f in files_by_type[t][:5]:  # Show first 5
                print(f"    - {Path(f).name}")

    # Priority 2: Services (application layer)
    print("\nPriority 2: Application Layer (Business Logic)")
    print("-" * 40)
    if "service" in files_by_type:
        print(f"  services: {len(files_by_type['service'])} files")
        # Show services with lowest complexity first (easier to migrate)
        service_complexities = [
            (f, c) for f, c in zip(files_by_type["service"], complexity_by_type["service"])
        ]
        service_complexities.sort(key=lambda x: x[1])
        for f, c in service_complexities[:5]:
            print(f"    - {Path(f).name} (complexity: {c})")

    # Priority 3: Repositories and data access
    print("\nPriority 3: Infrastructure Layer (Data Access)")
    print("-" * 40)
    infra_types = ["repository", "provider", "database"]
    for t in infra_types:
        if t in files_by_type:
            print(f"  {t}: {len(files_by_type[t])} files")

    # Priority 4: Controllers and APIs
    print("\nPriority 4: Interface Layer (APIs)")
    print("-" * 40)
    interface_types = ["controller", "api"]
    for t in interface_types:
        if t in files_by_type:
            print(f"  {t}: {len(files_by_type[t])} files")

    # Complexity analysis
    print("\n" + "=" * 60)
    print("COMPLEXITY ANALYSIS")
    print("=" * 60)

    all_complexities = []
    for complexities in complexity_by_type.values():
        all_complexities.extend(complexities)

    if all_complexities:
        print(f"  Average complexity: {sum(all_complexities)/len(all_complexities):.2f}")
        print(f"  Max complexity: {max(all_complexities)}")
        print(f"  Min complexity: {min(all_complexities)}")

        # Files with highest complexity (need refactoring)
        print("\n  High Complexity Files (Need Refactoring):")
        complex_files = []
        for item in data:
            if item.get("complexity", 0) > 20:
                complex_files.append((item["path"], item["complexity"]))

        complex_files.sort(key=lambda x: -x[1])
        for f, c in complex_files[:10]:
            print(f"    - {Path(f).name}: {c}")

    # Import dependencies analysis
    print("\n" + "=" * 60)
    print("DEPENDENCY ANALYSIS")
    print("=" * 60)

    # Find circular dependencies
    import_graph = {}
    for item in data:
        file_path = item["path"]
        imports = item.get("imports", [])
        import_graph[file_path] = imports

    # Count external dependencies
    external_deps = defaultdict(int)
    internal_deps = defaultdict(int)

    for item in data:
        for imp in item.get("imports", []):
            if imp.startswith("deepsearch"):
                internal_deps[imp] += 1
            elif not imp.startswith("_"):
                external_deps[imp.split(".")[0]] += 1

    print("  Top External Dependencies:")
    for dep, count in sorted(external_deps.items(), key=lambda x: -x[1])[:10]:
        print(f"    - {dep}: used {count} times")

    print("\n  Top Internal Dependencies:")
    for dep, count in sorted(internal_deps.items(), key=lambda x: -x[1])[:10]:
        print(f"    - {dep}: used {count} times")

    # Generate migration plan
    print("\n" + "=" * 60)
    print("RECOMMENDED MIGRATION PLAN")
    print("=" * 60)

    print(
        """
Phase 1: Quick Wins (Week 1)
  1. Delete all 'unknown' type files (likely utilities/scripts)
  2. Move simple entity/model files to domain/entities
  3. Establish domain layer foundation

Phase 2: Service Migration (Week 2)
  1. Start with low-complexity services
  2. Apply dependency injection pattern
  3. Create application service interfaces

Phase 3: Infrastructure (Week 3)
  1. Consolidate data access patterns
  2. Implement repository pattern
  3. Unify provider interfaces

Phase 4: Interface Layer (Week 4)
  1. Refactor API controllers
  2. Implement CQRS pattern
  3. Clean up REST endpoints
"""
    )

    # Save actionable migration plan
    migration_plan = {
        "statistics": {
            "total_files": len(data),
            "types": dict(type_stats),
            "avg_complexity": (
                sum(all_complexities) / len(all_complexities) if all_complexities else 0
            ),
        },
        "priorities": {
            "p1_domain": [
                f for f in files_by_type.get("entity", []) + files_by_type.get("model", [])
            ][:20],
            "p2_services": [f for f in files_by_type.get("service", [])][:20],
            "p3_infrastructure": [
                f for f in files_by_type.get("repository", []) + files_by_type.get("provider", [])
            ][:20],
            "p4_interfaces": [
                f for f in files_by_type.get("controller", []) + files_by_type.get("api", [])
            ][:20],
        },
    }

    with open("migration_action_plan.json", "w") as f:
        json.dump(migration_plan, f, indent=2)

    print("\n✅ Action plan saved to migration_action_plan.json")

    return type_stats, len(data)


if __name__ == "__main__":
    analyze_results()
