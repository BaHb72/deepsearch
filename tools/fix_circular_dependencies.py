"""
循环依赖修复工具
分析并提供具体的循环依赖解决方案
"""

import json
from pathlib import Path
from typing import Any, Dict, List


class CircularDependencyFixer:
    def __init__(self):
        self.report: Dict[str, Any] = {}
        self.circular_deps: List[List[str]] = []
        self.module_deps: Dict[str, List[str]] = {}
        self.load_analysis_report()
        self.fixes: List[Dict[str, Any]] = []

    def load_analysis_report(self):
        """加载依赖分析报告"""
        report_file = Path("dependency_analysis_report.json")
        if report_file.exists():
            with open(report_file, "r", encoding="utf-8") as f:
                raw_report = json.load(f)
                if isinstance(raw_report, dict):
                    self.report = raw_report
                self.circular_deps = [
                    list(cycle) for cycle in self.report.get("circular_dependencies", [])
                    if isinstance(cycle, list)
                ]
                raw_module_deps = self.report.get("module_dependencies", {})
                if isinstance(raw_module_deps, dict):
                    self.module_deps = {
                        module: list(deps) if isinstance(deps, list) else []
                        for module, deps in raw_module_deps.items()
                    }
        else:
            print("[!] 未找到依赖分析报告，请先运行 analyze_dependencies.py")
            exit(1)

    def analyze_and_fix(self):
        """分析并修复循环依赖"""
        print("=" * 60)
        print("循环依赖修复方案")
        print("=" * 60)

        # 分析主要的循环依赖模式
        patterns = self.identify_patterns()

        print("\n[+] 识别到的循环依赖模式:")
        for pattern_name, cycles in patterns.items():
            print(f"\n  {pattern_name}: {len(cycles)}个循环")
            for cycle in cycles[:2]:  # 只显示前2个示例
                print(f"    - {' -> '.join(cycle)}")

        # 生成具体的修复方案
        self.generate_fixes()

        # 输出修复方案
        self.output_fixes()

    def identify_patterns(self) -> Dict[str, List[List[str]]]:
        """识别循环依赖模式"""
        patterns: Dict[str, List[List[str]]] = {
            "core_centric": [],  # 以core为中心的循环
            "config_cycle": [],  # config相关的循环
            "observability_cycle": [],  # observability相关的循环
            "infrastructure_cycle": [],  # infrastructure相关的循环
            "small_cycles": [],  # 小循环（2-3个模块）
        }

        for cycle in self.circular_deps:
            if "core" in cycle:
                patterns["core_centric"].append(cycle)
            elif "config" in cycle:
                patterns["config_cycle"].append(cycle)
            elif "observability" in cycle:
                patterns["observability_cycle"].append(cycle)
            elif "infrastructure" in cycle:
                patterns["infrastructure_cycle"].append(cycle)
            elif len(cycle) <= 4:
                patterns["small_cycles"].append(cycle)

        return patterns

    def generate_fixes(self):
        """生成具体的修复方案"""

        # 1. Core模块的循环依赖修复
        self.fixes.append(
            {
                "priority": "HIGH",
                "problem": "Core模块与多个模块形成循环依赖",
                "modules": ["core", "gateway", "messaging", "config", "observability"],
                "solution": """
1. 将core拆分为更小的独立模块:
   - core/runtime: 运行时管理（不依赖其他模块）
   - core/components: 组件管理（依赖runtime）
   - core/lifecycle: 生命周期管理（依赖runtime）

2. 使用依赖注入替代直接导入:
   - 在core/runtime中定义接口
   - 在初始化时注入具体实现
   - 避免模块间的直接import

3. 将共享配置移到独立的shared/config模块

4. 具体修改:
   # core/runtime/engine.py
   - 移除: from deepsearch.gateway import ...
   - 改为: 在__init__中接收gateway实例

   # core/components/manager.py
   - 移除: from deepsearch.observability import ...
   - 改为: 通过依赖注入获取监控服务
""",
                "files_to_modify": [
                    "deepsearch/core/runtime/engine.py",
                    "deepsearch/core/components/component_manager.py",
                    "deepsearch/core/gateway/gateway.py",
                ],
            }
        )

        # 2. Config模块的循环依赖修复
        self.fixes.append(
            {
                "priority": "HIGH",
                "problem": "Config模块与observability和messaging形成循环",
                "modules": ["config", "observability", "messaging"],
                "solution": """
1. 创建独立的配置层:
   - shared/config/base.py: 基础配置类（无依赖）
   - shared/config/loader.py: 配置加载器

2. 移除config对其他模块的依赖:
   - config模块只负责加载和解析配置
   - 不应该import observability或messaging

3. 具体修改:
   # config/__init__.py
   - 移除: from deepsearch.observability import logger
   - 改为: 使用Python内置logging

   # config/settings.py
   - 移除: from deepsearch.messaging import ...
   - 配置验证逻辑移到应用层
""",
                "files_to_modify": [
                    "deepsearch/config/__init__.py",
                    "deepsearch/config/settings.py",
                    "deepsearch/config/loader.py",
                ],
            }
        )

        # 3. Infrastructure循环依赖修复
        self.fixes.append(
            {
                "priority": "MEDIUM",
                "problem": "Infrastructure与shared和core形成循环",
                "modules": ["infrastructure", "shared", "core"],
                "solution": """
1. Infrastructure层应该是最底层，不依赖上层:
   - 移除对core的依赖
   - 移除对application的依赖

2. 使用接口隔离:
   - 在domain/interfaces定义接口
   - infrastructure实现这些接口
   - 上层通过接口使用infrastructure

3. 具体修改:
   # infrastructure/providers/factory.py
   - 移除: from deepsearch.core import ...
   - 改为: 通过构造函数注入需要的依赖

   # infrastructure/persistence/database.py
   - 移除: from deepsearch.core.config import ...
   - 改为: 配置通过参数传递
""",
                "files_to_modify": [
                    "deepsearch/infrastructure/providers/factory.py",
                    "deepsearch/infrastructure/persistence/database.py",
                ],
            }
        )

        # 4. Observability循环依赖修复
        self.fixes.append(
            {
                "priority": "MEDIUM",
                "problem": "Observability与event和messaging形成循环",
                "modules": ["observability", "event", "messaging"],
                "solution": """
1. Observability应该是独立的横切关注点:
   - 不应该依赖业务模块
   - 其他模块通过接口使用observability

2. 具体修改:
   # observability/monitoring/monitor.py
   - 移除: from deepsearch.event import ...
   - 改为: 定义监控接口，由event实现

   # observability/logging/logger.py
   - 移除: from deepsearch.messaging import ...
   - 改为: 使用事件发布订阅模式
""",
                "files_to_modify": [
                    "deepsearch/observability/monitoring/monitor.py",
                    "deepsearch/observability/logging/logger.py",
                ],
            }
        )

        # 5. 小循环的快速修复
        self.fixes.append(
            {
                "priority": "LOW",
                "problem": "小循环依赖（2-3个模块间）",
                "modules": ["utils-config", "messaging-config", "shared-core"],
                "solution": """
1. utils-config循环:
   - utils不应该依赖config
   - 将需要配置的工具类改为接收配置参数

2. messaging-config循环:
   - messaging的配置定义移到config模块
   - messaging只负责实现，不定义配置结构

3. shared-core循环:
   - shared应该是最底层的共享代码
   - core不应该被shared依赖
   - 将共享的核心功能移到shared
""",
                "files_to_modify": [
                    "deepsearch/utils/helpers.py",
                    "deepsearch/messaging/config.py",
                    "deepsearch/shared/core_utils.py",
                ],
            }
        )

    def output_fixes(self):
        """输出修复方案"""
        print("\n" + "=" * 60)
        print("具体修复方案")
        print("=" * 60)

        for idx, fix in enumerate(self.fixes, 1):
            print(f"\n[{idx}] {fix['problem']}")
            print(f"    优先级: {fix['priority']}")
            print(f"    涉及模块: {', '.join(fix['modules'])}")
            print(f"    解决方案:{fix['solution']}")
            print("    需要修改的文件:")
            for file in fix["files_to_modify"]:
                print(f"      - {file}")

        # 生成执行计划
        self.generate_execution_plan()

    def generate_execution_plan(self):
        """生成执行计划"""
        print("\n" + "=" * 60)
        print("执行计划")
        print("=" * 60)

        print(
            """
[第一阶段] 解除核心循环（1-2天）
1. 重构core模块，拆分为runtime、components、lifecycle
2. 引入依赖注入容器，移除直接import
3. 测试核心功能是否正常

[第二阶段] 修复配置循环（1天）
1. 创建shared/config基础配置模块
2. 移除config对其他模块的依赖
3. 更新所有配置引用

[第三阶段] 清理infrastructure（1-2天）
1. 定义domain/interfaces接口
2. infrastructure实现接口
3. 上层通过接口使用infrastructure

[第四阶段] 独立observability（1天）
1. 定义监控接口
2. 移除对业务模块的依赖
3. 实现事件发布订阅

[第五阶段] 修复小循环（半天）
1. 快速修复2-3个模块的小循环
2. 运行测试验证

[验证阶段]（半天）
1. 重新运行依赖分析
2. 确认循环依赖已解决
3. 运行完整测试套件
"""
        )

        # 保存修复方案
        self.save_fix_plan()

    def save_fix_plan(self):
        """保存修复方案到文件"""
        fix_plan = {
            "total_cycles": len(self.circular_deps),
            "fixes": self.fixes,
            "execution_order": [
                "core_refactoring",
                "config_isolation",
                "infrastructure_cleanup",
                "observability_independence",
                "small_cycles_fix",
            ],
        }

        output_file = Path("circular_dependency_fixes.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(fix_plan, f, indent=2, ensure_ascii=False)

        print(f"\n[*] 修复方案已保存到: {output_file}")


if __name__ == "__main__":
    fixer = CircularDependencyFixer()
    fixer.analyze_and_fix()
