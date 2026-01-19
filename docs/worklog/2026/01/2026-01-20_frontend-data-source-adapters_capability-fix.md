# 前端数据源适配器: 能力声明与健康检查修复

> 日期: 2026-01-20
> 模块: apps/web/src/services/data-source/adapters/
> 类型: bugfix | enhancement

---

## 为什么要改

### 遇到的问题

前端数据源适配器存在三个问题：

1. **MiniQMT 能力声明不实**
   - `capabilities` 列表声明支持 `stock_basic`
   - 但实际处理器返回 `null`
   - 导致：系统认为 MiniQMT 能提供基础股票信息，但调用时失败

2. **AmazingData 健康检查是假的**
   - `isAvailable()` 直接返回 `true`
   - 导致：无法检测 AmazingData 服务是否真正可用
   - 影响：数据源自动降级机制失效

3. **AmazingData K线能力缺失**
   - 后端 `historyApi.queryKline` 已支持 K线查询
   - 但前端适配器未接入
   - 导致：K线数据只能走 MiniQMT，无法利用 AmazingData 的 K线能力

### 现有方案的问题

- 能力声明与实现不一致，违反"契约式设计"原则
- 健康检查返回假阳性，导致系统无法正确切换数据源

---

## 最终方案

### 修复策略

1. **诚实原则** - 只声明真正能实现的能力
2. **防御性编程** - 健康检查必须真实检测服务状态
3. **能力扩展** - 补充 AmazingData 的 K线能力

### 关键改动

#### 文件: `adapters/miniqmt.ts`

```typescript
// 改之前
const MINIQMT_CAPABILITIES: DataCapability[] = [
    'realtime_quote',
    'stock_kline',
    'tick_data',
    'stock_basic',  // 声称支持但实际返回 null
    'income_statement',
    ...
]

// 改之后
const MINIQMT_CAPABILITIES: DataCapability[] = [
    'realtime_quote',
    'stock_kline',
    'tick_data',
    // stock_basic 未实现真实 API，已移除
    'income_statement',
    ...
]
```

**为什么这样改**: 能力列表是适配器对外的"契约"，声明了却做不到等于欺骗调用方。

#### 文件: `adapters/amazingdata.ts`

```typescript
// 改之前
async isAvailable(): Promise<boolean> {
    return true  // 永远返回 true，无真实检查
}

// 改之后
async isAvailable(): Promise<boolean> {
    try {
        const res = await getApiInfo()  // 调用轻量级 API
        return res.data !== null && res.data !== undefined
    } catch {
        return false
    }
}
```

**为什么这样改**:

- `getApiInfo()` 是最轻量的 API，只返回元信息
- 真实检测网络连接和服务状态
- 失败时正确返回 false，触发降级逻辑

#### 文件: `adapters/amazingdata.ts` (K线能力)

```typescript
// 新增 stock_kline handler
stock_kline: async (params) => {
    const codeList = params.codes || (params.code ? [params.code] : [])
    if (codeList.length === 0) return null

    // 日期格式转换: "2026-01-20" -> 20260120
    const beginDate = params.startDate
        ? parseInt(params.startDate.replace(/-/g, ''), 10)
        : undefined

    // 周期映射: 前端格式 -> AmazingData 格式
    const periodMap = {
        '1d': 'daily', '1w': 'weekly', '1M': 'monthly',
        '1min': '1min', '5min': '5min', ...
    }

    const res = await historyApi.queryKline({
        code_list: codeList,
        begin_date: beginDate || 20200101,
        end_date: endDate || today,
        period: periodMap[params.period] || 'daily',
    })
    return extractDataFrame(res.data)
}
```

**为什么这样改**:

- 前端使用 ISO 日期格式，后端使用数字格式，需要转换
- 周期名称也需要映射（`1d` -> `daily`）
- 适配器的职责就是屏蔽这些差异

---

## 注意事项

### 这个方案的局限

1. **健康检查有网络开销**
   - 每次调用 `isAvailable()` 都会发起 HTTP 请求
   - 如果频繁调用，可能影响性能
   - 建议：调用方应该缓存结果，不要每次请求都检查

2. **K线参数默认值**
   - 如果不传 `startDate`，默认从 2020-01-01 开始
   - 这是硬编码的默认值，可能需要根据业务调整

### 如果要改回去

1. **恢复 stock_basic 能力** - 需要先实现真实的 API 调用
2. **简化健康检查** - 如果确认服务永远在线，可以改回 `return true`

### 相关模式

这次修复遵循的设计原则：

1. **契约式设计** - 声明的能力必须真实实现
2. **防御性编程** - 不信任外部服务的可用性
3. **适配器模式** - 屏蔽后端 API 的格式差异

---

## 关键结论

> 数据源适配器的 capabilities 列表是一份"契约"，声明了就必须做到。
> 健康检查是自动降级机制的基础，必须真实检测服务状态，不能返回假阳性。

---

## 修改文件清单

| 文件 | 修改类型 |
|------|---------|
| `apps/web/src/services/data-source/adapters/miniqmt.ts` | 移除未实现的能力声明 |
| `apps/web/src/services/data-source/adapters/amazingdata.ts` | 实现健康检查 + 添加 K线能力 |
