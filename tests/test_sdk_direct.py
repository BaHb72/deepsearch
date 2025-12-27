"""
硬核SDK直接测试脚本
直接调用AmazingData SDK，不通过Provider层
"""

import sys
import time
from datetime import datetime, timedelta

print("=" * 60)
print("AmazingData SDK 直接测试")
print("=" * 60)

# 1. 导入SDK
print("\n[1] 导入SDK...")
try:
    import AmazingData as ad

    print(f"    SDK导入成功: {ad}")
except ImportError as e:
    print(f"    SDK导入失败: {e}")
    sys.exit(1)

# 2. 登录
print("\n[2] 登录TGW...")
USERNAME = "212200038719"
PASSWORD = "212200038719@2025"
HOST = "101.230.159.234"
PORT = 8600

print(f"    用户名: {USERNAME}")
print(f"    主机: {HOST}:{PORT}")

start_time = time.time()
result = ad.login(username=USERNAME, password=PASSWORD, host=HOST, port=PORT)
elapsed = time.time() - start_time

print(f"    登录结果: {result}")
print(f"    耗时: {elapsed:.2f}秒")

if result not in (0, True):
    print("    登录失败，退出测试！")
    sys.exit(1)

print("    登录成功!")

# 3. 创建数据对象
print("\n[3] 创建数据对象...")
try:
    info_data = ad.InfoData()
    base_data = ad.BaseData()
    print(f"    InfoData: {info_data}")
    print(f"    BaseData: {base_data}")
except Exception as e:
    print(f"    创建数据对象失败: {e}")
    sys.exit(1)

# 4. 测试配置
LOCAL_PATH = "D://AmazingData_local_data//"
IS_LOCAL = False  # 强制从服务器获取
CODE_LIST = ["SZ.002202"]  # 测试金风科技龙虎榜

# 日期参数 - 使用最近7天的数据
END_DATE = int(datetime.now().strftime("%Y%m%d"))
BEGIN_DATE = int((datetime.now() - timedelta(days=7)).strftime("%Y%m%d"))

print("\n[4] 测试参数:")
print(f"    local_path: {LOCAL_PATH}")
print(f"    is_local: {IS_LOCAL}")
print(f"    code_list: {CODE_LIST}")
print(f"    begin_date: {BEGIN_DATE}")
print(f"    end_date: {END_DATE}")

# 5. 测试get_long_hu_bang (只用参数组2: begin_date/end_date)
print("\n[5] 测试 get_long_hu_bang (龙虎榜)...")
print("    调用: info_data.get_long_hu_bang(")
print(f"        code_list={CODE_LIST},")
print(f"        begin_date={BEGIN_DATE},")
print(f"        end_date={END_DATE}")
print("    )")
print("    注意: 只使用参数组2, 不传local_path/is_local")

try:
    start_time = time.time()
    result = info_data.get_long_hu_bang(
        code_list=CODE_LIST, begin_date=BEGIN_DATE, end_date=END_DATE
    )
    elapsed = time.time() - start_time

    print(f"    耗时: {elapsed:.2f}秒")
    if result is not None:
        print(f"    返回类型: {type(result)}")
        if hasattr(result, "shape"):
            print(f"    数据形状: {result.shape}")
            if len(result) > 0:
                print(f"    列名: {list(result.columns)[:5]}...")
                print(f"    前2行:\n{result.head(2)}")
        else:
            print(f"    返回值: {result}")
    else:
        print("    返回: None")
except Exception as e:
    print(f"    调用失败: {e}")
    import traceback

    traceback.print_exc()

# 6. 测试get_balance_sheet (资产负债表)
print("\n[6] 测试 get_balance_sheet (资产负债表)...")
print("    调用: info_data.get_balance_sheet(")
print(f"        code_list={CODE_LIST},")
print(f"        local_path='{LOCAL_PATH}',")
print("        is_local=False  # 尝试网络获取")
print("    )")

