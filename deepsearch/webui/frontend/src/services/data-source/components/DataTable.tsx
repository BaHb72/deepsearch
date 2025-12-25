/**
 * DataTable - 通用数据表格组件
 * 基于数据源插槽架构，自动选择数据源获取数据
 */
import React from 'react'
import { Table, Empty, Alert } from 'antd'
import type { TableProps } from 'antd'
import { useDataSource } from '../hooks/useDataSource'
import type { DataCapability, DataSourceType, DataSourceParams, ColumnDef } from '../types'

export interface DataTableProps {
    /** 数据能力类型 */
    capability: DataCapability
    /** 请求参数 */
    params?: DataSourceParams
    /** 优先使用的数据源 */
    preferredSource?: DataSourceType
    /** 表格高度 */
    height?: number
    /** 是否自动获取数据 */
    autoFetch?: boolean
    /** 表格大小 */
    size?: 'small' | 'middle' | 'large'
    /** 是否显示分页 */
    pagination?: false | TableProps<unknown>['pagination']
    /** 自定义列配置 */
    customColumns?: ColumnDef[]
    /** 数据变化回调 */
    onDataChange?: (data: unknown[]) => void
}

/**
 * 将 ColumnDef 转换为 antd Table columns
 */
function toAntdColumns(columns: ColumnDef[]): TableProps<unknown>['columns'] {
    return columns.map((col) => ({
        key: col.key,
        title: col.title,
        dataIndex: col.dataIndex,
        width: col.width,
        align: col.align,
        ellipsis: true,
    }))
}

export const DataTable: React.FC<DataTableProps> = ({
    capability,
    params = {},
    preferredSource,
    height = 300,
    autoFetch = false,
    size = 'small',
    pagination = { pageSize: 10 },
    customColumns,
    onDataChange,
}) => {
    const { data, columns, loading, error, source, refresh } = useDataSource({
        capability,
        params,
        preferredSource,
        autoFetch,
    })

    // 数据变化回调
    React.useEffect(() => {
        if (onDataChange && data.length > 0) {
            onDataChange(data)
        }
    }, [data, onDataChange])

    if (error) {
        return (
            <Alert
                message="数据获取失败"
                description={error}
                type="error"
                showIcon
                action={
                    <a onClick={refresh}>重试</a>
                }
            />
        )
    }

    const tableColumns = customColumns
        ? toAntdColumns(customColumns)
        : toAntdColumns(columns)

    return (
        <Table
            dataSource={data}
            columns={tableColumns}
            loading={loading}
            rowKey="_key"
            size={size}
            scroll={{ x: 'max-content', y: height }}
            pagination={pagination}
            locale={{
                emptyText: (
                    <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description={
                            <span>
                                暂无数据
                                {source && <span style={{ color: '#999' }}> (来源: {source})</span>}
                            </span>
                        }
                    />
                ),
            }}
        />
    )
}

export default DataTable
