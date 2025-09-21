"""
依赖关系分析工具
分析项目中的循环依赖、模块耦合度等问题
"""

import ast
import os
from pathlib import Path
from typing import Dict, Set, List, Tuple
from collections import defaultdict
import json

class DependencyAnalyzer:
    def __init__(self, root_path: str = "deepsearch"):
        self.root_path = Path(root_path)
        self.imports: Dict[str, Set[str]] = defaultdict(set)
        self.module_deps: Dict[str, Set[str]] = defaultdict(set)
        self.circular_deps: List[Tuple[str, str]] = []
        self.coupling_scores: Dict[str, float] = {}

    def analyze(self):
        """分析整个项目的依赖关系"""
        print("[*] 正在分析依赖关系...")

        # 1. 收集所有导入关系
        self._collect_imports()

        # 2. 检测循环依赖
        self._detect_circular_dependencies()

        # 3. 计算模块耦合度
        self._calculate_coupling()

        # 4. 分析架构层次违规
        self._check_architecture_violations()

        # 5. 生成报告
        self._generate_report()

    def _collect_imports(self):
        """收集所有Python文件的导入关系"""
        for py_file in self.root_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            module_name = self._get_module_name(py_file)

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imported = alias.name
                            if imported.startswith("deepsearch"):
                                self.imports[module_name].add(imported)
                                self._add_module_dep(module_name, imported)

                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.startswith("deepsearch"):
                            self.imports[module_name].add(node.module)
                            self._add_module_dep(module_name, node.module)
            except:
                pass  # 忽略解析错误的文件

    def _get_module_name(self, file_path: Path) -> str:
        """获取模块的完整名称"""
        relative = file_path.relative_to(self.root_path.parent)
        parts = list(relative.parts[:-1]) + [relative.stem]
        return ".".join(parts)

    def _add_module_dep(self, from_module: str, to_module: str):
        """添加模块级别的依赖"""
        from_top = from_module.split('.')[1] if len(from_module.split('.')) > 1 else from_module
        to_top = to_module.split('.')[1] if len(to_module.split('.')) > 1 else to_module

        if from_top != to_top:
            self.module_deps[from_top].add(to_top)

    def _detect_circular_dependencies(self):
        """检测循环依赖"""
        visited = set()
        rec_stack = set()

        def dfs(module: str, path: List[str]) -> bool:
            visited.add(module)
            rec_stack.add(module)
            path.append(module)

            for dep in self.module_deps.get(module, []):
                if dep not in visited:
                    if dfs(dep, path.copy()):
                        return True
                elif dep in rec_stack:
                    # 找到循环依赖
                    cycle_start = path.index(dep)
                    cycle = path[cycle_start:] + [dep]
                    self.circular_deps.append(tuple(cycle))

            rec_stack.remove(module)
            return False

        for module in self.module_deps:
            if module not in visited:
                dfs(module, [])

    def _calculate_coupling(self):
        """计算模块耦合度"""
        total_modules = len(self.module_deps)

        for module, deps in self.module_deps.items():
            # 耦合度 = 依赖的模块数 / 总模块数
            if total_modules > 1:
                self.coupling_scores[module] = len(deps) / (total_modules - 1) * 100
            else:
                self.coupling_scores[module] = 0

    def _check_architecture_violations(self):
        """检查架构层次违规"""
        self.violations = []

        # 定义架构层次规则
        layer_rules = {
            'domain': [],  # 领域层不应该依赖其他层
            'application': ['domain'],  # 应用层只能依赖领域层
            'infrastructure': ['domain', 'application'],  # 基础设施层可以依赖领域和应用层
            'interfaces': ['domain', 'application', 'infrastructure'],  # 接口层可以依赖所有层
            'presentation': ['domain', 'application', 'infrastructure', 'interfaces'],
        }

        for module, deps in self.module_deps.items():
            if module in layer_rules:
                allowed_deps = layer_rules[module]
                for dep in deps:
                    if dep in layer_rules and dep not in allowed_deps:
                        self.violations.append({
                            'from': module,
                            'to': dep,
                            'type': 'layer_violation',
                            'message': f'{module}层不应该依赖{dep}层'
                        })

    def _generate_report(self):
        """生成分析报告"""
        print("\n" + "="*60)
        print("依赖关系分析报告")
        print("="*60)

        # 1. 基本统计
        print(f"\n[+] 基本统计:")
        print(f"  - 分析的模块数: {len(self.module_deps)}")
        print(f"  - 总依赖关系数: {sum(len(deps) for deps in self.module_deps.values())}")
        print(f"  - 平均依赖数: {sum(len(deps) for deps in self.module_deps.values()) / max(len(self.module_deps), 1):.1f}")

        # 2. 循环依赖
        print(f"\n[+] 循环依赖检测:")
        if self.circular_deps:
            print(f"  [X] 发现 {len(self.circular_deps)} 个循环依赖:")
            for cycle in self.circular_deps[:5]:  # 只显示前5个
                print(f"    - {' -> '.join(cycle)}")
        else:
            print("  [OK] 未发现循环依赖")

        # 3. 高耦合模块
        print(f"\n[+] 模块耦合度分析:")
        high_coupling = [(m, s) for m, s in self.coupling_scores.items() if s > 30]
        if high_coupling:
            print(f"  [!] 高耦合模块 (>30%):")
            for module, score in sorted(high_coupling, key=lambda x: x[1], reverse=True)[:5]:
                deps_count = len(self.module_deps[module])
                print(f"    - {module}: {score:.1f}% (依赖{deps_count}个模块)")
        else:
            print("  [OK] 所有模块耦合度正常")

        # 4. 架构违规
        print(f"\n[+] 架构层次检查:")
        if self.violations:
            print(f"  [X] 发现 {len(self.violations)} 个架构违规:")
            for v in self.violations[:5]:
                print(f"    - {v['message']}")
        else:
            print("  [OK] 未发现架构层次违规")

        # 5. 模块依赖详情
        print(f"\n[+] 主要模块依赖关系:")
        main_modules = ['domain', 'application', 'infrastructure', 'interfaces', 'presentation',
                       'core', 'webui', 'event', 'messaging', 'observability']

        for module in main_modules:
            if module in self.module_deps:
                deps = self.module_deps[module]
                if deps:
                    print(f"  {module} -> {', '.join(sorted(deps))}")

        # 6. 建议
        print(f"\n[+] 优化建议:")
        if self.circular_deps:
            print("  1. 优先解决循环依赖问题，这会严重影响代码的可维护性")

        if high_coupling:
            print("  2. 重构高耦合模块，考虑使用依赖注入或接口隔离")

        if self.violations:
            print("  3. 修复架构层次违规，确保依赖方向正确")

        if not self.circular_deps and not high_coupling and not self.violations:
            print("  [*] 依赖关系良好，继续保持!")

        # 保存详细报告
        self._save_detailed_report()

    def _save_detailed_report(self):
        """保存详细的JSON报告"""
        report = {
            'summary': {
                'total_modules': len(self.module_deps),
                'total_dependencies': sum(len(deps) for deps in self.module_deps.values()),
                'circular_dependencies_count': len(self.circular_deps),
                'high_coupling_modules': len([s for s in self.coupling_scores.values() if s > 30]),
                'architecture_violations': len(self.violations)
            },
            'module_dependencies': {k: list(v) for k, v in self.module_deps.items()},
            'circular_dependencies': [list(cycle) for cycle in self.circular_deps],
            'coupling_scores': self.coupling_scores,
            'violations': self.violations
        }

        output_file = Path('dependency_analysis_report.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n[*] 详细报告已保存到: {output_file}")


if __name__ == "__main__":
    analyzer = DependencyAnalyzer()
    analyzer.analyze()