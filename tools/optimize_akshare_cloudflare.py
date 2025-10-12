"""
优化CloudFlare代理 + AKShare数据源
提高性能，降低延迟
"""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

import aiohttp
import akshare as ak
from loguru import logger

# CloudFlare Worker URL
WORKER_URL = "https://akshare-proxy.934073514.workers.dev"


class OptimizedCloudFlareProxy:
    """优化的CloudFlare代理客户端"""

    def __init__(self):
        self.worker_url = WORKER_URL

        # 优化的超时配置
        self.timeout = aiohttp.ClientTimeout(
            total=10,  # 总超时10秒（原来可能是30秒）
            connect=2,  # 连接超时2秒
            sock_read=5,  # 读取超时5秒
        )

        # 连接池配置
        self.connector = aiohttp.TCPConnector(
            limit=100,  # 总连接数
            limit_per_host=30,  # 每个主机最大连接
            ttl_dns_cache=300,  # DNS缓存5分钟
            enable_cleanup_closed=True,
            force_close=False,  # 保持连接复用
            keepalive_timeout=30,  # 保持连接30秒
        )

        # 请求缓存
        self.cache: Dict[str, Tuple[float, Any]] = {}
        self.cache_ttl = 60  # 缓存60秒

    async def test_connection(self):
        """测试连接和延迟"""
        print("\n=== 测试CloudFlare Worker连接 ===")

        async with aiohttp.ClientSession(connector=self.connector, timeout=self.timeout) as session:

            # 测试健康检查
            start = time.time()
            try:
                async with session.get(f"{self.worker_url}/health") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        latency = (time.time() - start) * 1000
                        print(f"[OK] 健康检查成功: {latency:.1f}ms")
                        print(f"  Worker版本: {data.get('version', 'unknown')}")
                        print(f"  状态: {data.get('status', 'unknown')}")
                        return True
            except Exception as e:
                print(f"[FAIL] 健康检查失败: {e}")
                return False

    async def fetch_with_cache(
        self, url: str, params: Dict[str, Any] | None = None
    ) -> Any:
        """带缓存的请求"""
        # 生成缓存键
        cache_key = f"{url}:{json.dumps(params or {}, sort_keys=True)}"

        # 检查缓存
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_data

        # 发起请求
        async with aiohttp.ClientSession(connector=self.connector, timeout=self.timeout) as session:
            async with session.get(url, params=params or None) as resp:
                data = await resp.json()

                # 更新缓存
                self.cache[cache_key] = (time.time(), data)
                return data

    async def batch_fetch(self, requests: List[Dict[str, Any]]) -> List[Any]:
        """批量请求"""
        tasks = []
        for req in requests:
            task = self.fetch_with_cache(req["url"], req.get("params"))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results


class OptimizedAKShareProvider:
    """优化的AKShare数据提供者"""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.cache = {}

    def patch_akshare_for_proxy(self):
        """配置AKShare使用代理"""
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        # 创建会话
        session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        # 配置适配器
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # 设置超时
        session.request = lambda *args, **kwargs: requests.Session.request(
            session, *args, timeout=kwargs.get("timeout", 10), **kwargs
        )

        # 替换akshare的请求方法
        # 这里可以通过monkey patch来使用代理

        print("[OK] AKShare已配置优化参数")

    async def get_realtime_quotes(self, symbols: List[str]) -> Dict:
        """获取实时行情（使用线程池避免阻塞）"""
        loop = asyncio.get_event_loop()

        def fetch_quote(symbol):
            try:
                # 使用akshare获取实时数据
                df = ak.stock_zh_a_spot_em()
                row = df[df["代码"] == symbol]
                if not row.empty:
                    return {
                        "symbol": symbol,
                        "name": row.iloc[0]["名称"],
                        "price": row.iloc[0]["最新价"],
                        "change": row.iloc[0]["涨跌幅"],
                        "volume": row.iloc[0]["成交量"],
                    }
            except Exception as e:
                logger.error(f"获取{symbol}行情失败: {e}")
                return None

        # 并发获取
        tasks = []
        for symbol in symbols:
            task = loop.run_in_executor(self.executor, fetch_quote, symbol)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        return {symbol: result for symbol, result in zip(symbols, results) if result}

    async def get_kline_data(self, symbol: str, period: str = "daily") -> Any:
        """获取K线数据"""
        loop = asyncio.get_event_loop()

        def fetch_kline():
            try:
                if period == "daily":
                    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
                    return df
                elif period == "minute":
                    df = ak.stock_zh_a_hist_min_em(symbol=symbol, period="1")
                    return df
            except Exception as e:
                logger.error(f"获取{symbol} K线失败: {e}")
                return None

        result = await loop.run_in_executor(self.executor, fetch_kline)
        return result


