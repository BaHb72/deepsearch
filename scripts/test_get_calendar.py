"""诊断 AmazingData SDK BaseData.get_calendar"""

import traceback

print("=" * 60)
print("AmazingData SDK get_calendar 诊断")
print("=" * 60)

# 检查可用的 SDK 包
sdk_candidates = ["AmazingData", "amazingdata", "tgw", "amazingdata_sdk"]
sdk = None
sdk_name = None

for name in sdk_candidates:
    try:
        sdk = __import__(name)
        sdk_name = name
        print(f"\n✅ 成功加载 SDK: {name}")
        break
    except ImportError as e:
        print(f"❌ {name}: {e}")

if sdk is None:
    print("\n没有找到可用的 SDK！")
    exit(1)

# 检查 BaseData
print(f"\n检查 SDK 结构 ({sdk_name}):")
print(f"  SDK 模块: {sdk}")

base_data_cls = getattr(sdk, "BaseData", None)
market_data_cls = getattr(sdk, "MarketData", None)
info_data_cls = getattr(sdk, "InfoData", None)

print(f"  BaseData: {base_data_cls}")
print(f"  MarketData: {market_data_cls}")
print(f"  InfoData: {info_data_cls}")

if base_data_cls is None:
    print("\n⚠️ SDK 中没有 BaseData 类！")
    print("\n可用的顶级属性 (非下划线开头):")
    attrs = [a for a in dir(sdk) if not a.startswith("_")]
    for attr in sorted(attrs)[:30]:
        print(f"  - {attr}")
    if len(attrs) > 30:
        print(f"  ... 共 {len(attrs)} 个属性")
    exit(1)

# 尝试创建 BaseData 实例
print("\n尝试创建 BaseData 实例...")
try:
    base_instance = base_data_cls()
    print(f"  ✅ BaseData 实例: {base_instance}")
except Exception as e:
    print(f"  ❌ 创建失败: {e}")
    traceback.print_exc()
    exit(1)

# 检查 get_calendar
print("\n检查 get_calendar 方法...")
get_calendar = getattr(base_instance, "get_calendar", None)
if get_calendar is None:
    print("  ❌ 没有 get_calendar 方法")
    print("  可用方法:")
    for attr in dir(base_instance):
        if not attr.startswith("_") and callable(getattr(base_instance, attr, None)):
            print(f"    - {attr}")
    exit(1)

print(f"  ✅ get_calendar: {get_calendar}")

# 调用 get_calendar
print("\n调用 get_calendar()...")
try:
    calendar = get_calendar()
    print(f"  ✅ 调用成功!")
    print(f"  返回类型: {type(calendar)}")
    print(f"  返回值: {calendar}")
    if calendar:
        print(f"  长度: {len(calendar)}")
        if hasattr(calendar, "__iter__"):
            items = list(calendar)[:5]
            print(f"  前5个: {items}")
except Exception as e:
    print(f"  ❌ 调用失败: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
