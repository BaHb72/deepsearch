/**
 * AmazingData 通用工具函数
 */
import type { ColumnsType } from 'antd/es/table'
import { Tooltip } from 'antd'
import React from 'react'
import type { DataFrameResult } from '@/api/amazingdata'

/** DataFrame数据转表格数据 */
export const dataFrameToTableData = (df: DataFrameResult | null | undefined): Record<string, unknown>[] => {
    if (!df || !df.data || df.data.length === 0) return []
    const columns = df.columns || []
    return df.data.map((row, idx) => {
        const record: Record<string, unknown> = { _key: idx }
        columns.forEach((col, i) => {
            record[col] = row[i]
        })
        return record
    })
}

/** 自动生成表格列（基础版） */
export const autoColumns = (df: DataFrameResult | null | undefined): ColumnsType<Record<string, unknown>> => {
    if (!df || !df.columns) return []
    return df.columns.map((col) => ({
        title: col,
        dataIndex: col,
        key: col,
        ellipsis: true,
        width: 120,
    }))
}

/** 自动生成表格列（带Tooltip，支持列拖拽） */
export const autoColumnsWithTooltip = (df: DataFrameResult | null | undefined): ColumnsType<Record<string, unknown>> => {
    if (!df || !df.columns) return []
    return df.columns.map((col) => ({
        title: col,
        dataIndex: col,
        key: col,
        width: 130,
        ellipsis: { showTitle: false },
        render: (value: unknown) => {
            const text = value === null || value === undefined ? '-' : String(value)
            return (
                <Tooltip placement="topLeft" title={text}>
                    <span style={{ whiteSpace: 'nowrap' }}>{text}</span>
                </Tooltip>
            )
        },
    }))
}
