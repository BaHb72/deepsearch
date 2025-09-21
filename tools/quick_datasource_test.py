"""
快速数据源连接测试
"""
import asyncio
import socket
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_tcp_connection(host, port, timeout=5):
    """测试TCP连接"""
    try:
        start = time.time()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        latency = (time.time() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return True, latency
    except Exception as e:
        return False, str(e)

async def test_amazingdata():
    """测试AmazingData连接"""
    print("\n测试 AmazingData (120.86.124.106:8600)...")
    result, info = await test_tcp_connection("120.86.124.106", 8600)
    if result:
        print(f"  [OK] 连接成功，延迟: {info:.1f}ms")
    else:
        print(f"  [FAIL] 连接失败: {info}")
    return result

async def test_qmt():
    """测试QMT连接"""
    print("\n测试 QMT (127.0.0.1:9999)...")
    result, info = await test_tcp_connection("127.0.0.1", 9999)
    if result:
        print(f"  [OK] 连接成功，延迟: {info:.1f}ms")
    else:
        print(f"  [FAIL] 连接失败: {info}")
    return result

async def test_redis():
    """测试Redis连接"""
    print("\n测试 Redis (localhost:6379)...")
    result, info = await test_tcp_connection("localhost", 6379)
    if result:
        print(f"  [OK] 连接成功，延迟: {info:.1f}ms")
    else:
        print(f"  [FAIL] 连接失败: {info}")
    return result

async def test_postgresql():
    """测试PostgreSQL连接"""
    print("\n测试 PostgreSQL (localhost:5432)...")
    result, info = await test_tcp_connection("localhost", 5432)
    if result:
        print(f"  [OK] 连接成功，延迟: {info:.1f}ms")
    else:
        print(f"  [FAIL] 连接失败: {info}")
    return result

async def test_cloudflare():
    """测试CloudFlare Workers"""
    print("\n测试 CloudFlare Workers...")
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            start = time.time()
            async with session.get(
                "https://akshare-proxy.934073514.workers.dev/health",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                latency = (time.time() - start) * 1000
                if resp.status == 200:
                    print(f"  [OK] 连接成功，延迟: {latency:.1f}ms")
                    return True
                else:
                    print(f"  [FAIL] HTTP状态码: {resp.status}")
                    return False
    except Exception as e:
        print(f"  [FAIL] 连接失败: {e}")
        return False

async def main():
    print("="*60)
    print("DeepSearch 数据源快速连接测试")
    print("="*60)
    
    results = []
    
    # 测试各个数据源
    results.append(("AmazingData", await test_amazingdata()))
    results.append(("QMT", await test_qmt()))
    results.append(("Redis", await test_redis()))
    results.append(("PostgreSQL", await test_postgresql()))
    results.append(("CloudFlare", await test_cloudflare()))
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总:")
    print("-"*60)
    
    available = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[OK] 可用" if result else "[FAIL] 不可用"
        print(f"  {name:15} : {status}")
    
    print("-"*60)
    print(f"总体可用性: {available}/{total} ({available/total*100:.0f}%)")
    
    # 提供建议
    if not results[1][1]:  # QMT不可用
        print("\n[WARNING] 建议:")
        print("  1. 启动QMT终端")
        print("  2. 运行: python deepsearch/datafeed/qmt/scripts/qmt_collector_prod.py")
    
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())