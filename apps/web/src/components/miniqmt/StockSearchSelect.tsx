/**
 * 股票搜索选择组件
 * 从缓存 API 加载股票列表，支持代码/名称/拼音搜索
 */
import React, { useState } from 'react'
import { Select, Spin, Button, Space, Typography } from 'antd'
import request from '@/api/request'

const { Option } = Select
const { Text } = Typography

export interface StockOption {
    symbol: string
    name: string
    pinyin: string
}

export interface StockSearchSelectProps {
    value: string
    onChange: (value: string) => void
    placeholder?: string
    style?: React.CSSProperties
}

export const StockSearchSelect: React.FC<StockSearchSelectProps> = ({
    value,
    onChange,
    placeholder = '输入代码或搜索股票',
    style = { width: 280 },
}) => {
    const [options, setOptions] = useState<StockOption[]>([])
    const [loading, setLoading] = useState(false)
    const [searchValue, setSearchValue] = useState('')
    const [refreshing, setRefreshing] = useState(false)

    // 从 API 加载股票列表
    const fetchStockList = async () => {
        setLoading(true)
        try {
            const res = await request.get<{
                success: boolean
                data?: StockOption[]
                refreshing?: boolean
            }>('/miniqmt/xtdata/stock-list', {
                skipBackendCheck: true,
            } as any)

            if ((res as any).refreshing) {
                setRefreshing(true)
                setTimeout(fetchStockList, 3000)
            } else if ((res as any).success && (res as any).data?.length > 0) {
                setOptions((res as any).data as StockOption[])
                setRefreshing(false)
            }
        } catch (err) {
            console.warn('加载股票列表失败', err)
        } finally {
            setLoading(false)
        }
    }

    // 首次加载
    React.useEffect(() => {
        fetchStockList()
    }, [])

    // 根据搜索词过滤选项
    const filteredOptions = options.filter((stock) => {
        if (!searchValue) return true
        const lower = searchValue.toLowerCase()
        return (
            stock.symbol.toLowerCase().includes(lower) ||
            stock.name.toLowerCase().includes(lower) ||
            stock.pinyin.toLowerCase().includes(lower)
        )
    })

    // 处理选择或输入
    const handleSelect = (val: string) => {
        onChange(val)
        setSearchValue('')
    }

    // 获取显示值
    const getDisplayValue = () => {
        if (!value) return undefined
        const matched = options.find(opt => opt.symbol === value)
        if (matched) {
            return { value: matched.symbol, label: `${matched.name} (${matched.symbol})` }
        }
        return { value, label: value }
    }

    return (
        <Select
            showSearch
            labelInValue
            value={getDisplayValue()}
            onChange={(opt: any) => handleSelect(opt?.value || opt)}
            onSearch={setSearchValue}
            searchValue={searchValue}
            filterOption={false}
            loading={loading}
            placeholder={refreshing ? '缓存初始化中...' : placeholder}
            style={style}
            dropdownMatchSelectWidth={false}
            optionLabelProp="label"
            notFoundContent={
                loading ? <Spin size="small" /> : (
                    searchValue ? (
                        <div style={{ padding: 8 }}>
                            <Button
                                type="link"
                                size="small"
                                onClick={() => handleSelect(searchValue)}
                            >
                                使用 "{searchValue}" 作为股票代码
                            </Button>
                        </div>
                    ) : (refreshing ? '缓存初始化中...' : '输入代码或名称搜索')
                )
            }
        >
            {filteredOptions.slice(0, 100).map((opt) => (
                <Option key={opt.symbol} value={opt.symbol} label={`${opt.name} (${opt.symbol})`}>
                    <Space>
                        <Text strong>{opt.symbol}</Text>
                        <Text type="secondary">{opt.name}</Text>
                        {opt.pinyin && <Text type="secondary" style={{ fontSize: 12 }}>({opt.pinyin})</Text>}
                    </Space>
                </Option>
            ))}
        </Select>
    )
}