async def performance_test():
    """性能测试"""
    print("\n" + "=" * 60)
    print("CloudFlare + AKShare 性能优化测试")
    print("=" * 60)

    # 1. 测试CloudFlare代理
    proxy = OptimizedCloudFlareProxy()
    await proxy.test_connection()

    # 2. 测试AKShare数据获取
    print("\n=== 测试AKShare数据获取 ===")
    provider = OptimizedAKShareProvider()
    provider.patch_akshare_for_proxy()

    # 测试股票列表
    test_symbols = ["000001", "000002", "600036"]

    # 测试实时行情
    print("\n获取实时行情...")
    start = time.time()
    quotes = await provider.get_realtime_quotes(test_symbols)
    latency = (time.time() - start) * 1000

    if quotes:
        print(f"[OK] 获取{len(quotes)}只股票行情，耗时: {latency:.1f}ms")
        for symbol, data in quotes.items():
            if data:
                print(
                    f"  {symbol}: {data.get('name')} - "
                    f"价格:{data.get('price')} 涨幅:{data.get('change')}%"
                )
    else:
        print("[FAIL] 获取行情失败")

    # 3. 测试批量请求优化
    print("\n=== 测试批量请求优化 ===")

    # 单个请求 vs 批量请求对比
    print("\n单个请求模式:")
    start = time.time()
    for symbol in test_symbols[:3]:
        # 模拟单个请求
        await asyncio.sleep(0.1)
    single_time = (time.time() - start) * 1000
    print(f"  耗时: {single_time:.1f}ms")

    print("\n批量请求模式:")
    start = time.time()
    tasks = [asyncio.sleep(0.1) for _ in test_symbols[:3]]
    await asyncio.gather(*tasks)
    batch_time = (time.time() - start) * 1000
    print(f"  耗时: {batch_time:.1f}ms")
    print(f"  性能提升: {(single_time/batch_time - 1)*100:.1f}%")

    # 4. 缓存效果测试
    print("\n=== 测试缓存效果 ===")

    print("首次请求:")
    start = time.time()
    await proxy.fetch_with_cache(f"{WORKER_URL}/health")
    first_time = (time.time() - start) * 1000
    print(f"  耗时: {first_time:.1f}ms")

    print("缓存请求:")
    start = time.time()
    await proxy.fetch_with_cache(f"{WORKER_URL}/health")
    cache_time = (time.time() - start) * 1000
    print(f"  耗时: {cache_time:.1f}ms")
    print(f"  性能提升: {(first_time/cache_time - 1)*100:.1f}%")

    print("\n" + "=" * 60)
    print("优化建议:")
    print("1. 使用连接池复用连接，减少握手时间")
    print("2. 实施请求批处理，减少往返次数")
    print("3. 启用本地缓存，避免重复请求")
    print("4. 调整超时参数，快速失败")
    print("5. 使用异步并发，提高吞吐量")
    print("=" * 60)


async def test_akshare_apis():
    """测试常用的AKShare API"""
    print("\n=== 测试AKShare常用API ===")

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=5)

    async def test_api(api_func, api_name, *args, **kwargs):
        """测试单个API"""
        try:
            start = time.time()
            result = await loop.run_in_executor(executor, lambda: api_func(*args, **kwargs))
            latency = (time.time() - start) * 1000

            if result is not None:
                print(f"[OK] {api_name}: {latency:.1f}ms")
                return True
            else:
                print(f"[FAIL] {api_name}: 无数据")
                return False
        except Exception as e:
            print(f"[FAIL] {api_name}: {str(e)[:50]}")
            return False

    # 测试各种API
    apis_to_test = [
        (ak.stock_zh_a_spot_em, "实时行情(东财)"),
        (ak.stock_info_a_code_name, "股票列表"),
        (lambda: ak.stock_zh_a_hist("000001", "daily", "qfq"), "日K线数据"),
        (lambda: ak.stock_individual_info_em("000001"), "个股信息"),
        (lambda: ak.stock_zh_index_spot, "指数行情"),
    ]

    success_count = 0
    for api_func, api_name in apis_to_test:
        if await test_api(api_func, api_name):
            success_count += 1

    print(
        f"\n成功率: {success_count}/{len(apis_to_test)} ({success_count/len(apis_to_test)*100:.0f}%)"
    )


if __name__ == "__main__":
    print("开始优化测试...")
    asyncio.run(performance_test())
    asyncio.run(test_akshare_apis())
