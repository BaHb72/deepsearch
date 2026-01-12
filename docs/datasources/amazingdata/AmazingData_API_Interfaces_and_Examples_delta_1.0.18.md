# AmazingData 1.0.18 差异标注（确定性，剔除无意义项）

说明：本文件在“只做减法”的基础上，补充对新增/变更项的差异标注，但严格基于 SDK 1.0.18
的真实结构（运行时反射/签名/文档字符串），不凭名称猜测用途；仅记录具备实质信息的条目（签名、参数含义、可选值等）。

## 一、文档存在但 SDK 不存在（减法）

- SubscribeData 回调命名 onSnapshotindex / onSnapshot / onSnapshotfuture / onSnapshotetf / onSnapshotkzz /
  onSnapshothkt：
  - 标注：SDK 1.0.18 未提供同名 API；这些为示例函数名，不对应 SDK 内置回调。

- 市场枚举 market：
  - 标注：SDK 1.0.18 未提供 `Market` 枚举类型；应以 `AmazingData.utils.security_type.security_type_info` 的配置为准。

## 二、SDK 存在但文档未覆盖（新增，提供确定性信息）

仅记录具备可验证“签名/枚举/文档字符串”的条目；不对用途进行主观猜测。

### 2.1 SubscribeData 内置回调（方法签名）

- OnMDSnapshot(self, data, err)
- OnMDIndexSnapshot(self, data, err)
- OnMDHKTSnapshot(self, data, err)
- OnMDFutureSnapshot(self, data, err)
- OnMDOptionSnapshot(self, data, err)
- OnMDOrderBook(self, data, err)
- OnMDOrderBookSnapshot(self, data, err)
- OnMDOrderQueue(self, data, err)
- OnMDTickOrder(self, data, err)
- OnMDTickExecution(self, data, err)
- OnMDAfterHourFixedPriceSnapshot(self, data, err)
- OnMDCSIIndexSnapshot(self, data, err)
- OnMDCnIndexSnapshot(self, data, err)
- OnMDHKTProductStatus(self, data, err)
- OnMDHKTRealtimeLimit(self, data, err)
- OnMDHKTVCM(self, data, err)
- OnSnapshotDerive(self, data, err)
- OnKLine(self, data, kline_type, err)

说明：见 `AmazingData.subscribe_api.on_data.SubscribeData` 反射结果。所有回调统一 `(data, err)` 形态（`OnKLine` 另含
`kline_type`）。`register(self, code_list, period=None)` 为订阅注册入口；`process_data(self, data, period)` 为分发入口。

### 2.2 Period 枚举（完整名称清单）

- snapshotL2, order, execution, order_queue, snapshotHKT, snapshotfuture, snapshot, day,
  min1, min3, min5, min10, min15, min30, min60, min120, week, month, season, year

说明：来源于 `AmazingData.utils.constant.Period.__members__`；其中事件类（如 snapshot/order/...）与历史 K 线粒度（如
minN/day/...）并存。默认值示例：`MarketData.query_kline(..., period=10000, ...)`（仅记录数值，不推断语义映射）。

### 2.3 BaseData 新增/补充（方法签名与要点）

- get_future_code_info(self, security_type='EXTRA_FUTURE')
  - 文档字符串包含子类型示例：`ZJ_FUTURE`（中金所）/`SQ_FUTURE`（上期所）/`DS_FUTURE`（大商所）/`ZS_FUTURE`（郑商所）/
      `SN_FUTURE`（上能所）。
- get_calendar(self, data_type='str', market='SH', date=YYYYMMDD)
  - data_type 允许值：'datetime' 或 'str'；market 允许值示例：SH / SZ / BJ。

### 2.4 security_type 相关（以配置为准）

- extra_type 额外存在 `EXTRA_IDNEX_A_SH_SZ`（注意拼写）等键；完整键集合来自
  `AmazingData.utils.security_type.security_type_info['extra_type']`。
- base_type 包含 `MARKET_SH`、`MARKET_SZ`、`SH_ETF`、`SZ_ETF`、`ZJ_FUTURE`、`SQ_FUTURE` 等键及其代码正则；以
  `security_type_info['base_type']` 为准。

## 三、签名差异（与文档示例可能不一致）

不更改原有文档，仅在此记录 SDK 的确定性签名，供实现方按需对齐调用层：

- MarketData.query_snapshot(self, code_list, begin_date, end_date, **kwargs)
- MarketData.query_kline(self, code_list, begin_date=20240101, end_date=20991231, period=10000, **kwargs)
- SubscribeData.register(self, code_list, period=None)
- BaseData.get_code_list(self, security_type='EXTRA_STOCK_A_SH_SZ')
- BaseData.get_hist_code_list(self, security_type='EXTRA_STOCK_A_SH_SZ', start_date=20240101, end_date=20240701,
  local_path='D://AmazingData_local_data//')
- InfoData.get_margin_summary(self, local_path='D://AmazingData_local_data//', is_local=True, **kwargs)  # 无 code_list
  形参

以上均源自运行时 `inspect.signature`。如与现有文档呈现不同，请以此签名为准调整调用端；文档主体暂不增删，以降低官方改动对系统的连带破坏。
