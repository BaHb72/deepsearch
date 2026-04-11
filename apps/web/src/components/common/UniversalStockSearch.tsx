/**
 * 通用股票搜索选择组件
 * 支持多数据源切换：MiniQMT / AmazingData
 * 使用适配器模式实现数据源解耦
 */
import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Select, Spin, Button, Space, Typography } from 'antd'
import {
    loadStockOptions,
    searchStockOptions,
    type StockListSource,
    type StockOption,
} from '@/api/stock-search'

const { Option } = Select
const { Text } = Typography

// ============= 类型定义 =============

export type { StockOption } from '@/api/stock-search'

/** 数据源类型 */
export type DataSourceType = 'miniqmt' | 'amazingdata'

/** 数据源适配器接口 */
interface StockDataAdapter {
    /** 获取股票列表 */
    fetchStockList: () => Promise<{
        data: StockOption[]
        refreshing?: boolean
        source?: StockListSource
    }>
    /** 数据源显示名称 */
    displayName: string
    /** 占位符文本 */
    placeholder: string
}

// ============= 数据源适配器实现 =============

const dataSourceAdapters: Record<DataSourceType, StockDataAdapter> = {
    miniqmt: {
        displayName: 'MiniQMT',
        placeholder: '输入代码或搜索股票 (MiniQMT)',
        fetchStockList: async () => {
            const result = await loadStockOptions()
            return {
                data: result.options,
                refreshing: result.refreshing,
                source: result.source,
            }
        },
    },
    amazingdata: {
        displayName: 'AmazingData',
        placeholder: '输入代码或搜索股票 (AmazingData)',
        fetchStockList: async () => {
            const result = await loadStockOptions()
            return {
                data: result.options,
                refreshing: result.refreshing,
                source: result.source,
            }
        },
    },
}

// ============= 组件 Props =============

export interface UniversalStockSearchProps {
    /** 数据源类型 (可选，默认 miniqmt) */
    dataSource?: DataSourceType
    /** 当前选中值 */
    value: string
    /** 值变更回调 (同时传递 symbol 和 name) */
    onChange: (value: string, name?: string) => void
    /** 自定义占位符 */
    placeholder?: string
    /** 自定义样式 */
    style?: React.CSSProperties
    /** 是否显示数据源标签 */
    showSourceLabel?: boolean
}

// ============= 组件实现 =============

