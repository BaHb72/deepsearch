/**
 * KlineSection - K线数据组件
 * 使用 useRichDataSource 获取数据，支持展示扩展字段
 */
import React, { useState } from 'react'
import { Button, Space, Select, Alert } from 'antd'
import { ReloadOutlined, LineChartOutlined, TableOutlined } from '@ant-design/icons'
import { ProCard } from '@ant-design/pro-components'
import ReactECharts from 'echarts-for-react'
import type { DataSourceType, CoreKlineData } from '@/services/data-source'
import { useRichDataSource, DataTable } from '@/services/data-source'
import { DataSourceBadge } from '@/components/common/DataSourceBadge'
import { ExtendedFieldsPanel } from '@/components/common/ExtendedFieldsPanel'

export interface KlineSectionProps {
    stockCode: string
    preferredSource?: DataSourceType
    onSuggestSourceSwitch?: (source: DataSourceType) => void
    defaultPeriod?: string
    /** 是否显示扩展字段面板 */
    showExtended?: boolean
}

const PERIOD_OPTIONS = [
    { value: '1m', label: '1分钟' },
    { value: '5m', label: '5分钟' },
    { value: '15m', label: '15分钟' },
    { value: '30m', label: '30分钟' },
    { value: '60m', label: '60分钟' },
    { value: '1d', label: '日线' },
]

export const KlineSection: React.FC<KlineSectionProps> = ({
    stockCode,
    preferredSource,
    onSuggestSourceSwitch,
    defaultPeriod = '1d',
    showExtended = true,
}) => {
    const [period, setPeriod] = useState(defaultPeriod)
    const [viewMode, setViewMode] = useState<'chart' | 'table'>('chart')

    const { data, extended, meta, loading, error, refresh } = useRichDataSource<CoreKlineData>({
        capability: 'stock_kline',
        params: { code: stockCode, period, count: 100 },
        preferredSource,
        autoFetch: true,
        deps: [stockCode, period],
        monitor: {
            pageKey: 'dev/playground',
            pageName: '数据源沙盒',
            moduleKey: 'quote',
            moduleName: '行情数据',
            onSwitchSource: onSuggestSourceSwitch,
        },
    })

    // 合并所有扩展字段（K线数据有多条）
    const allExtendedKeys = new Set<string>()
    extended.forEach(ext => {
        if (ext) Object.keys(ext).forEach(k => allExtendedKeys.add(k))
    })
    const hasExtended = allExtendedKeys.size > 0

    // 生成 K 线图配置
    const getChartOption = () => {
        if (!data || data.length === 0) return {}

        const klineData = data.map((item) => [
            item.open,
            item.close,
            item.low,
            item.high,
        ])
        const dates = data.map((item) => {
            const time = item.time
            if (typeof time === 'number') {
                return new Date(time).toLocaleDateString()
            }
            return String(time)
        })
        const volumes = data.map((item) => item.volume || 0)

        return {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
            },
            grid: [
                { left: '10%', right: '10%', top: '10%', height: '50%' },
                { left: '10%', right: '10%', top: '68%', height: '20%' },
            ],
            xAxis: [
                { type: 'category', data: dates, gridIndex: 0, axisLabel: { show: false } },
                { type: 'category', data: dates, gridIndex: 1 },
            ],
            yAxis: [
                { type: 'value', scale: true, gridIndex: 0 },
                { type: 'value', scale: true, gridIndex: 1 },
            ],
            series: [
                {
                    name: 'K线',
                    type: 'candlestick',
                    data: klineData,
                    itemStyle: {
                        color: '#f5222d',
                        color0: '#52c41a',
                        borderColor: '#f5222d',
                        borderColor0: '#52c41a',
                    },
                },
                {
                    name: '成交量',
                    type: 'bar',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: volumes,
                    itemStyle: {
                        color: (params: { dataIndex: number }) => {
                            const item = data[params.dataIndex]
                            return item.close >= item.open ? '#f5222d' : '#52c41a'
                        },
                    },
                },
            ],
        }
    }

    return (
        <ProCard
            title={
                <Space>
                    <span>K线数据</span>
                    <DataSourceBadge
                        source={meta?.source}
                        latency={meta?.latency}
                        size="small"
                    />
                </Space>
            }
            extra={
                <Space>
                    <Select
                        value={period}
                        onChange={setPeriod}
                        options={PERIOD_OPTIONS}
                        style={{ width: 90 }}
                        size="small"
                    />
                    <Button
                        type={viewMode === 'chart' ? 'primary' : 'default'}
                        icon={<LineChartOutlined />}
                        size="small"
                        onClick={() => setViewMode('chart')}
                    />
                    <Button
                        type={viewMode === 'table' ? 'primary' : 'default'}
                        icon={<TableOutlined />}
                        size="small"
                        onClick={() => setViewMode('table')}
                    />
                    <Button
                        icon={<ReloadOutlined />}
                        onClick={refresh}
                        loading={loading}
                        size="small"
                    >
                        刷新
                    </Button>
                </Space>
            }
            bordered
            headerBordered
        >
            {error && (
                <Alert
                    message="获取K线数据失败"
                    description={error}
                    type="warning"
                    showIcon
                    style={{ marginBottom: 16 }}
                />
            )}
            {viewMode === 'chart' ? (
                <ReactECharts
                    option={getChartOption()}
                    style={{ height: 400 }}
                    showLoading={loading}
                />
            ) : (
                <DataTable
                    capability="stock_kline"
                    params={{ code: stockCode, period }}
                    preferredSource={preferredSource}
                    autoFetch={false}
                    height={350}
                />
            )}

            {/* 扩展字段面板 - 显示第一条数据的扩展字段 */}
            {showExtended && hasExtended && extended[0] && (
                <ExtendedFieldsPanel
                    extended={extended[0]}
                    source={meta?.source}
                    title="K线扩展数据"
                />
            )}
        </ProCard>
    )
}

export default KlineSection
