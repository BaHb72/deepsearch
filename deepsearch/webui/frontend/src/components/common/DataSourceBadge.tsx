/**
 * DataSourceBadge - 数据来源标识
 * 显示当前数据来自哪个数据源
 */
import React from 'react'
import { Tag, Tooltip, Space } from 'antd'
import { DatabaseOutlined, ClockCircleOutlined } from '@ant-design/icons'
import type { DataSourceType } from '@/services/data-source'
import { SOURCE_COLORS } from './DataSourceSelect'

export interface DataSourceBadgeProps {
    /** 数据源类型 */
    source?: DataSourceType
    /** 响应延迟 (ms) */
    latency?: number
    /** 是否缓存数据 */
    cached?: boolean
    /** 大小 */
    size?: 'small' | 'default'
    /** 是否显示延迟 */
    showLatency?: boolean
}

/** 数据源显示名称映射 */
const SOURCE_LABELS: Record<DataSourceType, string> = {
    miniqmt: 'MiniQMT',
    amazingdata: 'AmazingData',
    akshare: 'AkShare',
    tushare: 'TuShare',
    eastmoney: '东方财富',
}

export const DataSourceBadge: React.FC<DataSourceBadgeProps> = ({
    source,
    latency,
    cached,
    size = 'default',
    showLatency = false,
}) => {
    if (!source) {
        return null
    }

    const label = SOURCE_LABELS[source] || source
    const color = SOURCE_COLORS[source] || 'default'

    const tooltipContent = (
        <Space direction="vertical" size={2}>
            <span>数据来源: {label}</span>
            {latency !== undefined && <span>响应时间: {latency}ms</span>}
            {cached && <span>来自缓存</span>}
        </Space>
    )

    return (
        <Tooltip title={tooltipContent}>
            <Space size={4}>
                <Tag
                    color={color}
                    icon={<DatabaseOutlined />}
                    style={{
                        margin: 0,
                        fontSize: size === 'small' ? 11 : 12,
                    }}
                >
                    {label}
                </Tag>
                {showLatency && latency !== undefined && (
                    <Tag
                        icon={<ClockCircleOutlined />}
                        style={{
                            margin: 0,
                            fontSize: size === 'small' ? 11 : 12,
                        }}
                    >
                        {latency}ms
                    </Tag>
                )}
                {cached && (
                    <Tag color="cyan" style={{ margin: 0, fontSize: size === 'small' ? 11 : 12 }}>
                        缓存
                    </Tag>
                )}
            </Space>
        </Tooltip>
    )
}

export default DataSourceBadge
