import React, { useMemo } from 'react'
import { Button, Empty, Space, Tag, Typography } from 'antd'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'

import type {
    ConceptPulseIndexPoint,
    IndexConceptPulseEvent,
} from '@/api/marketDataLive'

const { Text } = Typography

interface IndexConceptPulseChartProps {
    indexPoints: ConceptPulseIndexPoint[]
    events: IndexConceptPulseEvent[]
    selectedEventAt?: string | null
    loading?: boolean
    onSelectEvent?: (capturedAt: string) => void
}

const formatIndexChange = (value?: number | null) => {
    if (value == null) return '--'
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

const IndexConceptPulseChart: React.FC<IndexConceptPulseChartProps> = ({
    indexPoints,
    events,
    selectedEventAt,
    loading = false,
    onSelectEvent,
}) => {
    const chartData = useMemo(() => {
        const orderedPoints = [...indexPoints].sort((a, b) => a.ts.localeCompare(b.ts))
        const pointMap = new Map<string, ConceptPulseIndexPoint>()
        orderedPoints.forEach((point) => {
            pointMap.set(point.time, point)
        })

        const markerData = events
            .map((event) => {
                const point = pointMap.get(event.time)
                if (!point) return null
                const active = selectedEventAt === event.captured_at
                return {
                    name: event.label,
                    value: event.label,
                    coord: [point.time, point.value],
                    eventKey: event.captured_at,
                    symbolSize: active ? 20 : 16,
                    itemStyle: {
                        color: active ? '#1677ff' : '#f59e0b',
                        borderColor: '#fff',
                        borderWidth: 2,
                    },
                    label: {
                        show: true,
                        position: 'top',
                        formatter: event.label,
                        color: active ? '#0f172a' : '#92400e',
                        fontWeight: 600,
                        fontSize: 11,
                        backgroundColor: active ? 'rgba(219,234,254,0.95)' : 'rgba(254,243,199,0.95)',
                        borderRadius: 8,
                        padding: [4, 8],
                    },
                }
            })
            .filter(Boolean)

        return { orderedPoints, markerData }
    }, [events, indexPoints, selectedEventAt])

    const latestPoint = chartData.orderedPoints[chartData.orderedPoints.length - 1]
    const option = useMemo<EChartsOption>(() => ({
        animation: false,
        grid: {
            left: 36,
            right: 24,
            top: 52,
            bottom: 48,
        },
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(15,23,42,0.92)',
            borderWidth: 0,
            textStyle: {
                color: '#f8fafc',
            },
            formatter: (params: unknown) => {
                const axisPoints = Array.isArray(params) ? params : []
                const point = axisPoints[0] as { axisValue?: string; data?: number } | undefined
                const time = point?.axisValue ?? '--'
                const value = point?.data ?? '--'
                const matchedEvents = events.filter((item) => item.time === time)
                const eventText = matchedEvents.length
                    ? `<br/>启动概念：${matchedEvents.map((item) => item.label).join(' / ')}`
                    : ''
                return `时间：${time}<br/>上证指数：${value}${eventText}`
            },
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: chartData.orderedPoints.map((point) => point.time),
            axisLine: {
                lineStyle: {
                    color: '#cbd5e1',
                },
            },
            axisLabel: {
                color: '#64748b',
                interval: (index: number) => index % 30 === 0,
            },
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: {
                lineStyle: {
                    color: '#e2e8f0',
                    type: 'dashed',
                },
            },
            axisLabel: {
                color: '#64748b',
            },
        },
        series: [
            {
                name: '上证指数',
                type: 'line',
                smooth: true,
                symbol: 'none',
                data: chartData.orderedPoints.map((point) => point.value),
                lineStyle: {
                    width: 2.5,
                    color: '#0f766e',
                },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(15,118,110,0.20)' },
                            { offset: 1, color: 'rgba(15,118,110,0.02)' },
                        ],
                    },
                },
                markPoint: {
                    symbolKeepAspect: true,
                    data: chartData.markerData as never[],
                },
            },
        ],
    }), [chartData.markerData, chartData.orderedPoints, events])

    if (!chartData.orderedPoints.length) {
        return <Empty description="暂无上证指数分时数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
    }

    return (
        <div>
            <Space
                align="center"
                style={{
                    width: '100%',
                    justifyContent: 'space-between',
                    marginBottom: 12,
                    flexWrap: 'wrap',
                }}
            >
                <Space size={8} wrap>
                    <Tag color="processing">上证指数</Tag>
                    <Text type="secondary">最新时间 {latestPoint?.time ?? '--'}</Text>
                    <Text strong style={{ color: '#0f766e' }}>
                        {latestPoint?.value?.toFixed(2) ?? '--'}
                    </Text>
                    <Text strong style={{ color: (latestPoint?.change_pct ?? 0) >= 0 ? '#dc2626' : '#2563eb' }}>
                        {formatIndexChange(latestPoint?.change_pct)}
                    </Text>
                </Space>
                <Text type="secondary">已标注 {events.length} 个概念启动时点</Text>
            </Space>

            <ReactECharts
                option={option}
                style={{ height: 360, width: '100%' }}
                showLoading={loading}
                opts={{ renderer: 'svg' }}
                onEvents={{
                    click: (params: { data?: { eventKey?: string } }) => {
                        const eventKey = params?.data?.eventKey
                        if (eventKey && onSelectEvent) {
                            onSelectEvent(eventKey)
                        }
                    },
                }}
            />

            <Space wrap size={[8, 8]} style={{ marginTop: 12 }}>
                {events.length ? events.map((event) => (
                    <Button
                        key={event.captured_at}
                        size="small"
                        type={selectedEventAt === event.captured_at ? 'primary' : 'default'}
                        onClick={() => onSelectEvent?.(event.captured_at)}
                    >
                        {event.time} {event.label}
                    </Button>
                )) : (
                    <Text type="secondary">当前运行期内尚未识别到新的阈值启动事件。</Text>
                )}
            </Space>
        </div>
    )
}

export default IndexConceptPulseChart
