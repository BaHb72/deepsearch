#!/usr/bin/env python
"""
API 文档自动生成工具
扫描前后端代码，生成完整的 API 文档
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml
from loguru import logger

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 导入编码处理工具
from deepsearch.core.utils.file_encoding import (
    SafeFileHandler,
    PlatformEncodingHelper,
    safe_open
)
BACKEND_DIR = PROJECT_ROOT / "deepsearch" / "webui"
FRONTEND_DIR = PROJECT_ROOT / "deepsearch" / "webui" / "frontend" / "src"
DOCS_DIR = PROJECT_ROOT / "docs" / "api"


class ApiEndpoint:
    """API 端点信息"""
    
    def __init__(self):
        self.path: str = ""
        self.method: str = ""
        self.name: str = ""
        self.description: str = ""
        self.category: str = ""
        self.file_path: str = ""
        self.line_number: int = 0
        self.params: List[Dict] = []
        self.response: Dict = {}
        self.requires_auth: bool = False
        self.deprecated: bool = False
        self.frontend_usage: List[str] = []
        self.backend_impl: str = ""
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "path": self.path,
            "method": self.method,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "params": self.params,
            "response": self.response,
            "requires_auth": self.requires_auth,
            "deprecated": self.deprecated,
            "frontend_usage": self.frontend_usage,
            "backend_impl": self.backend_impl
        }
    
    def __repr__(self):
        return f"<ApiEndpoint {self.method} {self.path}>"


class ApiDocumentGenerator:
    """API 文档生成器"""
    
    def __init__(self):
        self.endpoints: List[ApiEndpoint] = []
        self.frontend_apis: Dict[str, List[str]] = {}
        self.backend_routes: Dict[str, ApiEndpoint] = {}
        
    def scan_backend(self):
        """扫描后端 API 路由"""
        logger.info("扫描后端 API 路由...")
        
        # 扫描所有 Python 文件
        for py_file in BACKEND_DIR.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            
            self._parse_python_file(py_file)
    
    def _parse_python_file(self, file_path: Path):
        """解析 Python 文件中的路由定义"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")
            
            # 查找路由装饰器
            router_patterns = [
                r'@router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                r'@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            ]
            
            for i, line in enumerate(lines):
                for pattern in router_patterns:
                    match = re.search(pattern, line)
                    if match:
                        endpoint = self._extract_endpoint_info(
                            lines, i, match.group(1), match.group(2), file_path
                        )
                        if endpoint:
                            self.endpoints.append(endpoint)
                            key = f"{endpoint.method}:{endpoint.path}"
                            self.backend_routes[key] = endpoint
                            
        except Exception as e:
            logger.error(f"解析文件 {file_path} 失败: {e}")
    
    def _extract_endpoint_info(
        self, lines: List[str], start_line: int, method: str, path: str, file_path: Path
    ) -> Optional[ApiEndpoint]:
        """提取端点信息"""
        endpoint = ApiEndpoint()
        endpoint.method = method.upper()
        endpoint.path = path
        endpoint.file_path = str(file_path.relative_to(PROJECT_ROOT))
        endpoint.line_number = start_line + 1
        
        # 查找函数定义
        for i in range(start_line + 1, min(start_line + 10, len(lines))):
            if lines[i].strip().startswith("def "):
                func_match = re.match(r"def\s+(\w+)\s*\(", lines[i].strip())
                if func_match:
                    endpoint.name = func_match.group(1)
                    
                # 提取文档字符串
                for j in range(i + 1, min(i + 20, len(lines))):
                    if '"""' in lines[j] or "'''" in lines[j]:
                        doc_start = j
                        doc_end = j
                        for k in range(j + 1, min(j + 30, len(lines))):
                            if '"""' in lines[k] or "'''" in lines[k]:
                                doc_end = k
                                break
                        
                        doc_lines = lines[doc_start:doc_end + 1]
                        endpoint.description = self._parse_docstring(doc_lines)
                        break
                break
        
        # 检查是否需要认证
        endpoint.requires_auth = self._check_auth_required(lines, start_line)
        
        # 提取分类
        endpoint.category = self._extract_category(file_path)
        
        return endpoint
    
    def _parse_docstring(self, lines: List[str]) -> str:
        """解析文档字符串"""
        doc = []
        for line in lines:
            cleaned = line.strip().replace('"""', "").replace("'''", "")
            if cleaned:
                doc.append(cleaned)
        return " ".join(doc[:2]) if doc else ""  # 只取前两行作为描述
    
    def _check_auth_required(self, lines: List[str], start_line: int) -> bool:
        """检查是否需要认证"""
        # 查找附近的认证装饰器
        for i in range(max(0, start_line - 5), min(start_line + 5, len(lines))):
            if "require_auth" in lines[i] or "Depends(get_current_user)" in lines[i]:
                return True
        return False
    
    def _extract_category(self, file_path: Path) -> str:
        """根据文件路径提取分类"""
        path_str = str(file_path)
        
        categories = {
            "system": "系统管理",
            "database": "数据库",
            "market": "市场数据",
            "trading": "交易",
            "monitor": "监控",
            "data_source": "数据源",
            "data-source": "数据源",
            "qmt": "QMT集成",
            "strategy": "策略",
            "backtest": "回测"
        }
        
        for key, value in categories.items():
            if key in path_str.lower():
                return value
        
        return "其他"
    
    def scan_frontend(self):
        """扫描前端 API 调用"""
        logger.info("扫描前端 API 调用...")
        
        # 扫描所有 JavaScript/TypeScript 文件
        for ext in ["*.js", "*.jsx", "*.ts", "*.tsx"]:
            for js_file in FRONTEND_DIR.rglob(ext):
                if "node_modules" in str(js_file):
                    continue
                
                self._parse_frontend_file(js_file)
    
    def _parse_frontend_file(self, file_path: Path):
        """解析前端文件中的 API 调用"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 查找 API 调用模式
            patterns = [
                # request({ url: '/path', method: 'method' }) 格式
                r'url\s*:\s*[\'"`]([^\'"`]+)[\'"`]',
                # request('/path') 格式
                r'request\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
                # axios 调用格式
                r'axios\.\w+\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
                # fetch 调用格式
                r'fetch\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
                # HTTP方法直接调用格式
                r'(?:get|post|put|delete|patch)\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
            ]

            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if match and match.startswith("/"):
                        # 清理URL，移除模板变量部分进行标准化
                        clean_url = self._normalize_url(match)
                        rel_path = str(file_path.relative_to(PROJECT_ROOT))
                        if clean_url not in self.frontend_apis:
                            self.frontend_apis[clean_url] = []
                        self.frontend_apis[clean_url].append(rel_path)

        except Exception as e:
            logger.error(f"解析前端文件 {file_path} 失败: {e}")

    def _normalize_url(self, url: str) -> str:
        """标准化URL，处理模板变量"""
        # 移除查询参数
        if '?' in url:
            url = url.split('?')[0]

        # 将模板变量 ${var} 转换为 {var}
        url = re.sub(r'\$\{([^}]+)\}', r'{\1}', url)

        # 处理路径参数（如 :id -> {id}）
        url = re.sub(r':(\w+)', r'{\1}', url)

        return url
    
    def match_frontend_backend(self):
        """匹配前后端 API"""
        logger.info("匹配前后端 API...")

        for endpoint in self.endpoints:
            # 构建可能的完整路径
            full_paths = []

            # 添加原始路径
            full_paths.append(endpoint.path)

            # 从文件路径推断可能的前缀
            file_parts = endpoint.file_path.split('/')
            if 'endpoints' in file_parts:
                endpoints_index = file_parts.index('endpoints')
                if endpoints_index + 1 < len(file_parts):
                    category = file_parts[endpoints_index + 1]
                    # 添加带前缀的路径
                    full_paths.append(f"/api/{category}{endpoint.path}")
                    full_paths.append(f"/{category}{endpoint.path}")

            # 通用API前缀
            full_paths.append(f"/api{endpoint.path}")

            # 查找前端使用
            for api_path, files in self.frontend_apis.items():
                for full_path in full_paths:
                    if self._paths_match(api_path, full_path):
                        endpoint.frontend_usage.extend(files)
                        break

    def _paths_match(self, frontend_path: str, backend_path: str) -> bool:
        """检查前后端路径是否匹配"""
        # 直接匹配
        if frontend_path == backend_path:
            return True

        # 参数化路径匹配 (处理 {id} 等参数)
        frontend_pattern = re.sub(r'\{[^}]+\}', r'[^/]+', frontend_path)
        backend_pattern = re.sub(r'\{[^}]+\}', r'[^/]+', backend_path)

        if re.match(f"^{frontend_pattern}$", backend_path) or re.match(f"^{backend_pattern}$", frontend_path):
            return True

        # 后缀匹配（处理前缀差异）
        if frontend_path.endswith(backend_path) or backend_path.endswith(frontend_path):
            return True

        return False
    
    def generate_documentation(self):
        """生成文档"""
        logger.info("生成 API 文档...")
        
        # 确保文档目录存在
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        
        # 生成主文档
        self._generate_main_doc()
        
        # 生成分类文档
        self._generate_category_docs()
        
        # 生成 OpenAPI 规范
        self._generate_openapi_spec()
        
        # 生成前端 API 映射
        self._generate_frontend_mapping()
        
        # 生成统计报告
        self._generate_statistics()
    
    def _generate_main_doc(self):
        """生成主文档"""
        doc_path = DOCS_DIR / "README.md"

        # 构建文档内容
        content = []
        content.append("# API 文档\n\n")
        content.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        content.append(f"总计 API 端点: {len(self.endpoints)}\n\n")

        # 按分类分组
        categories = {}
        for endpoint in self.endpoints:
            if endpoint.category not in categories:
                categories[endpoint.category] = []
            categories[endpoint.category].append(endpoint)

        content.append("## API 分类\n\n")
        for category, endpoints in sorted(categories.items()):
            content.append(f"### {category} ({len(endpoints)} 个)\n\n")
            content.append("| 方法 | 路径 | 描述 | 前端使用 |\n")
            content.append("|------|------|------|----------|\n")

            for ep in sorted(endpoints, key=lambda x: x.path):
                usage = "✓" if ep.frontend_usage else "✗"
                desc = ep.description[:50] + "..." if len(ep.description) > 50 else ep.description
                content.append(f"| {ep.method} | {ep.path} | {desc} | {usage} |\n")

            content.append("\n")

        # 使用安全文件写入
        SafeFileHandler.write_file(doc_path, ''.join(content))
    
    def _generate_category_docs(self):
        """生成分类文档"""
        categories = {}
        for endpoint in self.endpoints:
            if endpoint.category not in categories:
                categories[endpoint.category] = []
            categories[endpoint.category].append(endpoint)

        for category, endpoints in categories.items():
            safe_name = re.sub(r'[^\w\s-]', '', category).strip().replace(' ', '_')
            doc_path = DOCS_DIR / f"{safe_name}.md"

            # 构建文档内容
            content = []
            content.append(f"# {category} API\n\n")

            for ep in sorted(endpoints, key=lambda x: x.path):
                content.append(f"## {ep.method} {ep.path}\n\n")

                if ep.description:
                    content.append(f"**描述**: {ep.description}\n\n")

                content.append(f"**文件**: `{ep.file_path}:{ep.line_number}`\n\n")

                if ep.requires_auth:
                    content.append("**认证**: 需要\n\n")

                if ep.frontend_usage:
                    content.append("**前端使用**:\n")
                    for file in ep.frontend_usage[:5]:  # 只显示前5个
                        content.append(f"- `{file}`\n")
                    if len(ep.frontend_usage) > 5:
                        content.append(f"- ... 还有 {len(ep.frontend_usage) - 5} 个文件\n")
                    content.append("\n")

                content.append("---\n\n")

            # 使用安全文件写入
            SafeFileHandler.write_file(doc_path, ''.join(content))
    
    def _generate_openapi_spec(self):
        """生成 OpenAPI 规范"""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "DeepSearch API",
                "version": "1.0.0",
                "description": "量化交易系统 API"
            },
            "servers": [
                {"url": "http://localhost:8000/api", "description": "开发服务器"}
            ],
            "paths": {}
        }
        
        for endpoint in self.endpoints:
            if endpoint.path not in spec["paths"]:
                spec["paths"][endpoint.path] = {}
            
            spec["paths"][endpoint.path][endpoint.method.lower()] = {
                "summary": endpoint.name,
                "description": endpoint.description,
                "tags": [endpoint.category],
                "responses": {
                    "200": {"description": "成功"},
                    "400": {"description": "请求错误"},
                    "500": {"description": "服务器错误"}
                }
            }
            
            if endpoint.requires_auth:
                spec["paths"][endpoint.path][endpoint.method.lower()]["security"] = [
                    {"bearerAuth": []}
                ]
        
        spec_path = DOCS_DIR / "openapi.json"
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
    
    def _generate_frontend_mapping(self):
        """生成前端 API 映射"""
        mapping_path = DOCS_DIR / "frontend_mapping.md"
        
        with open(mapping_path, "w", encoding="utf-8") as f:
            f.write("# 前端 API 使用映射\n\n")
            
            # 未使用的后端 API
            unused_apis = [ep for ep in self.endpoints if not ep.frontend_usage]
            if unused_apis:
                f.write("## ⚠️ 未使用的后端 API\n\n")
                for ep in unused_apis:
                    f.write(f"- {ep.method} {ep.path} ({ep.file_path}:{ep.line_number})\n")
                f.write("\n")
            
            # 未匹配的前端调用
            unmatched_calls = []
            for api_path in self.frontend_apis:
                matched = False
                for ep in self.endpoints:
                    if api_path == ep.path or api_path.endswith(ep.path):
                        matched = True
                        break
                if not matched:
                    unmatched_calls.append(api_path)
            
            if unmatched_calls:
                f.write("## ⚠️ 未匹配的前端 API 调用\n\n")
                for path in sorted(unmatched_calls):
                    files = self.frontend_apis[path]
                    f.write(f"- {path}\n")
                    for file in files[:3]:
                        f.write(f"  - {file}\n")
                f.write("\n")
    
    def _generate_statistics(self):
        """生成统计报告"""
        stats_path = DOCS_DIR / "statistics.md"
        
        # 统计数据
        total_endpoints = len(self.endpoints)
        used_endpoints = len([ep for ep in self.endpoints if ep.frontend_usage])
        unused_endpoints = total_endpoints - used_endpoints
        
        categories = {}
        for ep in self.endpoints:
            if ep.category not in categories:
                categories[ep.category] = {"total": 0, "used": 0}
            categories[ep.category]["total"] += 1
            if ep.frontend_usage:
                categories[ep.category]["used"] += 1
        
        methods = {}
        for ep in self.endpoints:
            if ep.method not in methods:
                methods[ep.method] = 0
            methods[ep.method] += 1
        
        with open(stats_path, "w", encoding="utf-8") as f:
            f.write("# API 统计报告\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## 总体统计\n\n")
            f.write(f"- 总端点数: {total_endpoints}\n")
            f.write(f"- 已使用: {used_endpoints} ({used_endpoints/total_endpoints*100:.1f}%)\n")
            f.write(f"- 未使用: {unused_endpoints} ({unused_endpoints/total_endpoints*100:.1f}%)\n\n")
            
            f.write("## 分类统计\n\n")
            f.write("| 分类 | 总数 | 已使用 | 使用率 |\n")
            f.write("|------|------|--------|--------|\n")
            for cat, stats in sorted(categories.items()):
                usage_rate = stats["used"] / stats["total"] * 100
                f.write(f"| {cat} | {stats['total']} | {stats['used']} | {usage_rate:.1f}% |\n")
            
            f.write("\n## 方法统计\n\n")
            for method, count in sorted(methods.items()):
                f.write(f"- {method}: {count}\n")
    
    def run(self):
        """运行文档生成器"""
        logger.info("开始生成 API 文档...")
        
        # 扫描后端
        self.scan_backend()
        logger.info(f"发现 {len(self.endpoints)} 个后端 API 端点")
        
        # 扫描前端
        self.scan_frontend()
        logger.info(f"发现 {len(self.frontend_apis)} 个前端 API 调用")
        
        # 匹配前后端
        self.match_frontend_backend()
        
        # 生成文档
        self.generate_documentation()
        
        logger.info(f"API 文档已生成到: {DOCS_DIR}")


def main():
    """主函数"""
    generator = ApiDocumentGenerator()
    generator.run()


if __name__ == "__main__":
    main()