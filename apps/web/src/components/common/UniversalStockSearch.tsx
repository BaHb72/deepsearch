/**
 * 通用股票搜索选择组件
 * 支持多数据源切换：MiniQMT / AmazingData
 * 使用适配器模式实现数据源解耦
 */
import React, { useState, useEffect, useCallback } from 'react'
import { Select, Spin, Button, Space, Typography } from 'antd'
import { loadStockOptions, type StockListSource, type StockOption } from '@/api/stock-search'

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
    const [searchValue, setSearchValue] = useState('')
    const [refreshing, setRefreshing] = useState(false)
    const [isFallbackSource, setIsFallbackSource] = useState(false)

    // 获取当前数据源适配器 (默认使用 miniqmt)
    const actualSource = dataSource || 'miniqmt'
    const adapter = dataSourceAdapters[actualSource]

    // 从数据源加载股票列表
    const fetchStockList = useCallback(async () => {
        setLoading(true)
        try {
            const result = await adapter.fetchStockList()
            if (result.refreshing) {
                setRefreshing(true)
                setIsFallbackSource(false)
                setTimeout(fetchStockList, 3000) // 缓存初始化中，3秒后重试
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
        setIsFallbackSource(false)
        fetchStockList()
    }, [actualSource, fetchStockList])

    // 根据搜索词过滤选项
    const filteredOptions = options.filter((stock) => {
        if (!searchValue) return true
        const lower = searchValue.toLowerCase()
        return (
            stock.symbol.toLowerCase().includes(lower) ||
            stock.name.toLowerCase().includes(lower) ||
            (stock.pinyin?.toLowerCase().includes(lower) ?? false)
        )
    })

    // 处理选择或输入
    const handleSelect = (val: string) => {
        // 查找对应的股票名称
        const matched = options.find((opt) => opt.symbol === val)
        const name = matched?.name || undefined
        onChange(val, name)
        setSearchValue('')
    }

    // 获取显示值
    const getDisplayValue = () => {
        if (!value) return undefined
        const matched = options.find((opt) => opt.symbol === value)
        if (matched) {
            return { value: matched.symbol, label: `${matched.name} (${matched.symbol})` }
        }
        return { value, label: value }
    }

    const currentPlaceholder =
        placeholder || (isFallbackSource ? '数据源未就绪，支持直接输入股票代码' : adapter.placeholder)

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
                loading={loading}
                placeholder={refreshing ? '缓存初始化中...' : currentPlaceholder}
                style={style}
                dropdownMatchSelectWidth={false}
                optionLabelProp="label"
                notFoundContent={
                    loading ? (
                        <Spin size="small" />
                    ) : searchValue ? (
                        <div style={{ padding: 8 }}>
                            <Button
                                type="link"
                                size="small"
                                onClick={() => handleSelect(searchValue)}
                            >
                                使用 "{searchValue}" 作为股票代码
                            </Button>
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