try:
    start_time = time.time()
    result = info_data.get_balance_sheet(
        code_list=CODE_LIST, local_path=LOCAL_PATH, is_local=False  # 强制网络获取
    )
    elapsed = time.time() - start_time

    print(f"    耗时: {elapsed:.2f}秒")
    if result is not None:
        print(f"    返回类型: {type(result)}")
        if hasattr(result, "shape"):
            print(f"    数据形状: {result.shape}")
    else:
        print("    返回: None")
except Exception as e:
    print(f"    调用失败: {e}")
    import traceback

    traceback.print_exc()

# 7. 测试get_margin_summary
print("\n[7] 测试 get_margin_summary (融资融券汇总)...")
print("    调用: info_data.get_margin_summary(")
print(f"        local_path='{LOCAL_PATH}',")
print(f"        is_local={IS_LOCAL},")
print(f"        begin_date={BEGIN_DATE},")
print(f"        end_date={END_DATE}")
print("    )")

try:
    start_time = time.time()
    result = info_data.get_margin_summary(
        local_path=LOCAL_PATH, is_local=IS_LOCAL, begin_date=BEGIN_DATE, end_date=END_DATE
    )
    elapsed = time.time() - start_time

    print(f"    耗时: {elapsed:.2f}秒")
    if result is not None:
        print(f"    返回类型: {type(result)}")
        if hasattr(result, "shape"):
            print(f"    数据形状: {result.shape}")
            if len(result) > 0:
                print(f"    前2行:\n{result.head(2)}")
    else:
        print("    返回: None")
except Exception as e:
    print(f"    调用失败: {e}")
    import traceback

    traceback.print_exc()

# 8. 测试get_margin_detail
print("\n[8] 测试 get_margin_detail (融资融券明细)...")
print("    调用: info_data.get_margin_detail(")
print(f"        code_list={CODE_LIST},")
print(f"        local_path='{LOCAL_PATH}',")
print(f"        is_local={IS_LOCAL},")
print(f"        begin_date={BEGIN_DATE},")
print(f"        end_date={END_DATE}")
print("    )")

try:
    start_time = time.time()
    result = info_data.get_margin_detail(
        code_list=CODE_LIST,
        local_path=LOCAL_PATH,
        is_local=IS_LOCAL,
        begin_date=BEGIN_DATE,
        end_date=END_DATE,
    )
    elapsed = time.time() - start_time

    print(f"    耗时: {elapsed:.2f}秒")
    if result is not None:
        print(f"    返回类型: {type(result)}")
        if hasattr(result, "shape"):
            print(f"    数据形状: {result.shape}")
            if len(result) > 0:
                print(f"    前2行:\n{result.head(2)}")
    else:
        print("    返回: None")
except Exception as e:
    print(f"    调用失败: {e}")
    import traceback

    traceback.print_exc()

# 9. 测试get_profit_express
print("\n[9] 测试 get_profit_express (业绩快报)...")
print("    调用: info_data.get_profit_express(")
print(f"        code_list={CODE_LIST},")
print(f"        local_path='{LOCAL_PATH}',")
print(f"        is_local={IS_LOCAL},")
print(f"        begin_date={BEGIN_DATE},")
print(f"        end_date={END_DATE}")
print("    )")

try:
    start_time = time.time()
    result = info_data.get_profit_express(
        code_list=CODE_LIST,
        local_path=LOCAL_PATH,
        is_local=IS_LOCAL,
        begin_date=BEGIN_DATE,
        end_date=END_DATE,
    )
    elapsed = time.time() - start_time

    print(f"    耗时: {elapsed:.2f}秒")
    if result is not None:
        print(f"    返回类型: {type(result)}")
        if hasattr(result, "shape"):
            print(f"    数据形状: {result.shape}")
    else:
        print("    返回: None")
except Exception as e:
    print(f"    调用失败: {e}")
    import traceback

    traceback.print_exc()

# 10. 登出
print("\n[10] 登出...")
try:
    ad.logout(USERNAME)
    print("    登出成功")
except Exception as e:
    print(f"    登出失败: {e}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
