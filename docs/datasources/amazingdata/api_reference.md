# 星耀数智（AmazingData）API接口参考文档

> 资料来源：`docs/datasources/amazingdata/AmazingData_API.md`（2025-09-11 更新，文档版本 V1.0.8，Python SDK V1.0.8）。本文件梳理 DeepSearch 使用场景下的 API 分类、参数与返回格式，并指向完整字段说明。  
> 更新时间：2025-10-10

## 版本信息
- 官方文档版本：V1.0.8（2025-09-11）
- 推荐 SDK：AmazingData Python SDK ≥ V1.0.8  
  DeepSearch 当前内置 `third_party/amazingdata/AmazingData-1.0.10-cp313-none-any.whl`，接口与官方文档兼容。
- 适用网络：电信 `101.230.159.234:8600`、联通 `140.206.44.234:8600`（详见 `setup.md`）
- 缓存目录：建议统一配置为 `D://AmazingData_local_data//`，便于复权、历史类接口读取本地数据。

## 常用对象
- `ad.login / ad.logout / ad.update_password`：认证流程。
- `ad.BaseData`：获取代码表、复权因子、交易日历等基础数据。
- `ad.InfoData`：证券基础信息、财务报表、股东股本、权益与分红。
- `ad.MarketData`：历史行情查询（快照、K线）。
- `ad.SubscribeData`：实时行情订阅。
- 常量定义（`ad.constant.Period`、`ad.constant.SecurityType` 等）详见 `data_types.md`。

## 阅读指引
- 每个接口章节提供函数签名、主要参数和返回说明；完整字段列表与取值范围请对照 `AmazingData_API.md` 及 `data_types.md`。
- 所有接口在调用前必须先执行 `ad.login` 并在流程结束后 `ad.logout`。
- 需要本地缓存的接口统一支持 `local_path` 与 `is_local` 参数；建议通过配置文件统一管理路径。

