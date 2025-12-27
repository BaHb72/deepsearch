"""
DeepSearch 数据源综合验证工具

用于验证所有数据源的连接性、性能和数据质量
"""

import asyncio
import importlib
import importlib.util
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

from deepsearch.config import get_config
from deepsearch.infrastructure.persistence.duckdb_path import resolve_duckdb_path


def _import_optional(module_name: str) -> Any:
    """以 Any 形式加载可选依赖，便于在缺失类型桩时降级处理。"""

    return importlib.import_module(module_name)


async def _await_callable(call: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
    """帮助等待一个声明为 Awaitable 的可调用对象，统一类型推断。"""

    return await call(*args, **kwargs)


async def _await_if_awaitable(result: Any) -> None:
    """若返回值可等待则等待执行，用于兼容 sync/async 混合接口。"""

    if hasattr(result, "__await__"):
        await cast(Awaitable[Any], result)


@dataclass
class ValidationResult:
    """验证结果"""

    source_name: str
    is_available: bool
    latency_ms: float
    error_message: Optional[str] = None
    test_results: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class DataSourceValidator:
    """数据源验证器"""

    def __init__(self):
        self.config: Any = get_config()
        self.results: List[ValidationResult] = []
        self.test_symbol = "000001"  # 测试用股票代码

    async def validate_amazingdata(self) -> ValidationResult:
        """验证AmazingData数据源"""
        logger.info("验证 AmazingData 数据源...")
        start_time = time.time()
        has_sdk: bool = False

        try:
            amazingdata_cfg = getattr(self.config, "amazingdata", None)
            if amazingdata_cfg is None:
                raise RuntimeError("未在配置中找到 AmazingData 段")

            if not getattr(amazingdata_cfg, "enabled", False):
                raise RuntimeError("AmazingData未启用")

            connection = getattr(amazingdata_cfg, "connection", None)
            if connection is None:
                raise RuntimeError("AmazingData 缺少连接配置")

            connection_data = cast(Any, connection)

            # 检查是否安装了AmazingData SDK
            sdk_spec = importlib.util.find_spec("amazingdata.datafeeds")
            if sdk_spec is None:
                raise ImportError("AmazingData SDK未安装")

            datafeeds = _import_optional("amazingdata.datafeeds")
            BaseData = getattr(datafeeds, "BaseData")
            MarketData = getattr(datafeeds, "MarketData")
            has_sdk = True

            # 测试连接
            base_data = BaseData()
            base_data.login(
                username=getattr(connection_data, "username", ""),
                password=getattr(connection_data, "password", ""),
                ip=getattr(connection_data, "host", ""),
                port=getattr(connection_data, "port", 0),
            )

            # 测试获取股票列表
            test_start = time.time()
            stock_list = base_data.get_all_stockcode()
            list_latency = (time.time() - test_start) * 1000

            # 测试获取实时行情
            market_data = MarketData()
            test_start = time.time()
            quote = market_data.get_quotes(self.test_symbol)
            quote_latency = (time.time() - test_start) * 1000

            # 登出
            base_data.logout()

            latency = (time.time() - start_time) * 1000

            return ValidationResult(
                source_name="AmazingData",
                is_available=True,
                latency_ms=latency,
                test_results={
                    "sdk_installed": True,
                    "login_success": True,
                    "stock_list_count": len(stock_list) if stock_list else 0,
                    "stock_list_latency_ms": list_latency,
                    "quote_latency_ms": quote_latency,
                    "has_quote_data": quote is not None,
                },
            )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ValidationResult(
                source_name="AmazingData",
                is_available=False,
                latency_ms=latency,
                error_message=str(e),
                test_results={"sdk_installed": has_sdk},
            )

    async def validate_qmt(self) -> ValidationResult:
        """验证QMT数据源"""
        logger.info("验证 QMT 数据源...")
        start_time = time.time()

        try:
            # 测试TCP连接
            tcp_test_start = time.time()
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", 9999), timeout=5.0
                )
                writer.close()
                await writer.wait_closed()
                tcp_available = True
                tcp_latency = (time.time() - tcp_test_start) * 1000
            except Exception:
                tcp_available = False
                tcp_latency = 5000.0

            # 测试WebSocket连接
            ws_test_start = time.time()
            ws_available = False
            ws_latency = 5000.0

            try:
                aiohttp = _import_optional("aiohttp")

                session_factory = cast(Any, aiohttp.ClientSession)
                session = session_factory()
                try:
                    timeout = aiohttp.ClientTimeout(total=5)
                    ws_connect = cast(Callable[..., Awaitable[Any]], getattr(session, "ws_connect"))
                    ws = await _await_callable(ws_connect, "ws://127.0.0.1:9998", timeout=timeout)
                    ws_available = True
                    ws_latency = (time.time() - ws_test_start) * 1000
                    close = getattr(ws, "close", None)
                    if callable(close):
                        await _await_if_awaitable(close())
                finally:
                    close_session = getattr(session, "close", None)
                    if callable(close_session):
                        await _await_if_awaitable(close_session())
            except Exception:
                pass

            latency = (time.time() - start_time) * 1000
            is_available = tcp_available or ws_available

            return ValidationResult(
                source_name="QMT",
                is_available=is_available,
                latency_ms=latency,
                error_message=None if is_available else "QMT服务未运行",
                test_results={
                    "tcp_available": tcp_available,
                    "tcp_port": 9999,
                    "tcp_latency_ms": tcp_latency,
                    "websocket_available": ws_available,
                    "websocket_port": 9998,
                    "websocket_latency_ms": ws_latency,
                },
            )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ValidationResult(
                source_name="QMT", is_available=False, latency_ms=latency, error_message=str(e)
            )

    async def validate_cloudflare(self) -> ValidationResult:
        """验证CloudFlare Workers代理"""
        logger.info("验证 CloudFlare Workers 代理...")
        start_time = time.time()

        try:
            cloudflare_cfg = getattr(self.config, "cloudflare_workers", None)
            if cloudflare_cfg is None:
                raise RuntimeError("未配置 Cloudflare Workers 代理")

            proxy_url = getattr(cloudflare_cfg, "url", None)
            if not proxy_url:
                raise RuntimeError("Cloudflare Workers 缺少可用的 url")

            aiohttp = _import_optional("aiohttp")

            # 测试连接
            async with aiohttp.ClientSession() as session:
                # 测试健康检查端点
                health_start = time.time()
                async with session.get(
                    f"{proxy_url}/health", timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    health_status = resp.status == 200
                    health_latency = (time.time() - health_start) * 1000

                # 测试数据获取
                data_start = time.time()
                test_params = {"action": "stock_zh_a_spot_em", "params": {}}

                async with session.post(
                    proxy_url, json=test_params, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    data_status = resp.status == 200
                    response_data = await resp.json()
                    data_latency = (time.time() - data_start) * 1000

            latency = (time.time() - start_time) * 1000

            return ValidationResult(
                source_name="CloudFlare",
                is_available=health_status and data_status,
                latency_ms=latency,
                test_results={
                    "proxy_url": proxy_url,
                    "health_check_success": health_status,
                    "health_latency_ms": health_latency,
                    "data_fetch_success": data_status,
                    "data_latency_ms": data_latency,
                    "has_response_data": (
                        bool(response_data) if "response_data" in locals() else False
                    ),
                },
            )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ValidationResult(
                source_name="CloudFlare",
                is_available=False,
                latency_ms=latency,
                error_message=str(e),
            )

    async def validate_akshare_direct(self) -> ValidationResult:
        """验证AKShare直连"""
        logger.info("验证 AKShare 直连...")
        start_time = time.time()

        try:
            ak = _import_optional("akshare")

            # 测试获取股票列表
            list_start = time.time()
            stock_list = ak.stock_zh_a_spot_em()
            list_latency = (time.time() - list_start) * 1000

            # 测试获取日线数据
            kline_start = time.time()
            kline_data = ak.stock_zh_a_hist(
                symbol=self.test_symbol,
                period="daily",
                start_date="20250801",
                end_date="20250824",
                adjust="",
            )
            kline_latency = (time.time() - kline_start) * 1000

            latency = (time.time() - start_time) * 1000

            return ValidationResult(
                source_name="AKShare_Direct",
                is_available=True,
                latency_ms=latency,
                test_results={
                    "stock_list_count": len(stock_list) if stock_list is not None else 0,
                    "stock_list_latency_ms": list_latency,
                    "kline_data_count": len(kline_data) if kline_data is not None else 0,
                    "kline_latency_ms": kline_latency,
                },
            )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ValidationResult(
                source_name="AKShare_Direct",
                is_available=False,
                latency_ms=latency,
                error_message=str(e),
            )

    async def validate_database_connections(self) -> ValidationResult:
        """验证数据库连接"""
        logger.info("验证数据库连接...")
        start_time = time.time()

        database_cfg = getattr(self.config, "database", None)
        if database_cfg is None:
            raise RuntimeError("未找到数据库配置")

        test_results: Dict[str, Any] = {}
        all_available = True
        errors = []

        # 测试PostgreSQL
        main_db = getattr(database_cfg, "main", None)
        if getattr(main_db, "enabled", False):
            try:
                asyncpg = _import_optional("asyncpg")

                pg_start = time.time()
                main_conn = cast(Any, main_db)
                conn = await asyncpg.connect(
                    host=getattr(main_conn, "host", ""),
                    port=getattr(main_conn, "port", 0),
                    database=getattr(main_conn, "database", ""),
                    user=getattr(main_conn, "username", ""),
                    password=getattr(main_conn, "password", ""),
                )
                await conn.close()
                test_results["postgresql"] = {
                    "available": True,
                    "latency_ms": (time.time() - pg_start) * 1000,
                }
            except Exception as e:
                test_results["postgresql"] = {"available": False, "error": str(e)}
                all_available = False
                errors.append(f"PostgreSQL: {e}")

        # 测试Redis
        cache_db = getattr(database_cfg, "cache", None)
        if getattr(cache_db, "enabled", False):
            try:
                aioredis = _import_optional("redis.asyncio")

                redis_start = time.time()
                cache_conn = cast(Any, cache_db)
                redis_client = aioredis.from_url(
                    f"redis://{getattr(cache_conn, 'host', '')}:{getattr(cache_conn, 'port', 0)}",
                    password=getattr(cache_conn, "password", None) or None,
                    db=getattr(cache_conn, "db", 0),
                )
                await redis_client.ping()
                await redis_client.close()
                test_results["redis"] = {
                    "available": True,
                    "latency_ms": (time.time() - redis_start) * 1000,
                }
            except Exception as e:
                test_results["redis"] = {"available": False, "error": str(e)}
                all_available = False
                errors.append(f"Redis: {e}")

        # 测试DuckDB
        analytics_db = getattr(database_cfg, "analytics", None)
        if getattr(analytics_db, "enabled", False):
            try:
                duckdb = _import_optional("duckdb")

                duckdb_start = time.time()
                analytics_conn = cast(Any, analytics_db)
                db_path = resolve_duckdb_path(getattr(analytics_conn, "path", ""))
                conn = duckdb.connect(db_path)
                conn.execute("SELECT 1").fetchall()
                conn.close()
                test_results["duckdb"] = {
                    "available": True,
                    "latency_ms": (time.time() - duckdb_start) * 1000,
                }
            except Exception as e:
                test_results["duckdb"] = {"available": False, "error": str(e)}
                all_available = False
                errors.append(f"DuckDB: {e}")

        latency = (time.time() - start_time) * 1000

        return ValidationResult(
            source_name="Database",
            is_available=all_available,
            latency_ms=latency,
            error_message="; ".join(errors) if errors else None,
            test_results=test_results,
        )

    async def run_all_validations(self) -> List[ValidationResult]:
        """运行所有验证"""
        logger.info("开始验证所有数据源...")

        # 并发执行所有验证
        tasks = [
            self.validate_amazingdata(),
            self.validate_qmt(),
            self.validate_cloudflare(),
            self.validate_akshare_direct(),
            self.validate_database_connections(),
        ]

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        normalized_results: List[ValidationResult] = []

        for index, result in enumerate(raw_results):
            if isinstance(result, ValidationResult):
                normalized_results.append(result)
                continue

            error_message = str(result)
            source_name = getattr(result, "source_name", None)
            normalized_results.append(
                ValidationResult(
                    source_name=source_name if isinstance(source_name, str) else f"Unknown_{index}",
                    is_available=False,
                    latency_ms=0,
                    error_message=error_message,
                )
            )

        self.results = normalized_results

        return self.results

    def generate_report(self) -> Dict[str, Any]:
        """生成验证报告"""
        available_count = sum(1 for r in self.results if r.is_available)
        total_count = len(self.results)

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_sources": total_count,
                "available_sources": available_count,
                "availability_rate": available_count / total_count if total_count > 0 else 0,
                "average_latency_ms": (
                    sum(r.latency_ms for r in self.results) / total_count if total_count > 0 else 0
                ),
            },
            "sources": [asdict(r) for r in self.results],
            "recommendations": self.generate_recommendations(),
        }

        return report

    def generate_recommendations(self) -> List[str]:
        """生成优化建议"""
        recommendations = []

        for result in self.results:
            if not result.is_available:
                if result.source_name == "QMT":
                    recommendations.append(
                        "启动QMT终端并运行数据收集脚本: "
                        "python deepsearch/infrastructure/providers/datafeed/qmt/scripts/qmt_collector.py"
                    )
                elif result.source_name == "AmazingData":
                    recommendations.append(
                        "检查AmazingData SDK安装和认证信息: "
                        "pip install AmazingData-1.0.4-cp313-none-any.whl"
                    )
                elif result.source_name == "CloudFlare":
                    recommendations.append("检查CloudFlare Workers部署状态和网络连接")
            elif result.latency_ms > 1000:
                recommendations.append(
                    f"优化{result.source_name}的响应延迟 (当前: {result.latency_ms:.0f}ms)"
                )

        return recommendations

    def print_summary(self):
        """打印验证摘要"""
        print("\n" + "=" * 60)
        print("DeepSearch 数据源验证报告")
        print("=" * 60)
        print(f"验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)

        for result in self.results:
            status = "✅" if result.is_available else "❌"
            print(
                f"{status} {result.source_name:20} | "
                f"延迟: {result.latency_ms:7.1f}ms | "
                f"{'正常' if result.is_available else f'错误: {result.error_message}'}"
            )

        print("-" * 60)
        available = sum(1 for r in self.results if r.is_available)
        total = len(self.results)
        print(f"总体可用性: {available}/{total} ({available/total*100:.1f}%)")

        if recommendations := self.generate_recommendations():
            print("\n优化建议:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")

        print("=" * 60)


async def main():
    """主函数"""
    validator = DataSourceValidator()

    # 运行验证
    await validator.run_all_validations()

    # 打印摘要
    validator.print_summary()

    # 生成详细报告
    report = validator.generate_report()

    # 保存报告
    report_file = (
        f"./data/monitoring/validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    os.makedirs(os.path.dirname(report_file), exist_ok=True)

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n详细报告已保存至: {report_file}")

    # 返回退出码
    all_available = all(r.is_available for r in validator.results)
    return 0 if all_available else 1


if __name__ == "__main__":
    # 设置日志
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

    # 运行验证
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
