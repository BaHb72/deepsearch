# AkShare API 映射文档

## 概述
本文档整理了 AkShare 库的标准 API 接口，用于规范化数据源访问。

## 核心 API 接口

### 1. 实时行情类

#### stock_zh_a_spot_em - A股实时行情
```python
ak.stock_zh_a_spot_em()
```
- **功能**: 获取所有A股实时行情数据
- **参数**: 无
- **返回字段**:
  - 代码: 股票代码
  - 名称: 股票名称
  - 最新价: 当前价格
  - 涨跌幅: 涨跌百分比
  - 涨跌额: 涨跌金额
  - 成交量: 成交量（手）
  - 成交额: 成交金额
  - 振幅: 振幅百分比
  - 最高: 最高价
  - 最低: 最低价
  - 今开: 开盘价
  - 昨收: 昨日收盘价
  - 换手率: 换手率百分比
  - 市盈率-动态: 动态市盈率
  - 市净率: 市净率
  - 总市值: 总市值
  - 流通市值: 流通市值

#### stock_zh_b_spot_em - B股实时行情
```python
ak.stock_zh_b_spot_em()
```
- **功能**: 获取B股实时行情
- **参数**: 无
- **返回**: 类似A股格式

#### stock_kc_a_spot_em - 科创板实时行情
```python
ak.stock_kc_a_spot_em()
```
- **功能**: 获取科创板实时行情
- **参数**: 无
- **返回**: 类似A股格式

#### stock_zh_index_spot_em - 指数实时行情
```python
ak.stock_zh_index_spot_em()
```
- **功能**: 获取所有指数实时行情
- **参数**: 无
- **返回字段**:
  - 代码: 指数代码
  - 名称: 指数名称
  - 最新价: 当前点位
  - 涨跌幅: 涨跌百分比
  - 涨跌额: 涨跌点数
  - 成交量: 成交量
  - 成交额: 成交金额

### 2. 历史数据类

#### stock_zh_a_hist - A股历史数据（日/周/月）
```python
ak.stock_zh_a_hist(symbol, period, start_date, end_date, adjust)
```
- **功能**: 获取股票历史K线数据
- **参数**:
  - symbol (str): 股票代码，如 "000001"
  - period (str): 周期类型 "daily"/"weekly"/"monthly"
  - start_date (str): 开始日期 "20200101"
  - end_date (str): 结束日期 "20231231"
  - adjust (str): 复权类型 ""(不复权)/"qfq"(前复权)/"hfq"(后复权)
- **返回字段**:
  - 日期: 交易日期
  - 开盘: 开盘价
  - 收盘: 收盘价
  - 最高: 最高价
  - 最低: 最低价
  - 成交量: 成交量
  - 成交额: 成交金额
  - 振幅: 振幅
  - 涨跌幅: 涨跌幅
  - 涨跌额: 涨跌额
  - 换手率: 换手率

#### stock_zh_a_hist_min_em - A股分钟数据
```python
ak.stock_zh_a_hist_min_em(symbol, start_date, end_date, period, adjust)
```
- **功能**: 获取分钟级别K线数据
- **参数**:
  - symbol (str): 股票代码
  - start_date (str): 开始日期时间 "2024-01-01 09:30:00"
  - end_date (str): 结束日期时间 "2024-01-01 15:00:00"
  - period (str): 周期 "1"/"5"/"15"/"30"/"60" (分钟)
  - adjust (str): 复权类型
- **返回字段**: 类似日K线数据

### 3. 股票信息类

#### stock_individual_info_em - 个股信息
```python
ak.stock_individual_info_em(symbol)
```
- **功能**: 获取个股详细信息
- **参数**:
  - symbol (str): 股票代码
