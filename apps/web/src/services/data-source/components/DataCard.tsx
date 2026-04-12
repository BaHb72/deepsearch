/**
 * DataCard - 通用数据卡片组件
 * 包含标题、数据源标签、刷新按钮和数据表格
 */
import React, { useCallback } from 'react'
import { Card, Button, Space, Tag, Tooltip } from 'antd'
import { ReloadOutlined, DatabaseOutlined } from '@ant-design/icons'
import { DataTable, type DataTableProps } from './DataTable'
import type { DataSourceType } from '../types'
import { useDataSource } from '../hooks/useDataSource'

export interface DataCardProps extends Omit<DataTableProps, 'autoFetch'> {
    /** 卡片标题 */
    title: React.ReactNode
    /** 卡片图标 */
    icon?: React.ReactNode
    /** 卡片类型 */
    type?: 'default' | 'inner'
    /** 额外操作按钮 */
    extra?: React.ReactNode
    /** 是否显示数据源标签 */
    showSourceTag?: boolean
}

/** 数据源显示名称映射 */
const sourceNames: Record<DataSourceType, string> = {
    amazingdata: '银河数据',
    miniqmt: 'MiniQMT',
    akshare: 'AkShare',
    tushare: 'TuShare',
    eastmoney: '东方财富',
}

/** 数据源颜色映射 */
const sourceColors: Record<DataSourceType, string> = {
    amazingdata: 'blue',
    miniqmt: 'green',
    akshare: 'orange',
    tushare: 'purple',
    eastmoney: 'red',
}

export const DataCard: React.FC<DataCardProps> = ({
    title,
    icon,
    type = 'default',
    extra,
    showSourceTag = true,
    capability,
    params = {},
    preferredSource,
    ...tableProps
}) => {
    const { loading, source, refresh } = useDataSource({
        capability,
        params,
        preferredSource,
        autoFetch: false,
    })

    const handleRefresh = useCallback(() => {
        refresh()
    }, [refresh])

    return (
        <Card
            type={type === 'inner' ? 'inner' : undefined}
            size="small"
            title={
                <Space>
                    {icon}
                    <span>{title}</span>
                    {showSourceTag && source && (
                        <Tooltip title={`数据来源: ${sourceNames[source]}`}>
                            <Tag color={sourceColors[source]} style={{ marginLeft: 8 }}>
                                <DatabaseOutlined /> {sourceNames[source]}
                            </Tag>
                        </Tooltip>
                    )}
                </Space>
            }
            extra={
                <Space>
                    {extra}
                    <Button
                        icon={<ReloadOutlined />}
                        size="small"
                        onClick={handleRefresh}
                        loading={loading}
                    >
                        刷新
                    </Button>
                </Space>
            }
        >
            <DataTable
                capability={capability}
                params={params}
                preferredSource={preferredSource}
                {...tableProps}
            />
        </Card>
    )
}

export default DataCard
