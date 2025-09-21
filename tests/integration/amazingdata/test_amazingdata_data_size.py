"""
测试AmazingData返回数据量大小
"""
import sys
import time
import AmazingData as ad

# 配置
USERNAME = "212200038719"
PASSWORD = "212200038719@2025"
HOST = "101.230.159.234"
PORT = 8600

print("=" * 60)
print("AmazingData 数据量测试")
print("=" * 60)

# 登录
print("\n[1] 登录...")
login_result = ad.login(USERNAME, PASSWORD, HOST, PORT)
if login_result != 0 and login_result is not True:
    print(f"登录失败: {login_result}")
    sys.exit(1)
print("登录成功")

# 创建BaseData
print("\n[2] 创建BaseData对象...")
base_data = ad.BaseData()
print("BaseData创建成功")

# 测试get_code_info
print("\n[3] 调用get_code_info('EXTRA_STOCK_A')...")
start_time = time.time()

try:
    code_info = base_data.get_code_info('EXTRA_STOCK_A')
    elapsed = time.time() - start_time

    print(f"✓ 调用成功，耗时: {elapsed:.2f}秒")
    print(f"  返回类型: {type(code_info)}")

    if code_info is not None:
        # 检查数据大小
        import pandas as pd
        if isinstance(code_info, pd.DataFrame):
            print(f"  DataFrame形状: {code_info.shape}")
            print(f"  列数: {len(code_info.columns)}")
            print(f"  行数: {len(code_info)}")

            # 估算内存占用
            memory_usage = code_info.memory_usage(deep=True).sum()
            print(f"  内存占用: {memory_usage / 1024 / 1024:.2f} MB")

            # 显示前几列
            print(f"  列名: {list(code_info.columns)[:10]}...")

            # 测试转JSON的大小
            try:
                import json
                # 只测试前10行
                sample_json = code_info.head(10).to_json()
                print(f"  前10行JSON大小: {len(sample_json) / 1024:.2f} KB")

                # 估算全部数据JSON大小
                estimated_full_size = len(sample_json) * len(code_info) / 10 / 1024 / 1024
                print(f"  估算完整JSON大小: {estimated_full_size:.2f} MB")
            except Exception as e:
                print(f"  JSON转换测试失败: {e}")

except Exception as e:
    elapsed = time.time() - start_time
    print(f"✗ 调用失败，耗时: {elapsed:.2f}秒")
    print(f"  错误: {e}")

# 对比：测试获取少量数据
print("\n[4] 对比测试：获取交易日历（数据量小）...")
start_time = time.time()
try:
    calendar = base_data.get_calendar()
    elapsed = time.time() - start_time
    print(f"✓ 获取交易日历成功，耗时: {elapsed:.2f}秒")
    if calendar is not None:
        print(f"  数据条数: {len(calendar)}")
except Exception as e:
    print(f"✗ 获取失败: {e}")

# 登出
print("\n[5] 登出...")
ad.logout(USERNAME)
print("完成")

input("\n按Enter退出...")