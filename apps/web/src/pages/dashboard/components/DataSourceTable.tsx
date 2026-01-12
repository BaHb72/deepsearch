import React from 'react'
import { Badge, Space, Table, Tag, Tooltip } from 'antd'
import { getDataSourceStatusMeta } from '@/utils/dataSourceStatus'
import { formatDateTime, formatSuccessRate } from '../utils'

interface DataSourceTableProps {
    dataSourceStatus: any[]
    loading: boolean
}

const DataSourceTable: React.FC<DataSourceTableProps> = ({ dataSourceStatus, loading }) => {
    const getNormalizedSuccessRate = (record: Record<string, any>) => {
        const raw =
            typeof record.successRate === 'number'
                ? record.successRate
                : typeof record.metrics?.successRate === 'number'
                    ? record.metrics.successRate
                    : null

        if (typeof raw !== 'number' || Number.isNaN(raw)) {
            return null
        }

        return raw > 1 ? raw / 100 : raw
    }

    const columns = [
        {
            title: '数据源',
            dataIndex: 'name',
            key: 'name',
            render: (_: unknown, record: any) => (
                <div>
                    <strong>{record.name}</strong>
                    {Array.isArray(record.proxies) && record.proxies.length > 0 && (
                        <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                            {record.proxies.map((proxy: any) => {
                                const meta = getDataSourceStatusMeta(proxy.status)
                                const metrics = proxy.metrics ?? {}
                                const successLabel = formatSuccessRate(metrics?.successRate)
                                const tooltipLines = [
                                    '节点状态: ' + meta.text,
                                    typeof metrics?.avgLatency === 'number' && metrics.avgLatency >= 0
                                        ? '平均延迟: ' + metrics.avgLatency.toFixed(1) + ' ms'
                                        : null,
                                    typeof metrics?.totalRequests === 'number' && metrics.totalRequests > 0
                                        ? '请求数: ' + metrics.totalRequests
                                        : null,
                                    successLabel ? '成功率: ' + successLabel : null,
                                    proxy.reason ? '原因: ' + proxy.reason : null,
                                    proxy.lastTestTime ? '最近检测: ' + formatDateTime(proxy.lastTestTime) : null,
                                    !proxy.lastTestTime && proxy.lastTransition
                                        ? '最近变更: ' + formatDateTime(proxy.lastTransition)
                                        : null,
                                ].filter(Boolean)

                                const tooltipContent = (
                                    <div>
                                        {tooltipLines.map((line: string | null, index: number) => (
                                            <div
                                                key={index}
                                                style={{
                                                    marginTop: index === 0 ? 0 : 4,
                                                    fontSize: 12,
                                                    color: '#8c8c8c',
                                                }}
                                            >
                                                {line}
                                            </div>
                                        ))}
                                    </div>
                                )

                                return (
                                    <Tooltip key={proxy.id ?? proxy.name} title={tooltipContent}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                            <Tag color={meta.tagColor} style={{ margin: 0 }}>
                                                代理 {proxy.name}
                                            </Tag>
                                            {typeof proxy.available === 'boolean' && (
                                                <Badge status={proxy.available ? 'success' : 'error'} />
                                            )}
                                        </div>
                                    </Tooltip>
                                )
                            })}
                        </div>
                    )}
                </div>
            ),
        },
        {
            title: '状态',
            dataIndex: 'status',
            key: 'status',
            render: (_: unknown, record: any) => {
                const meta = getDataSourceStatusMeta(record.status)
                const tooltipLines = [meta.description]

                if (record.reason) {
                    tooltipLines.push('原因: ' + record.reason)
                }

                if (record.testSummary) {
                    tooltipLines.push('检测摘要: ' + record.testSummary)
                }

                if (record.lastTestTime) {
                    tooltipLines.push('最近检测: ' + formatDateTime(record.lastTestTime))
                } else if (record.lastTransition) {
                    tooltipLines.push('最近变更: ' + formatDateTime(record.lastTransition))
                }

                if (record.metrics?.totalRequests) {
                    tooltipLines.push('请求数: ' + record.metrics.totalRequests)
                }

                const successLabel = formatSuccessRate(record.metrics?.successRate ?? record.successRate)
                if (successLabel) {
                    tooltipLines.push('成功率: ' + successLabel)
                }

                if (record.hasSavedCredential) {
                    tooltipLines.push('凭据: 已保存')
                }

                const tooltipContent = (
                    <div>
                        {tooltipLines.map((line: string | null, index: number) => (
                            <div key={index} style={{ marginTop: index === 0 ? 0 : 4, fontSize: 12, color: '#8c8c8c' }}>
                                {line}
                            </div>
                        ))}
                    </div>
                )

                return (
                    <Space size={6}>
                        <Tooltip title={tooltipContent}>
                            <Tag color={meta.tagColor} style={{ margin: 0 }}>
                                {meta.text}
                            </Tag>
                        </Tooltip>
                        {typeof record.available === 'boolean' && (
                            <Badge status={record.available ? 'success' : 'error'} />
                        )}
                    </Space>
                )
            },
        },
        {
            title: '延迟',
            dataIndex: 'latency',
            key: 'latency',
            render: (latency: number | null) =>
                typeof latency === 'number' && latency >= 0 ? latency.toFixed(1) + ' ms' : '--',
        },
        {
            title: '成功率',
            dataIndex: 'successRate',
            key: 'successRate',
            render: (_: unknown, record: any) => {
                const rate = getNormalizedSuccessRate(record)
                const label = formatSuccessRate(rate)
                return label ?? '--'
            },
        },
        {
            title: '最近检测',
            dataIndex: 'lastTestTime',
            key: 'lastTestTime',
            render: (_: unknown, record: any) =>
                formatDateTime(record.lastTestTime ?? record.lastTransition ?? null),
        },
    ]

    return (
        <Table
            columns={columns}
            dataSource={dataSourceStatus}
            loading={loading}
            pagination={false}
            rowKey="key"
        />
    )
}

export default DataSourceTable
