"""
硬核SDK直接测试脚本
直接调用AmazingData SDK，不通过Provider层
从配置文件读取凭据
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

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

# 2. 从配置读取凭据并登录
print("\n[2] 登录TGW...")
from core.config import get_config

config = get_config()
ad_config = config.amazingdata.connection

USERNAME = ad_config.username
PASSWORD = ad_config.password
HOST = ad_config.host
PORT = ad_config.port

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
    print("    InfoData 创建成功")
except Exception as e:
    print(f"    InfoData 创建失败: {e}")

# 4. 测试 BaseData
print("\n[4] 测试 BaseData...")
try:
    base_data = ad.BaseData()
    calendar = base_data.get_calendar()
    print(f"    日历数据: {len(calendar) if calendar else 0} 条")
except Exception as e:
    print(f"    BaseData 测试失败: {e}")

print("\n" + "=" * 60)
print("测试完成")