## 目录
1. [认证接口](#认证接口)
2. [基础数据（BaseData / InfoData）](#基础数据basedata--infodata)
3. [实时行情订阅（SubscribeData）](#实时行情订阅subscribedata)
4. [历史行情查询（MarketData）](#历史行情查询marketdata)
5. [财务数据（InfoData）](#财务数据infodata)
6. [股东股本数据（InfoData）](#股东股本数据infodata)
7. [权益与分红数据（InfoData）](#权益与分红数据infodata)
8. [融资融券数据（InfoData）](#融资融券数据infodata)
9. [龙虎榜数据（InfoData）](#龙虎榜数据infodata)

---

## 认证接口

### ad.login
功能：登录星耀数智平台，所有数据接口必须在成功登录后调用。

函数签名：
```python
ad.login(username: str, password: str, host: str, port: int) -> int
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| username | str | 是 | AmazingData 账号（联系营业部开通） |
| password | str | 是 | 登录密码 |
| host | str | 是 | 服务器地址，常用值见版本信息 |
| port | int | 是 | 服务器端口，默认 8600 |

返回值：`0` 或 `True` 表示成功，其余为错误码。

### ad.logout
功能：登出平台，释放登录态。

函数签名：
```python
ad.logout() -> None
```

> **注意（2025-10）**：结合现网排查，AmazingData 官方 SDK 中的 `ad.logout()` 在会话收尾阶段触发底层线程清理缺陷，导致 Windows+WSL 镜像网络环境必现崩溃。为避免服务被异常终止，DeepSearch 当前禁用业务侧直接调用。
> 临时措施：由 `OptimizedAmazingDataProvider` / `ProcessIsolatedAmazingDataProvider` 内置的连接回收逻辑托管资源释放，绕过 SDK 缺陷。在官方发布修复版本前，请勿在生产脚本中显式调用 `ad.logout()`，并关注后续 SDK 升级公告。

### ad.update_password
功能：修改账号密码，需要在登录后调用。

函数签名：
```python
ad.update_password(username: str, old_password: str, new_password: str) -> int
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| username | str | 是 | AmazingData 账号 |
| old_password | str | 是 | 原密码 |
| new_password | str | 是 | 新密码 |

返回值：`0` 或 `True` 表示修改成功。

---

## 基础数据（BaseData / InfoData）

> 说明：`security_type`、`market`、`Period` 等取值范围参见 `data_types.md` 附录。

### BaseData.get_code_info
函数签名：
```python
BaseData.get_code_info(security_type: str = 'EXTRA_STOCK_A') -> pandas.DataFrame
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| security_type | str | 否 | 代码类型，默认沪深北 A 股列表 |

返回值：DataFrame（索引为证券代码），包含 `symbol`、`pre_close`、`high_limited`、`low_limited`、`price_tick` 等列。详细字段参见 `AmazingData_API.md` 3.5.2.1。

使用示例：
```python
base_data = ad.BaseData()
etf_info = base_data.get_code_info(security_type='EXTRA_ETF')
```

### BaseData.get_code_list
函数签名：
```python
BaseData.get_code_list(security_type: str = 'EXTRA_STOCK_A') -> list[str]
```

参数同上，返回值为指定市场当日最新代码列表（不提供历史回溯）。

### BaseData.get_future_code_list
函数签名：
```python
BaseData.get_future_code_list(security_type: str = 'EXTRA_FUTURE') -> list[str]
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| security_type | str | 是 | 期货交易所代码，支持中金所、上期所、大商所、郑商所、上期所能源 |

返回值：期货合约代码列表。

### BaseData.get_backward_factor
函数签名：
```python
BaseData.get_backward_factor(
    code_list: list[str],
    local_path: str,
    is_local: bool = True
) -> pandas.DataFrame
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| code_list | list[str] | 是 | 证券或基金代码列表 |
| local_path | str | 是 | 本地缓存目录，示例 `D://AmazingData_local_data//` |
| is_local | bool | 否 | 是否优先读取本地缓存，默认 True |

返回值：DataFrame（索引为交易日期、列为代码），为后复权因子。

### BaseData.get_adj_factor
函数签名与参数同 `get_backward_factor`，返回单次复权因子 DataFrame。

### BaseData.get_hist_code_list
函数签名：
```python
BaseData.get_hist_code_list(
    security_type: str = 'EXTRA_STOCK_A_SH_SZ',
    start_date: int,
    end_date: int,
    local_path: str
) -> list[str]
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| security_type | str | 是 | 证券类型（支持沪深北、期货等） |
| start_date | int | 是 | 起始交易日，格式 `YYYYMMDD` |
| end_date | int | 是 | 结束交易日，格式 `YYYYMMDD` |
| local_path | str | 是 | 本地缓存目录 |

返回值：指定区间的历史代码集合。

### BaseData.get_calendar
函数签名：
```python
BaseData.get_calendar(
    data_type: str = 'str',
    market: str = 'SH'
) -> list[int] | list[datetime.datetime]
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| data_type | str | 否 | 返回类型，`'str'` 或 `'datetime'` |
| market | str | 否 | 市场代码，默认上海（`SH`），支持深圳 `SZ`、北交所 `BJ` 等 |

返回值：交易日列表。

### InfoData.get_stock_basic
函数签名：
```python
InfoData.get_stock_basic(code_list: list[str]) -> pandas.DataFrame
```

参数说明：

| 参数 | 类型 | 必填 | 说明 |
| ---- | ---- | ---- | ---- |
| code_list | list[str] | 是 | 支持沪深北全部证券代码 |

返回值：DataFrame，列包含 `MARKET_CODE`、`SECURITY_NAME`、`LISTDATE`、`DELISTDATE`、`LISTPLATE_NAME` 等。完整字段见 `AmazingData_API.md` 3.5.2.8。

### InfoData.get_history_stock_status
函数签名：
```python
InfoData.get_history_stock_status(
    code_list: list[str],
    local_path: str,
    is_local: bool = True
) -> pandas.DataFrame
```

返回值：包含涨跌停价、ST 标记、除权除息等历史信息的 DataFrame。

### InfoData.get_bj_code_mapping
函数签名：
```python
InfoData.get_bj_code_mapping(
    local_path: str,
    is_local: bool = True
) -> pandas.DataFrame
```

返回值：北交所新旧代码对照表（列含 `OLD_CODE`、`NEW_CODE`、`SECURITY_NAME`、`LISTING_DATE`）。

---

## 实时行情订阅（SubscribeData）

调用步骤：

1. 执行 `ad.login` 并准备代码列表（通常先用 `BaseData.get_code_list`）。
2. 实例化 `ad.SubscribeData()`。
3. 使用 `@sub_data.register(code_list=..., period=...)` 装饰回调函数。
4. 在回调中处理 `data` 对象，类型对应不同 Snapshot。
5. 调用 `sub_data.run()` 启动订阅，完成后 `ad.logout()`。

支持的订阅接口如下：

| 回调函数 | 支持品种 | period 取值 | 返回对象 |
| -------- | -------- | ----------- | -------- |
| `onSnapshot_index` | 上交所、深交所、北交所指数 | `ad.constant.Period.snapshot.value` | `ad.constant.SnapshotIndex` |
| `onSnapshot` | 沪深北股票 Level-1 | `ad.constant.Period.snapshot.value` | `ad.constant.Snapshot` |
| `onSnapshot_future` | 中金所、上期所、大商所、郑商所、上期所能源期货 | `ad.constant.Period.snapshot_future.value` | `ad.constant.SnapshotFuture` |
| `onSnapshot_etf` | 沪深 ETF | `ad.constant.Period.snapshot.value` | `ad.constant.Snapshot` |
| `onSnapshot_kzz` | 沪深可转债 | `ad.constant.Period.snapshot.value` | `ad.constant.Snapshot` |
| `onSnapshot_hkt` | 港股通 | `ad.constant.Period.snapshot_hkt.value` | `ad.constant.SnapshotHKT` |
| `OnKLine` | 股票、指数、ETF、期货等 | `ad.constant.Period.*`（分钟/日/周/月/年） | `ad.constant.Kline` |

示例：
```python
sub_data = ad.SubscribeData()
codes = ad.BaseData().get_code_list('EXTRA_STOCK_A')

@sub_data.register(code_list=codes[:10], period=ad.constant.Period.snapshot.value)
def on_snapshot(data, period):
    print(period, data.code, data.last_price)

sub_data.run()
```

---

## 历史行情查询（MarketData）

先获取交易日历并实例化 `MarketData(calendar)`。

### MarketData.query_snapshot
函数签名：
```python
MarketData.query_snapshot(
    code_list: list[str],
    begin_date: int,
    end_date: int
) -> dict[str, pandas.DataFrame]
```

返回值：字典，键为代码，值为快照 DataFrame。DataFrame 列与订阅快照一致。

### MarketData.query_kline
函数签名：
```python
MarketData.query_kline(
    code_list: list[str],
    begin_date: int,
    end_date: int,
    period: ad.constant.Period
) -> dict[str, pandas.DataFrame]
```

返回值：字典，值为 K 线 DataFrame，列定义见 `data_types.md#kline`。

---

## 财务数据（InfoData）

所有函数均支持 `local_path` 与 `is_local` 参数，结构与 `get_history_stock_status` 相同，本文仅列出差异部分。

| 函数 | 功能 | 关键字段示例 |
| ---- | ---- | ---- |
| `get_balance_sheet` | 资产负债表 | `TOTAL_ASSETS`、`TOTAL_LIAB`、`EQUITY_ATTR_P` |
| `get_cash_flow` | 现金流量表 | `NET_CASH_OPERATE`、`NET_CASH_INVEST`、`NET_CASH_FINANCE` |
| `get_income` | 利润表 | `OPERATING_REV`、`NET_PROFIT`、`BASIC_EPS` |
| `get_profit_express` | 业绩快报 | `TOTAL_OPERATE_INCOME`、`NET_PROFIT`、`BASIC_EPS`、`REPORT_TYPE` |
| `get_profit_notice` | 业绩预告 | `PROFIT_RANGE_MIN`、`PROFIT_RANGE_MAX`、`P_CHANGE_RANGE`、`PROFIT_NOTICE_TYPE` |

> 全字段定义与取值约束参见 `AmazingData_API.md` 3.5.5.x 章节。

示例：
```python
info_data = ad.InfoData()
codes = ad.BaseData().get_hist_code_list(start_date=20240101, end_date=20240501, local_path='D://AmazingData_local_data//')
balance_df = info_data.get_balance_sheet(codes)
```

---

## 股东股本数据（InfoData）

| 函数 | 功能 | 返回内容摘要 |
| ---- | ---- | ---- |
| `get_share_holder` | 十大股东 | `HOLDER_NAME`、`HOLDER_QUANTITY`、`HOLDER_PCT` 等 |
| `get_holder_num` | 股东户数 | `HOLDER_NUM`、`HOLDER_NUM_CHANGE`、`AVG_HOLD_NUM` |
| `get_equity_structure` | 股本结构 | `TOTAL_SHARE`、`FLOAT_SHARE`、`NONFLOAT_SHARE` |
| `get_equity_pledge_freeze` | 股权质押/冻结 | `PLEDGE_NUM`、`FREEZE_NUM`、`UNFREEZE_DATE` |
| `get_equity_restricted` | 限售股解禁 | `LISTED_DATE`、`RESTRICTED_NUM`、`RESTRICTED_RATIO` |

所有接口支持 `local_path` 与 `is_local`，字段详见 `AmazingData_API.md` 3.5.6.x。

---

## 权益与分红数据（InfoData）

| 函数 | 功能 | 关键字段示例 |
| ---- | ---- | ---- |
| `get_dividend` | 分红方案 | `DIV_PROGRESS`、`DIV_TYPE`、`CASH_DIVIDEND`、`BONUS_RATIO` |
| `get_right_issue` | 配股信息 | `PROGRESS`、`PRICE`、`RATIO`、`RIGHTSISSUE_YEAR` |

配套代码表 `DIV_PROGRESS`、`PROGRESS` 的取值定义见 `data_types.md` 附录 4.1.7 和 4.1.8。

---

## 融资融券数据（InfoData）

| 函数 | 功能 | 返回内容摘要 |
| ---- | ---- | ---- |
| `get_margin_summary` | 融资融券成交汇总 | `MARGIN_BUY_VALUE`、`MARGIN_SELL_VALUE`、`SEC_BALANCE` |
| `get_margin_detail` | 融资融券交易明细 | `MARGIN_PURCHASE`、`STOCK_BALANCE`、`MARGIN_REPAY` |

接口同样支持本地缓存参数，字段定义参见 `AmazingData_API.md` 3.5.8.x。

---

## 龙虎榜数据（InfoData）

### InfoData.get_long_hu_bang
函数签名：
```python
InfoData.get_long_hu_bang(
    code_list: list[str],
    local_path: str,
    is_local: bool = True
) -> pandas.DataFrame
```

返回值：包含龙虎榜成交金额、买入/卖出营业部、累计占比等字段的 DataFrame。

---

## 附录与参考

- `docs/datasources/amazingdata/AmazingData_API.md`：PDF 全量展开，覆盖所有字段与取值约束。
- `docs/datasources/amazingdata/data_types.md`：枚举、数据结构与字段说明的结构化整理。
- `docs/datasources/amazingdata/quick_start.md`：登录、查询、订阅的基本示例。
- `docs/datasources/amazingdata/api_guide.md`：接口使用流程、最佳实践与故障排查。

> 修改或新增接口时，请先更新 `AmazingData_API.md` 或同步最新 PDF，再据此调整本参考文档与 `data_types.md`、`api_guide.md`、`quick_start.md`。