export const UniversalStockSearch: React.FC<UniversalStockSearchProps> = ({
    dataSource,
    value,
    onChange,
    placeholder,
    style = { width: 280 },
    showSourceLabel = false,
}) => {
    const [options, setOptions] = useState<StockOption[]>([])
    const [loading, setLoading] = useState(false)
    const [searching, setSearching] = useState(false)
    const [searchValue, setSearchValue] = useState('')
    const [refreshing, setRefreshing] = useState(false)
    const [isFallbackSource, setIsFallbackSource] = useState(false)
    const [dynamicOptions, setDynamicOptions] = useState<StockOption[]>([])
    const retryTimerRef = useRef<number | null>(null)

    // 获取当前数据源适配器 (默认使用 miniqmt)
    const actualSource = dataSource || 'miniqmt'
    const adapter = dataSourceAdapters[actualSource]

    const isKeywordMatch = useCallback((stock: StockOption, keyword: string): boolean => {
        const lower = keyword.toLowerCase()
        return (
            stock.symbol.toLowerCase().includes(lower) ||
            stock.name.toLowerCase().includes(lower) ||
            (stock.pinyin?.toLowerCase().includes(lower) ?? false)
        )
    }, [])

    const isLikelyStockCode = useCallback((input: string): boolean => {
        const normalized = input.trim().toUpperCase()
        if (!normalized) return false
        return /^(?:\d{6}|(?:\d{6}\.(?:SH|SZ|BJ))|(?:(?:SH|SZ|BJ)\d{6}))$/i.test(normalized)
    }, [])

    // 从数据源加载股票列表
    const fetchStockList = useCallback(async () => {
        setLoading(true)
        try {
            const result = await adapter.fetchStockList()
            if (result.refreshing) {
                setRefreshing(true)
                setIsFallbackSource(false)
                if (retryTimerRef.current !== null) {
                    window.clearTimeout(retryTimerRef.current)
                }
                retryTimerRef.current = window.setTimeout(() => {
                    retryTimerRef.current = null
                    void fetchStockList()
                }, 3000)
            } else {
                setOptions(result.data)
                setRefreshing(false)
                setIsFallbackSource((result.source ?? 'none') !== 'miniqmt')
            }
        } catch (err) {
            console.warn(`[${adapter.displayName}] 加载股票列表失败`, err)
            setOptions([])
            setRefreshing(false)
            setIsFallbackSource(true)
        } finally {
            setLoading(false)
        }
    }, [adapter])

    // 数据源变化时重新加载
    useEffect(() => {
        setOptions([]) // 清空旧数据
        setDynamicOptions([])
        setSearching(false)
        setIsFallbackSource(false)
        fetchStockList()
        return () => {
            if (retryTimerRef.current !== null) {
                window.clearTimeout(retryTimerRef.current)
                retryTimerRef.current = null
            }
        }
    }, [actualSource, fetchStockList])

    // 全量股票列表为空时，按关键字实时查询候选项
    useEffect(() => {
        const keyword = searchValue.trim()
        if (!keyword || refreshing) {
            setDynamicOptions([])
            setSearching(false)
            return
        }

        const localMatches = options.filter((item) => isKeywordMatch(item, keyword))
        if (localMatches.length > 0) {
            setDynamicOptions([])
            setSearching(false)
            return
        }

        let cancelled = false
        const timer = window.setTimeout(async () => {
            setSearching(true)
            try {
                const matches = await searchStockOptions(keyword)
                if (!cancelled) {
                    setDynamicOptions(matches)
                }
            } catch {
                if (!cancelled) {
                    setDynamicOptions([])
                }
            } finally {
                if (!cancelled) {
                    setSearching(false)
                }
            }
        }, 250)

        return () => {
            cancelled = true
            window.clearTimeout(timer)
        }
    }, [isKeywordMatch, options, refreshing, searchValue])

    const effectiveOptions = React.useMemo(() => {
        if (dynamicOptions.length === 0) {
            return options
        }
        const merged = new Map<string, StockOption>()
        for (const option of dynamicOptions) {
            merged.set(option.symbol, option)
        }
        for (const option of options) {
            if (!merged.has(option.symbol)) {
                merged.set(option.symbol, option)
            }
        }
        return Array.from(merged.values())
    }, [dynamicOptions, options])

    // 根据搜索词过滤选项
    const filteredOptions = effectiveOptions.filter((stock) => {
        if (!searchValue) return true
        return isKeywordMatch(stock, searchValue)
    })

    // 处理选择或输入
    const handleSelect = (val: string) => {
        // 查找对应的股票名称
        const matched = effectiveOptions.find((opt) => opt.symbol === val)
        const name = matched?.name || undefined
        onChange(val, name)
        setSearchValue('')
    }

    // 获取显示值
    const getDisplayValue = () => {
        if (!value) return undefined
        const matched = effectiveOptions.find((opt) => opt.symbol === value)
        if (matched) {
            return { value: matched.symbol, label: `${matched.name} (${matched.symbol})` }
        }
        return { value, label: value }
    }

    const currentPlaceholder =
        placeholder || (isFallbackSource ? '数据源未就绪，支持直接输入股票代码' : adapter.placeholder)
    const canUseRawCode = isLikelyStockCode(searchValue)

    return (
        <Space>
            {showSourceLabel && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                    [{adapter.displayName}]
                </Text>
            )}
            <Select
                showSearch
                labelInValue
                value={getDisplayValue()}
                onChange={(opt: any) => handleSelect(opt?.value || opt)}
                onSearch={setSearchValue}
                searchValue={searchValue}
                filterOption={false}
                loading={loading || searching}
                placeholder={refreshing ? '缓存初始化中...' : currentPlaceholder}
                style={style}
                dropdownMatchSelectWidth={false}
                optionLabelProp="label"
                notFoundContent={
                    loading || searching ? (
                        <Spin size="small" />
                    ) : searchValue ? (
                        <div style={{ padding: 8 }}>
                            {canUseRawCode ? (
                                <Button
                                    type="link"
                                    size="small"
                                    onClick={() => handleSelect(searchValue.trim().toUpperCase())}
                                >
                                    使用 {searchValue.trim().toUpperCase()} 作为股票代码
                                </Button>
                            ) : (
                                <Text type="secondary" style={{ fontSize: 12 }}>
                                    未匹配到股票，请尝试输入代码（如 300757 或 300757.SZ）
                                </Text>
                            )}
                        </div>
                    ) : refreshing ? (
                        '缓存初始化中...'
                    ) : (
                        '输入代码或名称搜索'
                    )
                }
            >
                {filteredOptions.slice(0, 100).map((opt) => (
                    <Option
                        key={opt.symbol}
                        value={opt.symbol}
                        label={`${opt.name} (${opt.symbol})`}
                    >
                        <Space>
                            <Text strong>{opt.symbol}</Text>
                            <Text type="secondary">{opt.name}</Text>
                        </Space>
                    </Option>
                ))}
            </Select>
        </Space>
    )
}

export default UniversalStockSearch
