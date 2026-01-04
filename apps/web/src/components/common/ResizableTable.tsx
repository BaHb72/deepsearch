/**
 * 可拖拽调整列宽的表格组件
 * 基于 antd Table 和 react-resizable 实现
 */
import React, { useState, useCallback } from 'react'
import { Table, Tooltip } from 'antd'
import type { TableProps, ColumnsType } from 'antd/es/table'
import { Resizable, ResizeCallbackData } from 'react-resizable'
import 'react-resizable/css/styles.css'

/** 可拖拽的表头单元格 */
const ResizableTitle: React.FC<{
    onResize: (e: React.SyntheticEvent, data: ResizeCallbackData) => void
    width: number
    [key: string]: any
}> = ({ onResize, width, ...restProps }) => {
    if (!width) {
        return <th {...restProps} />
    }

    return (
        <Resizable
            width={width}
            height={0}
            handle={
                <span
                    className="react-resizable-handle"
                    onClick={(e) => e.stopPropagation()}
                    style={{
                        position: 'absolute',
                        right: -5,
                        bottom: 0,
                        top: 0,
                        width: 10,
                        cursor: 'col-resize',
                        zIndex: 1,
                    }}
                />
            }
            onResize={onResize}
            draggableOpts={{ enableUserSelectHack: false }}
        >
            <th {...restProps} />
        </Resizable>
    )
}

/** 为列配置添加 Tooltip 和不换行样式 */
export const withTooltip = <T extends Record<string, unknown>>(
    columns: ColumnsType<T>
): ColumnsType<T> => {
    return columns.map((col) => {
        if ('children' in col) {
            return {
                ...col,
                children: withTooltip(col.children as ColumnsType<T>),
            }
        }
        const originalRender = col.render
        return {
            ...col,
            ellipsis: { showTitle: false },
            render: (value: any, record: T, index: number) => {
                const content = originalRender
                    ? originalRender(value, record, index)
                    : (value ?? '-')
                const textContent = typeof content === 'string' || typeof content === 'number'
                    ? String(content)
                    : value ?? '-'
                return (
                    <Tooltip placement="topLeft" title={textContent}>
                        <span style={{ whiteSpace: 'nowrap' }}>
                            {content}
                        </span>
                    </Tooltip>
                )
            },
        }
    })
}

export interface ResizableTableProps<T> extends Omit<TableProps<T>, 'columns'> {
    columns: ColumnsType<T>
    /** 是否启用列宽调整 */
    resizable?: boolean
    /** 是否为列添加 Tooltip */
    withTooltips?: boolean
}

/** 可拖拽列宽的表格 */
export function ResizableTable<T extends Record<string, unknown>>({
    columns: initialColumns,
    resizable = true,
    withTooltips = true,
    ...tableProps
}: ResizableTableProps<T>) {
    // 处理列配置，添加 Tooltip
    const processedColumns = withTooltips ? withTooltip(initialColumns) : initialColumns

    // 维护列宽状态
    const [columns, setColumns] = useState<ColumnsType<T>>(processedColumns)

    // 处理列宽变化
    const handleResize = useCallback(
        (index: number) =>
            (_: React.SyntheticEvent, { size }: ResizeCallbackData) => {
                setColumns((prevColumns) => {
                    const nextColumns = [...prevColumns]
                    nextColumns[index] = {
                        ...nextColumns[index],
                        width: size.width,
                    }
                    return nextColumns
                })
            },
        []
    )

    // 更新列以包含 onHeaderCell
    const resizableColumns = columns.map((col, index) => ({
        ...col,
        onHeaderCell: (column: any) => ({
            width: column.width,
            onResize: handleResize(index),
        }),
    }))

    // 表格组件配置
    const components = resizable
        ? {
            header: {
                cell: ResizableTitle,
            },
        }
        : undefined

    return (
        <Table<T>
            {...tableProps}
            columns={resizableColumns as ColumnsType<T>}
            components={components}
        />
    )
}

export default ResizableTable
