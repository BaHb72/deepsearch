/**
 * Rich Data Layer - 类型定义
 * 保留完整信息的多数据源统一格式
 */
import type { DataSourceType, DataCapability } from '../types'

// ============================================================
// 元信息
// ============================================================

/** 数据响应元信息 */
export interface RichDataMeta {
    /** 数据来源 */
    source: DataSourceType
    /** 能力/接口类型 */
    capability: DataCapability
    /** 获取时间戳 */
    timestamp: number
    /** 响应延迟 (ms) */
    latency: number
    /** 是否缓存数据 */
    cached: boolean
    /** 降级原因（若发生数据源切换） */
    fallbackReason?: string | null
    /** 路由尝试轨迹 */
    attempts?: Array<{
        provider: string
        success: boolean
        reason_code?: string | null
        reason_detail?: string | null
        latency_ms?: number | null
    }>
}

// ============================================================
// 核心标准字段 (跨数据源通用)
// ============================================================

/** 核心行情字段 */
export interface CoreQuoteData {
    code: string            // 股票代码
    name?: string           // 名称
    price?: number          // 最新价
    open?: number           // 开盘价
    high?: number           // 最高价
    low?: number            // 最低价
    close?: number          // 收盘价
    preClose?: number       // 昨收
    change?: number         // 涨跌额
    changePct?: number      // 涨跌幅 (%)
    volume?: number         // 成交量
    amount?: number         // 成交额
    time?: number           // 时间戳
}

/** 核心K线字段 */
export interface CoreKlineData {
    time: number | string   // 时间戳或日期字符串
    open: number
    high: number
    low: number
    close: number
    volume: number
    amount?: number
}

/** 核心财务字段 */
export interface CoreFinancialData {
    code: string            // 股票代码
    reportDate?: string     // 报告期
    revenue?: number        // 营业收入
    netProfit?: number      // 净利润
    totalAssets?: number    // 总资产
    totalLiab?: number      // 总负债
    totalEquity?: number    // 股东权益
}

/** 核心龙虎榜字段 */
export interface CoreDragonTigerData {
    code: string            // 股票代码
    name?: string           // 名称
    tradeDate: string       // 交易日期
    changeRate?: number     // 涨跌幅
    buyAmount?: number      // 买入额
    sellAmount?: number     // 卖出额
    netAmount?: number      // 净买入
    reason?: string         // 上榜原因
}

/** 核心大宗交易字段 */
export interface CoreBlockTradingData {
    code: string            // 股票代码
    name?: string           // 名称
    tradeDate: string       // 交易日期
    price?: number          // 成交价
    volume?: number         // 成交量
    amount?: number         // 成交额
    buyerName?: string      // 买方
    sellerName?: string     // 卖方
}

/** 核心股东数据字段 */
export interface CoreShareholderData {
    code: string            // 股票代码
    annDate?: string        // 公告日期
    holderNum?: number      // 股东户数
    holderNumChange?: number // 变化数
    holderNumChangePct?: number // 变化比例
}

// ============================================================
// 核心字段联合类型
// ============================================================

export type CoreData =
    | CoreQuoteData
    | CoreKlineData
    | CoreFinancialData
    | CoreDragonTigerData
    | CoreBlockTradingData
    | CoreShareholderData
    | Record<string, unknown>  // 兜底

// ============================================================
// Rich Data Response
// ============================================================

/** 富数据响应 - 保留完整信息 */
export interface RichDataResponse<TCore = CoreData, TRaw = Record<string, unknown>> {
    /** 请求是否成功 */
    success: boolean

    /** 元信息 */
    _meta: RichDataMeta

    /** 核心标准字段数组 (跨数据源通用) */
    core: TCore[]

    /** 扩展字段数组 (各数据源特有，不裁剪) */
    extended: Record<string, unknown>[]

    /** 原始数据 (可选，调试用) */
    _raw?: TRaw[]

    /** 数据条数 */
    count: number

    /** 错误信息 */
    error?: string
}

// ============================================================
// 字段映射类型
// ============================================================

/** 单个字段映射 */
export interface FieldMapping {
    /** 标准字段名 */
    core: string
    /** 各数据源对应的原始字段名 */
    sources: Partial<Record<DataSourceType, string | string[]>>
    /** 可选的转换函数 */
    transform?: (value: unknown, source: DataSourceType) => unknown
    /** 字段描述 */
    description?: string
}

/** 能力的字段映射配置 */
export interface CapabilityFieldMappings {
    capability: DataCapability
    mappings: FieldMapping[]
}

// ============================================================
// Hook 返回类型
// ============================================================

/** useRichDataSource Hook 选项 */
export interface UseRichDataSourceOptions {
    capability: DataCapability
    params: Record<string, unknown>
    preferredSource?: DataSourceType
    strictSource?: boolean
    autoFetch?: boolean
    deps?: unknown[]
    /** 是否保留原始数据 */
    preserveRaw?: boolean
    /** 慢加载监控上下文（用于全局慢加载提示） */
    monitor?: SlowLoadMonitorContext
}

/** 慢加载监控上下文 */
export interface SlowLoadMonitorContext {
    pageKey: string
    pageName: string
    moduleKey: string
    moduleName: string
    slowThresholdMs?: number
    onSwitchSource?: (target: DataSourceType) => void | Promise<void>
}

/** useRichDataSource Hook 返回值 */
export interface UseRichDataSourceResult<TCore = CoreData> {
    /** 核心标准数据 */
    data: TCore[]
    /** 扩展数据 */
    extended: Record<string, unknown>[]
    /** 元信息 */
    meta: RichDataMeta | null
    /** 加载状态 */
    loading: boolean
    /** 错误信息 */
    error: string | null
    /** 刷新函数 */
    refresh: () => Promise<void>
    /** 原始响应 */
    response: RichDataResponse<TCore> | null
}
