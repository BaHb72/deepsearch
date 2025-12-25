"""测试 MiniQMT 是否支持北交所数据"""
import xtquant.xtdata as xtdata

# 测试获取板块列表
print("=" * 50)
print("测试 MiniQMT 北交所数据支持")
print("=" * 50)

# 1. 获取所有可用板块
print("\n1. 获取所有板块列表:")
try:
    sectors = xtdata.get_sector_list()
    print(f"   总共 {len(sectors)} 个板块")
    # 查找包含"北"字的板块
    bj_sectors = [s for s in sectors if "北" in s]
    print(f"   包含'北'的板块: {bj_sectors}")
except Exception as e:
    print(f"   错误: {e}")

# 2. 尝试不同的北交所板块名称
print("\n2. 尝试获取北交所股票列表:")
sector_names = ["北交所", "北证", "北京证券交易所", "BJ"]
for name in sector_names:
    try:
        stocks = xtdata.get_stock_list_in_sector(name)
        count = len(stocks) if stocks else 0
        print(f"   '{name}': {count} 只股票")
        if stocks and count > 0:
            print(f"      示例: {stocks[:5]}")
    except Exception as e:
        print(f"   '{name}': 错误 - {e}")

# 3. 获取沪深A股作为对比
print("\n3. 获取沪深A股作为对比:")
try:
    stocks = xtdata.get_stock_list_in_sector("沪深A股")
    count = len(stocks) if stocks else 0
    print(f"   '沪深A股': {count} 只股票")
    # 检查是否包含北交所股票（4/8开头）
    bj_stocks = [s for s in (stocks or []) if s.endswith(".BJ") or 
                 (s.split(".")[0].startswith(("4", "8")) and len(s.split(".")[0]) == 6)]
    print(f"   其中北交所股票: {len(bj_stocks)} 只")
    if bj_stocks:
        print(f"   示例: {bj_stocks[:5]}")
except Exception as e:
    print(f"   错误: {e}")

print("\n" + "=" * 50)
print("测试完成")
