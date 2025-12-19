# AmazingData 接口扩展文档

本次扩展基于用户提供的API文档，为AmazingData接口补充了详细的字段说明。

## 扩展的接口

### 1. 龙虎榜数据 (get_long_hu_bang)

**接口位置**: `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`

**方法签名**:
```python
async def get_long_hu_bang(
    self,
    code_list: List[str],
    local_path: Optional[str] = None,
    is_local: bool = True,
    begin_date: Optional[int] = None,
    end_date: Optional[int] = None,
) -> pd.DataFrame
```

**功能说明**: 获取指定股票的龙虎榜数据

**参数**:
- `code_list`: 股票代码列表
- `local_path`: 本地存储路径
- `is_local`: 是否使用本地存储
- `begin_date`: 交易日期开始筛选(格式: YYYYMMDD)，可选
- `end_date`: 交易日期结束筛选(格式: YYYYMMDD)，可选

**返回字段**:
| 字段名 | 类型 | 说明 |
|--------|------|------|
| MARKET_CODE | string | 证券代码 |
| TRADE_DATE | string | 交易日期 |
| SECURITY_NAME | string | 证券名称 |
| REASON_TYPE | string | 二级原因类别 |
| REASON_TYPE_NAME | string | 二级原因 |
| CHANGE_RANGE | float | 涨跌幅(%) |
| TRADER_NAME | string | 营业部名称 |
| BUY_AMOUNT | float | 买入金额(万) |
| SELL_AMOUNT | float | 卖出金额(万) |
| FLOW_MARK | int | 资金标示(1表示买入,2表示卖出) |
| TOTAL_AMOUNT | float | 交易总金额(万元) |
| TOTAL_VOLUME | float | 交易总数量(万股) |

---

### 2. 大宗交易数据 (get_block_trading)

**接口位置**: `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`

**方法签名**:
```python
async def get_block_trading(
    self,
    code_list: List[str],
    local_path: Optional[str] = None,
    is_local: bool = True,
    begin_date: Optional[int] = None,
    end_date: Optional[int] = None,
) -> pd.DataFrame
```

**功能说明**: 获取指定股票列表的大宗交易数据

**参数**:
- `code_list`: 股票代码列表
- `local_path`: 本地存储路径
- `is_local`: 是否使用本地存储
- `begin_date`: 交易日期开始筛选(格式: YYYYMMDD)，可选
- `end_date`: 交易日期结束筛选(格式: YYYYMMDD)，可选

**返回字段**:
| 字段名 | 类型 | 说明 |
|--------|------|------|
| MARKET_CODE | string | 证券代码 |
| TRADE_DATE | string | 交易日期 |
| B_SHARE_PRICE | float | 成交价(元) |
| B_SHARE_VOLUME | float | 成交量(万股) |
| B_FREQUENCY | int | 年数 |
| BLOCK_AVG_VOLUME | float | 每笔成交数量(万股份) |
| B_SHARE_AMOUNT | float | 成交金额(万元) |
| B_BUYER_NAME | string | 买方席位部制 |
| B_SELLER_NAME | string | 卖方席位部制 |

---

### 3. 期权基本资料 (get_option_basic_info)

**接口位置**: `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`

**方法签名**:
```python
async def get_option_basic_info(
    self,
    code_list: List[str],
    local_path: Optional[str] = None,
    is_local: bool = True,
) -> pd.DataFrame
```

**功能说明**: 获取期权基本资料(沪深交易所的ETF期权)

**参数**:
- `code_list`: 期权代码列表
- `local_path`: 本地存储路径
- `is_local`: 是否使用本地存储

**返回字段**:
| 字段名 | 类型 | 说明 |
|--------|------|------|
| CONTRACT_FULL_NAME | string | 合约全称 |
| CONTRACT_TYPE | string | 合约类型(C表示认购, P表示认沽) |
| DELIVERY_MONTH | string | 交割月份 |
| EXPIRY_DATE | string | 到期日 |
| EXERCISE_PRICE | float | 行权价格 |
| EXERCISE_END_DATE | string | 权利行权日 |
| START_TRADE_DATE | string | 开始交易日 |
| LISTING_REF_PRICE | float | 挂牌参考价 |
| LAST_TRADE_DATE | string | 最后交易日 |
| EXCHANGE_CODE | string | 合约交易所代码 |
| DELIVERY_DATE | string | 标的交割日 |
| CONTRACT_UNIT | int | 合约单位 |
| IS_TRADE | string | 是否交易 |
| EXCHANGE_SHORT_NAME | string | 合约交易所简称 |
| CONTRACT_ADJUST_FLAG | string | 合约调整标识 |
| MARKET_CODE | string | 合约代码 |

---

### 4. 期权标准合约属性 (get_option_std_ctr_specs)

**接口位置**: `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`

**方法签名**:
```python
async def get_option_std_ctr_specs(
    self,
    code_list: List[str],
    local_path: Optional[str] = None,
    is_local: bool = True,
) -> pd.DataFrame
```

**功能说明**: 获取沪深期权标准合约的结构属性(沪深交易所的ETF期权)