- **返回字段** (DataFrame with item/value pairs):
  - 股票简称: 股票名称
  - 股票代码: 完整代码
  - 昨收: 昨日收盘价
  - 今开: 今日开盘价
  - 最高: 最高价
  - 最低: 最低价
  - 最新: 最新价格
  - 成交量: 成交量
  - 成交额: 成交金额
  - 涨跌: 涨跌金额
  - 涨跌幅: 涨跌百分比
  - 总股本: 总股本数量
  - 流通股: 流通股数量
  - 总市值: 总市值
  - 流通市值: 流通市值
  - 行业: 所属行业
  - 上市时间: 上市日期
  - 市盈率-动态: PE ratio
  - 市净率: PB ratio

#### stock_info_a_code_name - 股票代码名称映射
```python
ak.stock_info_a_code_name()
```
- **功能**: 获取所有A股代码和名称
- **参数**: 无
- **返回字段**:
  - code: 股票代码
  - name: 股票名称

### 4. 筹码分布类

#### stock_cyq_em - 筹码分布
```python
ak.stock_cyq_em(symbol, adjust)
```
- **功能**: 获取筹码分布数据
- **参数**:
  - symbol (str): 股票代码
  - adjust (str): 复权类型 "qfq"/"hfq"/""
- **返回字段**:
  - 日期: 交易日期
  - 获利比例: 获利筹码比例
  - 平均成本: 平均持仓成本
  - 90成本-10成本: 筹码集中度
  - 集中度: 筹码集中度百分比

### 5. 市场统计类

#### stock_sse_summary - 上交所市场总貌
```python
ak.stock_sse_summary()
```
- **功能**: 获取上交所市场统计
- **参数**: 无
- **返回**: 市场总市值、流通市值、成交额等

#### stock_szse_summary - 深交所市场总貌
```python
ak.stock_szse_summary(date)
```
- **功能**: 获取深交所市场统计
- **参数**:
  - date (str): 日期 "20240101"
- **返回**: 类似上交所统计

### 6. 特殊板块类

#### stock_zh_a_st_em - ST股票列表
```python
ak.stock_zh_a_st_em()
```
- **功能**: 获取ST/ST股票列表
- **参数**: 无
- **返回**: ST股票的实时行情数据

## API 路径映射规则

### CloudFlare Worker 代理路径
- 原始 AkShare API: `stock_zh_a_spot_em`
- Worker 路径: `/api/akshare/stock_zh_a_spot_em`

### 兼容性路径（已废弃，建议更新）
- `/eastmoney/realtime` → `stock_zh_a_spot_em` 
- `/eastmoney/kline` → `stock_zh_a_hist`
- `/eastmoney/test` → 健康检查端点

## 参数标准化

### 日期格式
- AkShare 原始格式: "20240101" (YYYYMMDD)
- 标准化格式: "2024-01-01" (YYYY-MM-DD)
- 转换: `date.replace("-", "")`

### 复权类型
- 不复权: "" 或 "none"
- 前复权: "qfq"
- 后复权: "hfq"

### 周期类型
- 日线: "daily"
- 周线: "weekly"
- 月线: "monthly"
- 分钟线: "1", "5", "15", "30", "60"

## 错误处理

### 常见错误码
- 404: API 不存在
- 401: 认证失败
- 429: 请求频率限制
- 500: 服务器内部错误

### 重试策略
- 最大重试次数: 3
- 指数退避: 1s, 2s, 4s
- 熔断器: 连续失败3次后标记为可疑，5次后标记为不健康

## 性能优化建议

1. **批量查询**: 使用 `stock_zh_a_spot_em` 一次获取所有股票，然后本地筛选
2. **缓存策略**:
   - 实时数据: 10秒
   - 日K线: 5分钟
   - 股票信息: 1小时
3. **并发控制**: 限制并发请求数不超过3个
4. **数据压缩**: 启用 gzip 压缩传输

## 更新日志

### 2025-08-21
- 整理标准 AkShare API 文档
- 统一 API 路径映射规则
- 添加参数标准化说明
- 完善错误处理机制