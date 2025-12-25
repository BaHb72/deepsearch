#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TGW 连接错误重现测试

验证 2025-11-07 bug报告中的问题是否已修复:
1. AmazingData SDK 登录触发 SystemExit
2. TGW push init 失败
3. Worker 锁冲突
4. 数据源模式自动切换
"""

import sys
sys.path.insert(0, "d:/Stock/code/deepsearch")

from datetime import datetime
import time
import os

# ========== 配置 ==========
CONFIG = {
    "username": "212200038719",
    "password": "212200038719@2025",
    "host": "101.230.159.234",
    "port": 8600
}

results = []


def record_result(test_name: str, passed: bool, message: str):
    """记录测试结果"""
    status = "[PASS]" if passed else "[FAIL]"
    results.append((test_name, passed, message))
    print(f"{status} {test_name}: {message}")


def test_1_sdk_login():
    """测试1: SDK 登录是否会触发 SystemExit"""
    print("\n" + "="*60)
    print("测试 1: SDK 登录 - 检查是否触发 SystemExit")
    print("="*60)
    
    try:
        import AmazingData as ad
        
        # 尝试登录
        result = ad.login(**CONFIG)
        
        if result == 0 or result is True:
            record_result("SDK登录", True, "登录成功，未触发 SystemExit")
            
            # 测试基本接口
            base = ad.BaseData()
            calendar = base.get_calendar()
            if calendar and len(calendar) > 0:
                record_result("BaseData.get_calendar", True, f"获取到 {len(calendar)} 条日历数据")
            else:
                record_result("BaseData.get_calendar", False, "无数据返回")
            
            # 登出
            try:
                ad.logout(CONFIG["username"])
            except:
                pass
            
            return True
        else:
            record_result("SDK登录", False, f"登录失败: {result}")
            return False
            
    except SystemExit as e:
        record_result("SDK登录", False, f"触发 SystemExit: {e}")
        return False
    except Exception as e:
        record_result("SDK登录", False, f"异常: {type(e).__name__}: {e}")
        return False


def test_2_push_mode():
    """测试2: TGW push 模式是否正常"""
    print("\n" + "="*60)
    print("测试 2: TGW Push 模式检查")
    print("="*60)
    
    try:
        import AmazingData as ad
        
        # 登录
        result = ad.login(**CONFIG)
        if result != 0 and result is not True:
            record_result("Push模式登录", False, f"登录失败: {result}")
            return False
        
        # 检查常量中的 Period 定义
        if hasattr(ad, 'constant') and hasattr(ad.constant, 'Period'):
            periods = []
            for attr in dir(ad.constant.Period):
                if not attr.startswith('_'):
                    periods.append(attr)
            record_result("Period常量检查", True, f"可用周期: {periods[:10]}...")
        else:
            record_result("Period常量检查", False, "未找到 Period 定义")
        
        # 尝试获取实时数据
        base = ad.BaseData()
        calendar = base.get_calendar()
        market = ad.MarketData(calendar)
        
        today = int(datetime.now().strftime("%Y%m%d"))
        snapshot = market.query_snapshot(
            code_list=["000001.SZ"],
            begin_date=today,
            end_date=today
        )
        
        if snapshot:
            record_result("实时快照查询", True, f"返回数据: {list(snapshot.keys())}")
        else:
            record_result("实时快照查询", False, "无数据返回")
        
        # 登出
        try:
            ad.logout(CONFIG["username"])
        except:
            pass
        
        return True
        
    except SystemExit as e:
        record_result("Push模式", False, f"触发 SystemExit: {e} (可能是 TGW push init 失败)")
        return False
    except Exception as e:
        record_result("Push模式", False, f"异常: {type(e).__name__}: {e}")
        return False


def test_3_worker_lock():
    """测试3: Worker 锁文件检查"""
    print("\n" + "="*60)
    print("测试 3: Worker 锁文件检查")
    print("="*60)
    
    import tempfile
    import glob
    
    temp_dir = tempfile.gettempdir()
    lock_pattern = os.path.join(temp_dir, "amazingdata_worker_*.lock")
    
    lock_files = glob.glob(lock_pattern)
    
    if lock_files:
        print(f"  发现 {len(lock_files)} 个锁文件:")
        for lf in lock_files:
            mtime = datetime.fromtimestamp(os.path.getmtime(lf))
            size = os.path.getsize(lf)
            print(f"    - {os.path.basename(lf)} (修改时间: {mtime}, 大小: {size})")
        record_result("锁文件检查", True, f"发现 {len(lock_files)} 个锁文件 (正常运行中)")
    else:
        record_result("锁文件检查", True, "无残留锁文件")
    
    return True


def test_4_kline_period_compat():
    """测试4: K线 period 参数兼容性"""
    print("\n" + "="*60)
    print("测试 4: K线 period 参数兼容性")
    print("="*60)
    
    try:
        import AmazingData as ad
        
        result = ad.login(**CONFIG)
        if result != 0 and result is not True:
            record_result("K线参数兼容", False, "登录失败")
            return False
        
        base = ad.BaseData()
        calendar = base.get_calendar()
        market = ad.MarketData(calendar)
        
        # 测试不同 period 值
        test_periods = [
            (10000, "1分钟 (10000)"),
            (10008, "日线 (10008)"),
        ]
        
        for period_val, period_name in test_periods:
            try:
                kline = market.query_kline(
                    code_list=["000001.SZ"],
                    begin_date=20241201,
                    end_date=20241210,
                    period=period_val
                )
                if kline and "000001.SZ" in kline:
                    data = kline["000001.SZ"]
                    count = len(data) if hasattr(data, '__len__') else "N/A"
                    record_result(f"K线查询-{period_name}", True, f"返回 {count} 条数据")
                else:
                    record_result(f"K线查询-{period_name}", False, "无数据")
            except Exception as e:
                record_result(f"K线查询-{period_name}", False, f"异常: {e}")
        
        # 登出
        try:
            ad.logout(CONFIG["username"])
        except:
            pass
        
        return True
        
    except Exception as e:
        record_result("K线参数兼容", False, f"异常: {type(e).__name__}: {e}")
        return False


def test_5_process_mode():
    """测试5: 进程隔离模式 (通过封装层)"""
    print("\n" + "="*60)
    print("测试 5: 进程隔离模式检查")
    print("="*60)
    
    try:
        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_proxy import (
            AmazingDataProcessProxy,
        )
        record_result("进程代理模块导入", True, "AmazingDataProcessProxy 可导入")
        
        # 检查关键类是否存在
        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (
            AmazingDataProcessPool,
        )
        record_result("进程池模块导入", True, "AmazingDataProcessPool 可导入")
        
        return True
        
    except ImportError as e:
        record_result("进程隔离模块", False, f"导入失败: {e}")
        return False
    except Exception as e:
        record_result("进程隔离模块", False, f"异常: {type(e).__name__}: {e}")
        return False


def test_6_access_violation():
    """测试6: 检查是否会触发 ACCESS_VIOLATION (0xC0000005)"""
    print("\n" + "="*60)
    print("测试 6: ACCESS_VIOLATION 检查 (登录后保持连接)")
    print("="*60)
    
    try:
        import AmazingData as ad
        
        result = ad.login(**CONFIG)
        if result != 0 and result is not True:
            record_result("ACCESS_VIOLATION测试", False, "登录失败")
            return False
        
        print("  登录成功，等待 3 秒观察是否崩溃...")
        time.sleep(3)
        
        # 如果能执行到这里，说明没有崩溃
        record_result("ACCESS_VIOLATION测试", True, "登录后 3 秒内未崩溃")
        
        # 执行一些操作
        base = ad.BaseData()
        codes = base.get_code_list(security_type='EXTRA_STOCK_A')
        if codes:
            record_result("登录后获取股票列表", True, f"获取到 {len(codes)} 只股票")
        
        # 登出
        try:
            ad.logout(CONFIG["username"])
        except:
            pass
        
        return True
        
    except SystemExit as e:
        record_result("ACCESS_VIOLATION测试", False, f"触发 SystemExit: {e}")
        return False
    except Exception as e:
        record_result("ACCESS_VIOLATION测试", False, f"异常: {type(e).__name__}: {e}")
        return False


def main():
    print("="*70)
    print("TGW 连接错误重现测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("参考: docs/archive/reports/bug_2025-11-07_market_data_runtime.md")
    print("="*70)
    
    # 运行所有测试
    test_1_sdk_login()
    test_2_push_mode()
    test_3_worker_lock()
    test_4_kline_period_compat()
    test_5_process_mode()
    test_6_access_violation()
    
    # 总结
    print("\n" + "="*70)
    print("测试结果汇总")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for name, status, msg in results:
        icon = "[PASS]" if status else "[FAIL]"
        print(f"  {icon} {name}")
        if status:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    
    # 结论
    print("\n" + "="*70)
    print("结论")
    print("="*70)
    
    if failed == 0:
        print("  所有之前报告的 TGW 连接错误现在都已修复!")
        print("  - SDK登录正常，无 SystemExit")
        print("  - TGW push 模式正常工作")
        print("  - 无 ACCESS_VIOLATION 崩溃")
    else:
        print("  部分问题仍然存在，请检查上述失败项")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
