"""
DeepSearch 数据源综合验证工具

用于验证所有数据源的连接性、性能和数据质量
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from deepsearch.config import get_config


@dataclass
class ValidationResult:
    """验证结果"""
    source_name: str
    is_available: bool
    latency_ms: float
    error_message: Optional[str] = None
    test_results: Dict[str, Any] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.test_results is None:
            self.test_results = {}


class DataSourceValidator:
    """数据源验证器"""
    
    def __init__(self):
        self.config = get_config()
        self.results = []
        self.test_symbol = "000001"  # 测试用股票代码
        
    async def validate_amazingdata(self) -> ValidationResult:
        """验证AmazingData数据源"""
        logger.info("验证 AmazingData 数据源...")
        start_time = time.time()
        
        try:
            # 检查是否安装了AmazingData SDK
            try:
                from amazingdata.datafeeds import BaseData, MarketData
                has_sdk = True
            except ImportError:
                has_sdk = False
                raise Exception("AmazingData SDK未安装")
            
            # 测试连接
            if has_sdk and self.config.amazingdata.enabled:
                base_data = BaseData()
                base_data.login(
                    username=self.config.amazingdata.connection.username,
                    password=self.config.amazingdata.connection.password,
                    ip=self.config.amazingdata.connection.host,
                    port=self.config.amazingdata.connection.port
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
                        "has_quote_data": quote is not None
                    }
                )
            else:
                raise Exception("AmazingData未启用")
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ValidationResult(
                source_name="AmazingData",
                is_available=False,
                latency_ms=latency,
                error_message=str(e),
                test_results={"sdk_installed": has_sdk if 'has_sdk' in locals() else False}
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
                    asyncio.open_connection('127.0.0.1', 9999),
                    timeout=5.0
                )
                writer.close()
                await writer.wait_closed()
                tcp_available = True
                tcp_latency = (time.time() - tcp_test_start) * 1000
            except:
                tcp_available = False
                tcp_latency = 5000
            
            # 测试WebSocket连接
            ws_test_start = time.time()
            ws_available = False
            ws_latency = 5000
            
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(
                        'ws://127.0.0.1:9998',
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as ws:
                        ws_available = True
                        ws_latency = (time.time() - ws_test_start) * 1000
                        await ws.close()
            except:
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
                    "websocket_latency_ms": ws_latency
                }
            )
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ValidationResult(
                source_name="QMT",
                is_available=False,
                latency_ms=latency,
                error_message=str(e)
            )
    
    async def validate_cloudflare(self) -> ValidationResult:
        """验证CloudFlare Workers代理"""
        logger.info("验证 CloudFlare Workers 代理...")
        start_time = time.time()
        
        try:
            import aiohttp
            
            proxy_url = self.config.cloudflare_workers.url
            
            # 测试连接
            async with aiohttp.ClientSession() as session:
                # 测试健康检查端点
                health_start = time.time()
                async with session.get(
                    f"{proxy_url}/health",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    health_status = resp.status == 200
                    health_latency = (time.time() - health_start) * 1000
                
                # 测试数据获取
                data_start = time.time()
                test_params = {
                    "action": "stock_zh_a_spot_em",
                    "params": {}
                }
                
                async with session.post(
                    proxy_url,
                    json=test_params,
                    timeout=aiohttp.ClientTimeout(total=15)
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
                    "has_response_data": bool(response_data) if 'response_data' in locals() else False
                }
            )
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ValidationResult(
                source_name="CloudFlare",
                is_available=False,
                latency_ms=latency,
                error_message=str(e)
            )
    
    async def validate_akshare_direct(self) -> ValidationResult:
        """验证AKShare直连"""
        logger.info("验证 AKShare 直连...")
        start_time = time.time()
        
        try:
            import akshare as ak
            
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
                adjust=""
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
                    "kline_latency_ms": kline_latency
                }
            )
            
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ValidationResult(
                source_name="AKShare_Direct",
                is_available=False,
                latency_ms=latency,
                error_message=str(e)
            )
    
    async def validate_database_connections(self) -> ValidationResult:
        """验证数据库连接"""
        logger.info("验证数据库连接...")
        start_time = time.time()
        
        test_results = {}
        all_available = True
        errors = []
        
        # 测试PostgreSQL
        if self.config.database.main.enabled:
            try:
                import asyncpg
                pg_start = time.time()
                conn = await asyncpg.connect(
                    host=self.config.database.main.host,
                    port=self.config.database.main.port,
                    database=self.config.database.main.database,
                    user=self.config.database.main.username,
                    password=self.config.database.main.password
                )
                await conn.close()
                test_results["postgresql"] = {
                    "available": True,
                    "latency_ms": (time.time() - pg_start) * 1000
                }
            except Exception as e:
                test_results["postgresql"] = {
                    "available": False,
                    "error": str(e)
                }
                all_available = False
                errors.append(f"PostgreSQL: {e}")
        
        # 测试Redis
        if self.config.database.cache.enabled:
            try:
                import redis.asyncio as aioredis
                redis_start = time.time()
                redis_client = await aioredis.from_url(
                    f"redis://{self.config.database.cache.host}:{self.config.database.cache.port}",
                    password=self.config.database.cache.password or None,
                    db=self.config.database.cache.db
                )
                await redis_client.ping()
                await redis_client.close()
                test_results["redis"] = {
                    "available": True,
                    "latency_ms": (time.time() - redis_start) * 1000
                }
            except Exception as e:
                test_results["redis"] = {
                    "available": False,
                    "error": str(e)
                }
                all_available = False
                errors.append(f"Redis: {e}")
        
        # 测试DuckDB
        if self.config.database.analytics.enabled:
            try:
                import duckdb
                duckdb_start = time.time()
                conn = duckdb.connect(self.config.database.analytics.path)
                conn.execute("SELECT 1").fetchall()
                conn.close()
                test_results["duckdb"] = {
                    "available": True,
                    "latency_ms": (time.time() - duckdb_start) * 1000
                }
            except Exception as e:
                test_results["duckdb"] = {
                    "available": False,
                    "error": str(e)
                }
                all_available = False
                errors.append(f"DuckDB: {e}")
        
        latency = (time.time() - start_time) * 1000
        
        return ValidationResult(
            source_name="Database",
            is_available=all_available,
            latency_ms=latency,
            error_message="; ".join(errors) if errors else None,
            test_results=test_results
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
            self.validate_database_connections()
        ]
        
        self.results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        for i, result in enumerate(self.results):
            if isinstance(result, Exception):
                self.results[i] = ValidationResult(
                    source_name=f"Unknown_{i}",
                    is_available=False,
                    latency_ms=0,
                    error_message=str(result)
                )
        
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
                "average_latency_ms": sum(r.latency_ms for r in self.results) / total_count if total_count > 0 else 0
            },
            "sources": [asdict(r) for r in self.results],
            "recommendations": self.generate_recommendations()
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
                        "python deepsearch/datafeed/qmt/scripts/qmt_collector_prod.py"
                    )
                elif result.source_name == "AmazingData":
                    recommendations.append(
                        "检查AmazingData SDK安装和认证信息: "
                        "pip install AmazingData-1.0.4-cp313-none-any.whl"
                    )
                elif result.source_name == "CloudFlare":
                    recommendations.append(
                        "检查CloudFlare Workers部署状态和网络连接"
                    )
            elif result.latency_ms > 1000:
                recommendations.append(
                    f"优化{result.source_name}的响应延迟 (当前: {result.latency_ms:.0f}ms)"
                )
        
        return recommendations
    
    def print_summary(self):
        """打印验证摘要"""
        print("\n" + "="*60)
        print("DeepSearch 数据源验证报告")
        print("="*60)
        print(f"验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*60)
        
        for result in self.results:
            status = "✅" if result.is_available else "❌"
            print(f"{status} {result.source_name:20} | "
                  f"延迟: {result.latency_ms:7.1f}ms | "
                  f"{'正常' if result.is_available else f'错误: {result.error_message}'}")
        
        print("-"*60)
        available = sum(1 for r in self.results if r.is_available)
        total = len(self.results)
        print(f"总体可用性: {available}/{total} ({available/total*100:.1f}%)")
        
        if recommendations := self.generate_recommendations():
            print("\n优化建议:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
        
        print("="*60)


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
    report_file = f"./data/monitoring/validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    
    with open(report_file, 'w', encoding='utf-8') as f:
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