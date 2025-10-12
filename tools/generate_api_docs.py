#!/usr/bin/env python
"""
生成API接口文档
扫描前端和后端代码，提取所有API定义并生成文档
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, TypedDict

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


class _FrontendApi(TypedDict):
    function: str
    url: str
    method: str
    file: str


def scan_frontend_apis() -> Dict[str, List[_FrontendApi]]:
    """扫描前端API文件，提取所有API定义"""
    frontend_api_dir = PROJECT_ROOT / "deepsearch/webui/frontend/src/api"
    apis: Dict[str, List[_FrontendApi]] = {}

    # 排除request.js
    exclude_files = ["request.js"]

    for api_file in frontend_api_dir.glob("*.js"):
        if api_file.name in exclude_files:
            continue

        module_name = api_file.stem
        apis[module_name] = []

        with open(api_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 匹配export function

        # 更宽松的匹配模式
        simple_pattern = (
            r'(?:url|URL)\s*:\s*[\'"`]([^\'"`]+)[\'"`].*?(?:method|METHOD)\s*:\s*[\'"`](\w+)[\'"`]'
        )

        # 先尝试找函数名
        func_matches = re.finditer(r"export\s+(?:async\s+)?function\s+(\w+)", content)
        func_positions = {m.group(1): m.start() for m in func_matches}

        # 找所有API调用
        for match in re.finditer(simple_pattern, content, re.DOTALL):
            url = match.group(1)
            method = match.group(2).upper()

            # 找最近的函数名
            pos = match.start()
            func_name = "unknown"
            for name, func_pos in func_positions.items():
                if func_pos < pos:
                    func_name = name

            apis[module_name].append(
                _FrontendApi(
                    function=func_name,
                    url=url,
                    method=method,
                    file=f"src/api/{api_file.name}",
                )
            )

    return apis


class _BackendApi(TypedDict):
    function: str
    path: str
    method: str
    file: str


def scan_backend_apis() -> Dict[str, List[_BackendApi]]:
    """扫描后端API文件，提取所有路由定义"""
    backend_api_dir = PROJECT_ROOT / "deepsearch/webui/api"
    apis: Dict[str, List[_BackendApi]] = {}

    for api_file in backend_api_dir.glob("*.py"):
        if api_file.name == "__init__.py":
            continue

        module_name = api_file.stem
        apis[module_name] = []

        with open(api_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 匹配路由装饰器
        route_pattern = r'@router\.(get|post|put|delete|patch)\s*\(\s*[\'"`]([^\'"`]+)[\'"`]'

        for match in re.finditer(route_pattern, content):
            method = match.group(1).upper()
            path = match.group(2)

            # 找下一个函数名
            func_pattern = r"(?:async\s+)?def\s+(\w+)\s*\("
            func_match = re.search(func_pattern, content[match.end() :])
            func_name = func_match.group(1) if func_match else "unknown"

            apis[module_name].append(
                _BackendApi(
                    function=func_name,
                    path=path,
                    method=method,
                    file=f"webui/api/{api_file.name}",
                )
            )

    return apis


def generate_frontend_doc(apis: Dict) -> str:
    """生成前端API文档"""
    doc = ["# 前端API接口文档\n"]
    doc.append(f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    doc.append("## 概述\n")
    doc.append("本文档记录了所有前端API接口定义。\n\n")

    # 统计
    total_apis = sum(len(module_apis) for module_apis in apis.values())
    doc.append(f"- 总模块数：{len(apis)}\n")
    doc.append(f"- 总接口数：{total_apis}\n\n")

    # 按模块分组
    for module, module_apis in sorted(apis.items()):
        doc.append(f"## {module}\n\n")
        doc.append(f"文件：`src/api/{module}.js`\n\n")

        doc.append("| 函数名 | 请求路径 | 方法 |\n")
        doc.append("|--------|----------|------|\n")

        for api in module_apis:
            doc.append(f"| {api['function']} | {api['url']} | {api['method']} |\n")

        doc.append("\n")

    return "".join(doc)


def generate_backend_doc(apis: Dict) -> str:
    """生成后端API文档"""
    doc = ["# 后端API接口文档\n"]
    doc.append(f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    doc.append("## 概述\n")
    doc.append("本文档记录了所有后端API路由定义。\n\n")

    # 统计
    total_apis = sum(len(module_apis) for module_apis in apis.values())
    doc.append(f"- 总模块数：{len(apis)}\n")
    doc.append(f"- 总接口数：{total_apis}\n\n")

    # 按模块分组
    for module, module_apis in sorted(apis.items()):
        doc.append(f"## {module}\n\n")
        doc.append(f"文件：`webui/api/{module}.py`\n\n")

        doc.append("| 函数名 | 路由路径 | 方法 |\n")
        doc.append("|--------|----------|------|\n")

        for api in module_apis:
            # 完整路径 = /api + 路由路径
            full_path = f"/api{api['path']}"
            doc.append(f"| {api['function']} | {full_path} | {api['method']} |\n")

        doc.append("\n")

    return "".join(doc)


def generate_mapping_doc(frontend_apis: Dict, backend_apis: Dict) -> str:
    """生成API映射关系文档"""
    doc = ["# API映射关系文档\n"]
    doc.append(f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    doc.append("## 概述\n")
    doc.append("本文档记录前端API与后端API的映射关系。\n\n")

    # 收集所有后端路由
    backend_routes = {}
    for module, module_apis in backend_apis.items():
        for api in module_apis:
            # 后端完整路径
            full_path = f"/api{api['path']}"
            key = f"{api['method']}:{full_path}"
            backend_routes[key] = {"module": module, "function": api["function"]}

    # 分析映射关系
    doc.append("## 映射关系表\n\n")
    doc.append("| 前端模块 | 前端函数 | 请求路径 | 方法 | 后端模块 | 后端函数 | 状态 |\n")
    doc.append("|----------|----------|----------|------|----------|----------|------|\n")

    unmatched_frontend = []
    matched_count = 0

    for module, module_apis in sorted(frontend_apis.items()):
        for api in module_apis:
            # 前端请求的完整路径
            frontend_path = api["url"]
            # 如果前端路径不以/api开头，则添加/api前缀
            if not frontend_path.startswith("/api"):
                full_path = f"/api{frontend_path}"
            else:
                full_path = frontend_path

            key = f"{api['method']}:{full_path}"

            if key in backend_routes:
                backend = backend_routes[key]
                status = "✅ 匹配"
                backend_module = backend["module"]
                backend_func = backend["function"]
                matched_count += 1
            else:
                status = "❌ 未匹配"
                backend_module = "-"
                backend_func = "-"
                unmatched_frontend.append(
                    {
                        "module": module,
                        "function": api["function"],
                        "path": api["url"],
                        "method": api["method"],
                    }
                )

            doc.append(
                f"| {module} | {api['function']} | {api['url']} | {api['method']} | {backend_module} | {backend_func} | {status} |\n"
            )

    doc.append("\n")

    # 统计
    doc.append("## 统计信息\n\n")
    total_frontend = sum(len(module_apis) for module_apis in frontend_apis.values())
    doc.append(f"- 前端接口总数：{total_frontend}\n")
    doc.append(f"- 后端接口总数：{len(backend_routes)}\n")
    doc.append(f"- 匹配成功：{matched_count}\n")
    doc.append(f"- 未匹配：{len(unmatched_frontend)}\n\n")

    # 问题接口
    if unmatched_frontend:
        doc.append("## ⚠️ 需要修复的接口\n\n")
        doc.append("以下前端接口在后端没有找到对应的路由：\n\n")

        for item in unmatched_frontend:
            doc.append(
                f"- **{item['module']}.{item['function']}**: `{item['method']} {item['path']}`\n"
            )

    return "".join(doc)


def main():
    """主函数"""
    print("开始扫描API接口...")

    # 扫描前端API
    print("扫描前端API...")
    frontend_apis = scan_frontend_apis()

    # 扫描后端API
    print("扫描后端API...")
    backend_apis = scan_backend_apis()

    # 生成文档
    docs_dir = PROJECT_ROOT / "docs/api"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # 前端API文档
    frontend_doc = generate_frontend_doc(frontend_apis)
    frontend_doc_path = docs_dir / "FRONTEND_API_REGISTRY.md"
    with open(frontend_doc_path, "w", encoding="utf-8") as f:
        f.write(frontend_doc)
    print(f"前端API文档已生成：{frontend_doc_path}")

    # 后端API文档
    backend_doc = generate_backend_doc(backend_apis)
    backend_doc_path = docs_dir / "BACKEND_API_REGISTRY.md"
    with open(backend_doc_path, "w", encoding="utf-8") as f:
        f.write(backend_doc)
    print(f"后端API文档已生成：{backend_doc_path}")

    # 映射关系文档
    mapping_doc = generate_mapping_doc(frontend_apis, backend_apis)
    mapping_doc_path = docs_dir / "API_MAPPING.md"
    with open(mapping_doc_path, "w", encoding="utf-8") as f:
        f.write(mapping_doc)
    print(f"映射关系文档已生成：{mapping_doc_path}")

    print("\n所有文档生成完成！")


if __name__ == "__main__":
    main()
