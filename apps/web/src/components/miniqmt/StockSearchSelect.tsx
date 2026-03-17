/**
 * MiniQMT 股票搜索组件
 * 复用通用股票搜索实现，避免重复维护数据加载和降级逻辑
 */
import React from 'react'
import UniversalStockSearch, { type StockOption } from '@/components/common/UniversalStockSearch'

export type { StockOption }

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
}) => (
    <UniversalStockSearch
        dataSource="miniqmt"
        value={value}
        onChange={(nextValue) => onChange(nextValue)}
        placeholder={placeholder}
        style={style}
    />
)