**参数**:
- `code_list`: 期权代码列表(支持深沪ETF期权的代码列表，如159919.SZ、159915.SZ、159922.SZ等)
- `local_path`: 本地存储路径
- `is_local`: 是否使用本地存储

**返回字段**:
| 字段名 | 类型 | 说明 |
|--------|------|------|
| EXERCISE_DATE | string | 期权行权日 |
| CONTRACT_UNIT | int | 合约单位 |
| POSITION_DECLARE_MIN | string | 实行申报下限 |
| QUOTE_CURRENCY_UNIT | string | 报价货币单位 |
| LAST_TRADING_DATE | string | 最后交易日 |
| POSITION_LIMIT | string | 实行限制 |
| DELIST_DATE | string | 摘牌日期 |
| NOTIONAL_VALUE | string | 名义价值 |
| EXERCISE_METHOD | string | 行权方式 |
| DELIVERY_METHOD | string | 交割方式 |
| SETTLEMENT_MONTH | string | 合约结算月份 |
| TRADING_FEE | string | 交易费叙 |
| EXCHANGE_NAME | string | 交易所名称 |
| OPTION_EN_NAME | string | 期权英文名称 |
| CONTRACT_VALUE | float | 合约价值 |
| IS_SIMULATION | int | 是否仿真交易(0否1是) |
| CONTRACT_UNIT_DIMENSI | string | 合约单位量纲 |
| OPTION_STRIKE_PRICE | string | 期权行权价 |
| IS_SIMULATION_TRADE | string | 是否仿真交易(0否1是) |
| LISTED_DATE | string | 上市日期 |
| OPTION_NAME | string | 期权名称 |
| PREMIUM | string | 期权金 |
| OPTION_TYPE | string | 期权类型(ETF对标类型) |
| TRADING_HOURS_DESC | string | 交易时间说明 |

---

## 使用示例

### 1. 龙虎榜数据

```python
from datetime import datetime, timedelta

# 获取最近30天的龙虎榜数据
end_date = int(datetime.now().strftime("%Y%m%d"))
begin_date = int((datetime.now() - timedelta(days=30)).strftime("%Y%m%d"))

data = await provider.get_long_hu_bang(
    code_list=["000001.SZ", "600519.SH"],
    begin_date=begin_date,
    end_date=end_date
)
```

### 2. 大宗交易数据

```python
from datetime import datetime, timedelta

# 获取最近30天的大宗交易数据
end_date = int(datetime.now().strftime("%Y%m%d"))
begin_date = int((datetime.now() - timedelta(days=30)).strftime("%Y%m%d"))

data = await provider.get_block_trading(
    code_list=["000001.SZ", "600519.SH"],
    begin_date=begin_date,
    end_date=end_date
)
```

### 3. 期权基本资料

```python
# 先获取期权代码列表
option_codes = await provider.get_option_code_list()

# 获取前10个期权的基本资料
data = await provider.get_option_basic_info(
    code_list=option_codes[:10]
)
```

### 4. 期权标准合约属性

```python
# 获取深沪ETF期权的标准合约属性
etf_codes = ["159919.SZ", "159915.SZ", "510300.SH", "510050.SH"]

data = await provider.get_option_std_ctr_specs(
    code_list=etf_codes
)
```

---

## 测试脚本

提供了专门的测试脚本来验证这些接口：

**脚本路径**: `scripts/test_amazingdata_extended_apis.py`

**运行方法**:
```bash
python scripts/test_amazingdata_extended_apis.py
```

该脚本会依次测试以上四个接口，并显示：
- 接口调用是否成功
- 返回的数据量
- 返回的字段列表
- 数据预览
- 字段完整性验证

---

## 注意事项

1. **所有接口都是异步方法**，需要使用 `await` 调用
2. **日期格式统一为 YYYYMMDD**，例如：20241213
3. **为避免数据源限流**，建议测试时：
   - 只测试少量股票代码（1-3个）
   - 限制时间范围（最近7-30天）
   - 分开测试不同接口
4. **部分接口可能返回空数据**，这是正常的：
   - 龙虎榜：只有上榜的股票才有数据
   - 大宗交易：只有发生大宗交易的股票才有数据
5. **期权接口需要先获取期权代码列表**，可通过 `get_option_code_list()` 获取

---

## 变更说明

### 2025-12-16

**更新内容**:
1. 为 `get_long_hu_bang` 补充了完整的字段文档，基于API文档3.5.9.1
2. 为 `get_block_trading` 补充了完整的字段文档，基于API文档3.5.9.2
3. 为 `get_option_basic_info` 补充了完整的字段文档，基于API文档3.5.10.1
4. 为 `get_option_std_ctr_specs` 补充了完整的字段文档，基于API文档3.5.10.2
5. 创建了专门的测试脚本 `test_amazingdata_extended_apis.py`

**文件修改**:
- `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`

**新增文件**:
- `scripts/test_amazingdata_extended_apis.py`
- `docs/amazingdata_extended_interfaces.md` (本文档)

---

## 相关文档

- AmazingData SDK 官方文档: 根据用户提供的截图
- 中泰数据平台数据字典: https://dict.thinktrader.net/dictionary
