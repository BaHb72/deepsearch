# 批次7分析结果：图片61-70

## 概览
图片61-70包含SubscribeData模块实时行情订阅回调函数。

---

## 提取的接口信息

### 9. SubscribeData 模块 - 实时行情订阅

#### 9.1 onSnapshot - 股票快照回调 (3.5.6.1)
```python
def onSnapshot(data):
    """股票实时行情快照回调"""
    pass

ad.SubscribeData.subscribe(
    code_list=["000001.SZ"],
    callback=onSnapshot
)
```
**回调参数**:
| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 股票代码 |
| last | float | 最新价 |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| volume | int | 成交量 |
| amount | float | 成交额 |
| bid/ask | list | 五档买卖盘 |

#### 9.2 onSnapshotIndex - 指数快照回调 (3.5.6.2)
```python
def onSnapshotIndex(data):
    """指数实时行情回调"""
    pass
```
**回调参数**: 同onSnapshot

#### 9.3 onSnapshotFuture - 期货快照回调 (3.5.6.3)
```python
def onSnapshotFuture(data):
    """期货实时行情回调"""
    pass
```

#### 9.4 onSnapshotETF - ETF快照回调 (3.5.6.4)
```python
def onSnapshotETF(data):
    """ETF实时行情回调"""
    pass
```

#### 9.5 onSnapshotKZZ - 可转债快照回调 (3.5.6.5)
```python
def onSnapshotKZZ(data):
    """可转债实时行情回调"""
    pass
```

#### 9.6 onSnapshotHKT - 港股通快照回调 (3.5.6.6)
```python
def onSnapshotHKT(data):
    """港股通实时行情回调"""
    pass
```

---

## 实现状态对比

| 接口 | 文档章节 | 现有实现 | 状态 |
|------|----------|----------|------|
| onSnapshot | 3.5.6.1 | 是 | 已实现 |
| onSnapshotIndex | 3.5.6.2 | 是 | 已实现 |
| onSnapshotFuture | 3.5.6.3 | 是 | 已实现 |
| onSnapshotETF | 3.5.6.4 | 是 | 已实现 |
| onSnapshotKZZ | 3.5.6.5 | 是 | 已实现 |
| onSnapshotHKT | 3.5.6.6 | 是 | 已实现 |
