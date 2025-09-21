# 星耀数智（AmazingData）快速入门指南

## 5分钟快速上手

本指南帮助您快速开始使用星耀数智数据服务。

## 目录
1. [环境准备](#环境准备)
2. [快速开始](#快速开始)
3. [常用场景示例](#常用场景示例)
4. [在DeepSearch中使用](#在deepsearch中使用)
5. [常见问题](#常见问题)

---

## 环境准备

### 1. 安装Python环境

确保Python版本 >= 3.8

```bash
python --version
```

### 2. 安装AmazingData SDK

```bash
# 方式1：使用whl文件安装
pip install installer/AmazingData-1.0.9-cp313-none-any.whl

# 方式2：如果在DeepSearch项目中
uv pip install installer/AmazingData-1.0.9-cp313-none-any.whl
```

### 3. 验证安装

```python
import AmazingData as ad
print(ad.__version__)
```

---

## 快速开始

### 第一个程序：获取股票行情

```python
import AmazingData as ad

# 1. 登录服务
ad.login(
    username='your_username',
    password='your_password',
    host='120.86.124.106',
    port=8600
)

# 2. 获取实时行情
market_data = ad.MarketData()
snapshot = market_data.get_snapshot(['000001'])  # 平安银行

# 3. 打印结果
stock = snapshot['000001']
print(f"股票：{stock['name']}")
print(f"最新价：{stock['last_price']}")
print(f"涨跌幅：{stock['change_percent']}%")

# 4. 登出
ad.logout()
```

---

## 常用场景示例

### 场景1：获取多只股票的实时行情

```python
import AmazingData as ad
import pandas as pd

# 登录
ad.login(username='user', password='pass', host='120.86.124.106', port=8600)

# 获取多只股票
stocks = ['000001', '000002', '600000', '600036']
market_data = ad.MarketData()
snapshot = market_data.get_snapshot(stocks)

# 转换为DataFrame便于查看
data = []
for code, info in snapshot.items():
    data.append({
        '代码': code,
        '名称': info['name'],
        '最新价': info['last_price'],
        '涨跌幅': info['change_percent'],
        '成交量': info['volume'],
        '成交额': info['amount']
    })

df = pd.DataFrame(data)
print(df)

ad.logout()
```

### 场景2：获取历史K线数据

```python
import AmazingData as ad
import pandas as pd

# 登录
ad.login(username='user', password='pass', host='120.86.124.106', port=8600)

market_data = ad.MarketData()

# 获取日K线（前复权）
kline_data = market_data.get_kline_data(
    code_list=['000001'],
    period=ad.constant.Period.day.value,
    start_date='20250101',
    end_date='20250115',
    adjust=ad.constant.Adjust.forward.value
)

# 转换为DataFrame
df = pd.DataFrame(kline_data['000001'])
df['time'] = pd.to_datetime(df['time'])
df.set_index('time', inplace=True)

print("平安银行日K线数据：")
print(df[['open', 'high', 'low', 'close', 'volume']])

ad.logout()
```

### 场景3：获取财务数据

```python
import AmazingData as ad

# 登录
ad.login(username='user', password='pass', host='120.86.124.106', port=8600)

info_data = ad.InfoData()

# 获取主要财务指标
indicators = info_data.get_key_indicators(['000001'], '2024Q3')

# 打印关键指标
data = indicators['000001'][0]
print(f"净资产收益率(ROE): {data['roe']}%")
print(f"每股收益(EPS): {data['eps']}")
print(f"每股净资产(BPS): {data['bps']}")
print(f"资产负债率: {data['debt_ratio']}%")

ad.logout()
```

### 场景4：实时订阅行情推送

```python
import AmazingData as ad
import time

# 登录
ad.login(username='user', password='pass', host='120.86.124.106', port=8600)

# 准备订阅
sub_data = ad.SubscribeData()

# 定义回调函数
@sub_data.register(
    code_list=['000001', '600000'],
    period=ad.constant.Period.snapshot.value
)
def on_snapshot(data, period):
    """收到快照数据时的处理"""
    print(f"[{time.strftime('%H:%M:%S')}] {data.code}: {data.last_price}")

print("开始订阅，按Ctrl+C停止...")
try:
    sub_data.run()  # 阻塞运行
except KeyboardInterrupt:
    print("\n订阅已停止")
    sub_data.stop()
    ad.logout()
```

### 场景5：获取龙虎榜数据

```python
import AmazingData as ad

# 登录
ad.login(username='user', password='pass', host='120.86.124.106', port=8600)

info_data = ad.InfoData()

# 获取某股票的龙虎榜
dragon_tiger = info_data.get_dragon_tiger(
    '000001',
    start_date='20250101',
    end_date='20250115'
)

for record in dragon_tiger:
    print(f"\n日期：{record['trade_date']}")
    print(f"上榜原因：{record['reason']}")
    print(f"净买入：{record['net_amount'] / 10000:.2f}万元")

    print("买入前5：")
    for item in record['buy_list'][:5]:
        print(f"  {item['broker']}: {item['amount'] / 10000:.2f}万")

ad.logout()
```

---

## 在DeepSearch中使用

### 方式1：直接使用AmazingDataProvider

```python
from deepsearch.infrastructure.providers.implementations.amazingdata import (
    AmazingDataProvider,
    AmazingDataConfig
)

# 创建配置
config = AmazingDataConfig(
    username="your_username",
    password="your_password",
    host="120.86.124.106",
    port=8600
)

# 创建提供者
provider = AmazingDataProvider(config)

# 异步初始化
import asyncio

async def main():
    await provider.initialize()

    # 获取K线
    df = await provider.get_kline('000001', period='1d')
    print(df.head())

    # 获取实时行情
    quotes = await provider.get_realtime_quote(['000001', '600000'])
    print(quotes)

asyncio.run(main())
```

### 方式2：通过配置文件自动加载

在 `settings.dev.yaml` 中配置：

```yaml
amazingdata:
  enabled: true
  priority: 1
  connection:
    username: "your_username"
    password: "your_password"
    host: "120.86.124.106"
    port: 8600
```

然后在代码中使用：

```python
from deepsearch.data_providers.enhanced_manager import get_data_manager

async def main():
    # 自动加载配置并选择最优数据源
    manager = await get_data_manager()

    # 获取数据（自动使用AmazingData）
    df = await manager.get_stock_daily(
        symbol='000001',
        start_date='2025-01-01',
        end_date='2025-01-15'
    )
    print(df)

asyncio.run(main())
```

### 方式3：在FastAPI中使用

```python
from fastapi import FastAPI, Depends
from deepsearch.webui.api.providers import get_amazingdata_provider

app = FastAPI()

@app.get("/quote/{symbol}")
async def get_quote(
    symbol: str,
    provider = Depends(get_amazingdata_provider)
):
    """获取实时行情"""
    quotes = await provider.get_realtime_quote([symbol])
    return quotes.get(symbol, {})

@app.get("/kline/{symbol}")
async def get_kline(
    symbol: str,
    period: str = '1d',
    provider = Depends(get_amazingdata_provider)
):
    """获取K线数据"""
    df = await provider.get_kline(symbol, period=period)
    return df.to_dict('records')
```

---

## 常见问题

### Q1: 登录失败怎么办？

**检查清单**：
1. 用户名密码是否正确
2. 服务器地址和端口是否正确（120.86.124.106:8600）
3. 网络是否可达：`ping 120.86.124.106`
4. 防火墙是否阻止了8600端口
5. IP是否在白名单中

### Q2: 获取数据为空？

**可能原因**：
1. 股票代码格式错误（应该是6位数字，如'000001'）
2. 日期范围无交易日
3. 该股票在指定日期停牌
4. 没有相应的数据权限

### Q3: 订阅数据收不到？

**解决方法**：
1. 确认登录成功
2. 检查订阅的股票代码是否正确
3. 确认订阅类型（snapshot/tick/kline）是否支持
4. 检查回调函数是否正确注册

### Q4: 如何提高查询性能？

**优化建议**：
1. 批量查询而非循环单个查询
2. 使用缓存避免重复查询
3. 合理设置查询时间范围
4. 使用异步并发请求

```python
# 好的做法：批量查询
codes = ['000001', '000002', '600000']
data = market_data.get_snapshot(codes)

# 差的做法：循环查询
for code in codes:
    data = market_data.get_snapshot([code])
```

### Q5: 连接断开如何处理？

**自动重连示例**：

```python
import AmazingData as ad
import time

def safe_login(max_retries=3):
    """带重试的登录"""
    for i in range(max_retries):
        try:
            result = ad.login(
                username='user',
                password='pass',
                host='120.86.124.106',
                port=8600
            )
            if result == 0 or result is True:
                print("登录成功")
                return True
        except Exception as e:
            print(f"登录失败 ({i+1}/{max_retries}): {e}")
            time.sleep(5)
    return False

# 使用
if safe_login():
    # 执行数据查询
    pass
```

---

## 下一步

- 查看[完整API参考文档](./AMAZINGDATA_API_REFERENCE.md)
- 了解[数据类型定义](./AMAZINGDATA_DATA_TYPES.md)
- 阅读[高级使用指南](./AMAZINGDATA_API_GUIDE.md)

---

*文档版本：1.0.0*
*更新日期：2025-01-15*