import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { PageContainer } from '@ant-design/pro-components'


import type { ColumnsType } from 'antd/es/table'
import {
    Alert,
    Button,
    Card,
    Col,
    Divider,
    Empty,
    List,
    Progress,
    Row,
    Segmented,
    Space,
    Spin,
    Statistic,
    Table,
    Tag,
    Typography,
} from 'antd'
import {
    AlertOutlined,
    AreaChartOutlined,
    CheckCircleOutlined,
    ClockCircleOutlined,
    CloudServerOutlined,
    DashboardOutlined,
    FundOutlined,
    ReloadOutlined,
    ThunderboltOutlined,
    WarningOutlined,
} from '@ant-design/icons'
import { Line } from '@ant-design/charts'
import dayjs from 'dayjs'

import {
    monitorAPI,
    type MonitorDashboardResponse,
    type MonitorEventsSummary,
    type MonitorHealthResponse,
    type MonitorHistoricalResponse,
    type MonitorRealtimeMetrics,
    type MonitorSlowEvent,
    type MonitorSlowEventsResponse,
} from '@/api/monitor'

const { Text } = Typography

const percentColor = (value?: number) => {
    if (typeof value !== 'number') return '#1890ff'
    if (value >= 90) return '#cf1322'
    if (value >= 75) return '#fa8c16'
    return '#52c41a'
}

const formatNumber = (value?: number, fractionDigits = 1) =>
    typeof value === 'number'
        ? value.toLocaleString('zh-CN', { maximumFractionDigits: fractionDigits })
        : '--'

const severityColorMap: Record<string, string> = {
    info: 'blue',
    warning: 'orange',
    warn: 'orange',
    error: 'red',
    critical: 'red',
    success: 'green',
}

const historyOptions = [
    { label: '6小时', value: 6 },
    { label: '12小时', value: 12 },
    { label: '24小时', value: 24 },
    { label: '3天', value: 72 },
]

const healthStatusIcon = (status: 'pass' | 'warn' | 'fail') => {
    if (status === 'pass') {
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />
    }
    if (status === 'warn') {
        return <WarningOutlined style={{ color: '#faad14' }} />
    }
    return <ThunderboltOutlined style={{ color: '#cf1322' }} />
}

const PerformanceAnalytics: React.FC = () => {
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const [dashboardData, setDashboardData] = useState<MonitorDashboardResponse | null>(null)
    const [realtimeMetrics, setRealtimeMetrics] = useState<MonitorRealtimeMetrics | null>(null)
    const [healthStatus, setHealthStatus] = useState<MonitorHealthResponse | null>(null)
    const [slowEventsData, setSlowEventsData] = useState<MonitorSlowEventsResponse | null>(null)
    const [historyData, setHistoryData] = useState<MonitorHistoricalResponse | null>(null)
    const [eventsSummary, setEventsSummary] = useState<MonitorEventsSummary | null>(null)
    const [historyRange, setHistoryRange] = useState<number>(24)

    const fetchRealtime = useCallback(async () => {
        try {
            const response = await monitorAPI.getRealtimeMetrics()
            setRealtimeMetrics(response.data)
        } catch (err) {
            console.error('获取实时性能指标失败:', err)
        }
    }, [])

    const fetchAll = useCallback(async (options?: { showLoading?: boolean }) => {
        const showLoading = options?.showLoading ?? true
        if (showLoading) {
            setLoading(true)
        } else {
            setRefreshing(true)
        }

        try {
            const [dashboard, health, slowEvents, history, summary] = await Promise.all([
                monitorAPI.getDashboard(),
                monitorAPI.getHealthStatus(),
                monitorAPI.getSlowEvents(30),
                monitorAPI.getHistoricalData(historyRange),
                monitorAPI.getEventsSummary(),
            ])

            setDashboardData(dashboard.data)
            setHealthStatus(health.data)
            setSlowEventsData(slowEvents.data)
            setHistoryData(history.data)
            setEventsSummary(summary.data)
            setError(null)

            await fetchRealtime()
        } catch (err) {
            console.error('加载性能监控数据失败:', err)
            setError(err instanceof Error ? err.message : '加载性能监控数据失败')
        } finally {
            if (showLoading) {
                setLoading(false)
            } else {
                setRefreshing(false)
            }
        }
    }, [fetchRealtime, historyRange])

    useEffect(() => {
        fetchAll({ showLoading: true })
    }, [fetchAll])

    useEffect(() => {
        const timer = window.setInterval(() => {
            fetchRealtime()
        }, 15000)

        return () => {
            window.clearInterval(timer)
        }
    }, [fetchRealtime])

    const usageSeries = useMemo(() => {
        if (!historyData?.data?.length) return []
        return historyData.data.flatMap((item) => {
            const series: { metric: string; value: number; time: string }[] = []
            if (typeof item.cpu_usage === 'number') {
                series.push({ metric: 'CPU 使用率', value: item.cpu_usage, time: item.timestamp })
            }
            if (typeof item.memory_usage === 'number') {
                series.push({ metric: '内存使用率', value: item.memory_usage, time: item.timestamp })
            }
            if (typeof item.disk_usage === 'number') {
                series.push({ metric: '磁盘使用率', value: item.disk_usage, time: item.timestamp })
            }
            return series
        })
    }, [historyData])

    const networkSeries = useMemo(() => {
        if (!historyData?.data?.length) return []
        return historyData.data.flatMap((item) => {
            const series: { metric: string; value: number; time: string }[] = []
            if (typeof item.network_in === 'number') {
                series.push({ metric: '入站流量', value: item.network_in, time: item.timestamp })
            }
            if (typeof item.network_out === 'number') {
                series.push({ metric: '出站流量', value: item.network_out, time: item.timestamp })
            }
            return series
        })
    }, [historyData])

    const slowEventColumns: ColumnsType<MonitorSlowEvent> = useMemo(() => ([
        {
            title: '事件类型',
            dataIndex: 'event_type',
            key: 'event_type',
            render: (value: string) => <Tag color="geekblue">{value}</Tag>,
        },
        {
            title: '耗时 (ms)',
            dataIndex: 'duration_ms',
            key: 'duration_ms',
            render: (value: number) => (
                <Text type={value > (slowEventsData?.threshold_ms ?? 1000) ? 'danger' : undefined}>
                    {value.toLocaleString('zh-CN')}
                </Text>
            ),
        },
        {
            title: '发生时间',
            dataIndex: 'timestamp',
            key: 'timestamp',
            render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm:ss'),
        },
        {
            title: '来源',
            dataIndex: 'source',
            key: 'source',
            render: (value: string) => <Tag color="purple">{value}</Tag>,
        },
        {
            title: '详情',
            dataIndex: 'details',
            key: 'details',
            ellipsis: true,
            render: (value?: string) => value || '-',
        },
    ]), [slowEventsData?.threshold_ms])

    return (
        <PageContainer header={{ title: '性能监控', ghost: true }}>
            <Spin spinning={loading} tip="正在加载性能数据...">
                <Space direction="vertical" size={24} style={{ width: '100%' }}>

                    {error && (
                        <Alert
                            type="error"
                            showIcon
                            message="性能数据加载异常"
                            description={error}
                        />
                    )}

                    <Card
                        title={
                            <Space>
                                <DashboardOutlined />
                                <span>系统性能总览</span>
                            </Space>
                        }
                        extra={
                            <Space size="middle">
                                <Segmented
                                    options={historyOptions}
                                    value={historyRange}
                                    onChange={(value) => setHistoryRange(Number(value))}
                                />
                                <Button
                                    type="primary"
                                    icon={<ReloadOutlined />}
                                    onClick={() => fetchAll({ showLoading: false })}
                                    loading={refreshing}
                                >
                                    刷新数据
                                </Button>
                            </Space>
                        }
                    >
                        <Row gutter={[16, 16]}>
                            <Col xs={24} md={6}>
                                <Card size="small" variant="borderless" style={{ background: '#f5fbff' }}>
                                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                                        <Space align="center">
                                            <AreaChartOutlined style={{ color: '#1890ff' }} />
                                            <Text>CPU 使用率</Text>
                                        </Space>
                                        <Statistic
                                            value={dashboardData?.performance?.cpu_usage ?? 0}
                                            precision={1}
                                            suffix="%"
                                            valueStyle={{ color: percentColor(dashboardData?.performance?.cpu_usage) }}
                                        />
                                        <Progress
                                            percent={dashboardData?.performance?.cpu_usage ?? 0}
                                            showInfo={false}
                                            strokeColor={percentColor(dashboardData?.performance?.cpu_usage)}
                                        />
                                    </Space>
                                </Card>
                            </Col>
                            <Col xs={24} md={6}>
                                <Card size="small" variant="borderless" style={{ background: '#f6ffed' }}>
                                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                                        <Space align="center">
                                            <CloudServerOutlined style={{ color: '#52c41a' }} />
                                            <Text>内存使用率</Text>
                                        </Space>
                                        <Statistic
                                            value={dashboardData?.performance?.memory_usage ?? 0}
                                            precision={1}
                                            suffix="%"
                                            valueStyle={{ color: percentColor(dashboardData?.performance?.memory_usage) }}
                                        />
                                        <Progress
                                            percent={dashboardData?.performance?.memory_usage ?? 0}
                                            showInfo={false}
                                            strokeColor={percentColor(dashboardData?.performance?.memory_usage)}
                                        />
                                    </Space>
                                </Card>
                            </Col>
                            <Col xs={24} md={6}>
                                <Card size="small" variant="borderless" style={{ background: '#fff7e6' }}>
                                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                                        <Space align="center">
                                            <FundOutlined style={{ color: '#fa8c16' }} />
                                            <Text>磁盘使用率</Text>
                                        </Space>
                                        <Statistic
                                            value={dashboardData?.performance?.disk_usage ?? 0}
                                            precision={1}
                                            suffix="%"
                                            valueStyle={{ color: percentColor(dashboardData?.performance?.disk_usage) }}
                                        />
                                        <Progress
                                            percent={dashboardData?.performance?.disk_usage ?? 0}
                                            showInfo={false}
                                            strokeColor={percentColor(dashboardData?.performance?.disk_usage)}
                                        />
                                    </Space>
                                </Card>
                            </Col>
                            <Col xs={24} md={6}>
                                <Card size="small" variant="borderless" style={{ background: '#fff0f6' }}>
                                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                                        <Space align="center">
                                            <ThunderboltOutlined style={{ color: '#eb2f96' }} />
                                            <Text>网络连接</Text>
                                        </Space>
                                        <Statistic
                                            value={dashboardData?.performance?.network_connections ?? 0}
                                            suffix="条"
                                        />
                                        <Text type="secondary">
                                            线程数：{dashboardData?.performance?.process?.threads ?? '--'} ｜ 打开文件：
                                            {dashboardData?.performance?.process?.open_files ?? '--'}
                                        </Text>
                                    </Space>
                                </Card>
                            </Col>
                        </Row>
                    </Card>

                    <Row gutter={[16, 16]}>
                        <Col xs={24} xl={14}>
                            <Card title="资源使用趋势" variant="borderless">
                                {usageSeries.length === 0 ? (
                                    <Empty description="暂无趋势数据" />
                                ) : (
                                    <Line
                                        data={usageSeries}
                                        xField="time"
                                        yField="value"
                                        seriesField="metric"
                                        smooth
                                        height={260}
                                        autoFit
                                        tooltip={{ shared: true }}
                                        xAxis={{ type: 'time' }}
                                        meta={{
                                            value: {
                                                formatter: (val: number) => `${val.toFixed(1)}%`,
                                            },
                                        }}
                                        color={['#1890ff', '#52c41a', '#722ed1']}
                                    />
                                )}
                            </Card>
                        </Col>
                        <Col xs={24} xl={10}>
                            <Card title="实时运行状态" variant="borderless">
                                <Row gutter={[16, 16]}>
                                    <Col span={12}>
                                        <Statistic
                                            title="CPU 使用率"
                                            value={realtimeMetrics?.cpu?.usage_percent ?? 0}
                                            precision={1}
                                            suffix="%"
                                            valueStyle={{ color: percentColor(realtimeMetrics?.cpu?.usage_percent) }}
                                        />
                                        <Text type="secondary">
                                            负载：{formatNumber(realtimeMetrics?.cpu?.load_average, 2)} ｜ 核心：
                                            {realtimeMetrics?.cpu?.cores ?? '--'}
                                        </Text>
                                    </Col>
                                    <Col span={12}>
                                        <Statistic
                                            title="内存占用"
                                            value={realtimeMetrics?.memory?.usage_percent ?? 0}
                                            precision={1}
                                            suffix="%"
                                            valueStyle={{ color: percentColor(realtimeMetrics?.memory?.usage_percent) }}
                                        />
                                        <Text type="secondary">
                                            已用 {formatNumber(realtimeMetrics?.memory?.used_gb, 2)} GB / 总计
                                            {formatNumber(realtimeMetrics?.memory?.total_gb, 2)} GB
                                        </Text>
                                    </Col>
                                    <Col span={12}>
                                        <Statistic
                                            title="磁盘使用"
                                            value={realtimeMetrics?.disk?.usage_percent ?? 0}
                                            precision={1}
                                            suffix="%"
                                            valueStyle={{ color: percentColor(realtimeMetrics?.disk?.usage_percent) }}
                                        />
                                        <Text type="secondary">
                                            读 {formatNumber(realtimeMetrics?.disk?.read_mb_s, 1)} MB/s ·
                                            写 {formatNumber(realtimeMetrics?.disk?.write_mb_s, 1)} MB/s
                                        </Text>
                                    </Col>
                                    <Col span={12}>
                                        <Statistic
                                            title="进程与线程"
                                            value={realtimeMetrics?.processes?.total ?? 0}
                                            suffix="个进程"
                                        />
                                        <Text type="secondary">
                                            运行中 {realtimeMetrics?.processes?.running ?? '--'} ·
                                            睡眠中 {realtimeMetrics?.processes?.sleeping ?? '--'} ·
                                            线程 {realtimeMetrics?.processes?.threads ?? '--'}
                                        </Text>
                                    </Col>
                                </Row>
                                <Divider style={{ margin: '16px 0' }} />
                                {networkSeries.length === 0 ? (
                                    <Empty description="暂无网络数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                                ) : (
                                    <Line
                                        data={networkSeries}
                                        xField="time"
                                        yField="value"
                                        seriesField="metric"
                                        smooth
                                        height={200}
                                        autoFit
                                        tooltip={{ shared: true }}
                                        xAxis={{ type: 'time' }}
                                        meta={{
                                            value: {
                                                formatter: (val: number) => `${val.toFixed(0)} KB/s`,
                                            },
                                        }}
                                        color={['#13c2c2', '#531dab']}
                                    />
                                )}
                            </Card>
                        </Col>
                    </Row>

                    <Row gutter={[16, 16]}>
                        <Col xs={24} lg={12}>
                            <Card
                                title={
                                    <Space>
                                        <CheckCircleOutlined />
                                        <span>健康巡检</span>
                                    </Space>
                                }
                                variant="borderless"
                            >
                                {healthStatus ? (
                                    <Space direction="vertical" size={16} style={{ width: '100%' }}>
                                        <Alert
                                            type={
                                                healthStatus.status === 'healthy'
                                                    ? 'success'
                                                    : healthStatus.status === 'degraded'
                                                        ? 'warning'
                                                        : 'error'
                                            }
                                            showIcon
                                            message={`总体状态：${healthStatus.status === 'healthy' ? '健康' : healthStatus.status === 'degraded' ? '注意' : '异常'}`}
                                            description={`最近检查时间：${dayjs(healthStatus.timestamp).format('YYYY-MM-DD HH:mm:ss')}`}
                                        />
                                        <List
                                            dataSource={healthStatus.checks}
                                            renderItem={(item) => (
                                                <List.Item>
                                                    <List.Item.Meta
                                                        avatar={healthStatusIcon(item.status)}
                                                        title={item.name}
                                                        description={`当前值：${item.value} · 阈值：${item.threshold}`}
                                                    />
                                                    <Tag
                                                        color={item.status === 'pass' ? 'green' : item.status === 'warn' ? 'orange' : 'red'}>
                                                        {item.status === 'pass' ? '正常' : item.status === 'warn' ? '预警' : '超标'}
                                                    </Tag>
                                                </List.Item>
                                            )}
                                        />
                                    </Space>
                                ) : (
                                    <Empty description="暂无健康检查数据" />
                                )}
                            </Card>
                        </Col>
                        <Col xs={24} lg={12}>
                            <Card
                                title={
                                    <Space>
                                        <CloudServerOutlined />
                                        <span>关键服务状态</span>
                                    </Space>
                                }
                                variant="borderless"
                            >
                                {dashboardData?.services?.length ? (
                                    <List
                                        itemLayout="horizontal"
                                        dataSource={dashboardData.services}
                                        renderItem={(service) => (
                                            <List.Item
                                                actions={[
                                                    <Tag key="status"
                                                        color={service.status === 'running' ? 'green' : 'red'}>
                                                        {service.status === 'running' ? '运行中' : '异常'}
                                                    </Tag>,
                                                ]}
                                            >
                                                <List.Item.Meta
                                                    title={service.name}
                                                    description={
                                                        <Space size={12} wrap>
                                                            {Object.entries(service.metrics || {}).map(([key, value]) => (
                                                                <span key={key}>{key}：{value}</span>
                                                            ))}
                                                        </Space>
                                                    }
                                                />
                                            </List.Item>
                                        )}
                                    />
                                ) : (
                                    <Empty description="暂无服务数据" />
                                )}
                            </Card>
                        </Col>
                    </Row>

                    <Row gutter={[16, 16]}>
                        <Col xs={24} lg={12}>
                            <Card
                                title={
                                    <Space>
                                        <AlertOutlined />
                                        <span>活跃告警</span>
                                    </Space>
                                }
                                variant="borderless"
                            >
                                {dashboardData?.alerts?.length ? (
                                    <List
                                        dataSource={dashboardData.alerts}
                                        renderItem={(alertItem, index) => (
                                            <List.Item key={index}>
                                                <List.Item.Meta
                                                    avatar={<WarningOutlined
                                                        style={{ color: severityColorMap[alertItem.level ?? 'warning'] || '#faad14' }} />}
                                                    title={alertItem.message || '未命名告警'}
                                                    description={dayjs(alertItem.timestamp).format('YYYY-MM-DD HH:mm:ss')}
                                                />
                                                <Tag color={severityColorMap[alertItem.level ?? 'warning'] || 'orange'}>
                                                    {alertItem.level ?? 'warning'}
                                                </Tag>
                                            </List.Item>
                                        )}
                                    />
                                ) : (
                                    <Empty description="当前暂无告警" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                                )}
                            </Card>
                        </Col>
                        <Col xs={24} lg={12}>
                            <Card
                                title={
                                    <Space>
                                        <ClockCircleOutlined />
                                        <span>事件概况</span>
                                    </Space>
                                }
                                variant="borderless"
                            >
                                {eventsSummary ? (
                                    <Space direction="vertical" size={16} style={{ width: '100%' }}>
                                        <Row gutter={[16, 16]}>
                                            <Col span={8}>
                                                <Statistic title="事件总数" value={eventsSummary.total_events} />
                                            </Col>
                                            <Col span={8}>
                                                <Statistic
                                                    title="告警数量"
                                                    value={eventsSummary.warning_count}
                                                    valueStyle={{ color: '#fa8c16' }}
                                                />
                                            </Col>
                                            <Col span={8}>
                                                <Statistic
                                                    title="异常数量"
                                                    value={eventsSummary.error_count}
                                                    valueStyle={{ color: '#cf1322' }}
                                                />
                                            </Col>
                                        </Row>
                                        <Divider style={{ margin: 0 }} />
                                        <Space size={[8, 8]} wrap>
                                            {Object.entries(eventsSummary.events_by_type || {}).map(([type, count]) => (
                                                <Tag key={type} color="blue">
                                                    {type}：{count}
                                                </Tag>
                                            ))}
                                        </Space>
                                        <List
                                            header={<Text type="secondary">最近事件</Text>}
                                            dataSource={eventsSummary.recent_events.slice(0, 5)}
                                            renderItem={(item) => (
                                                <List.Item>
                                                    <List.Item.Meta
                                                        title={item.message}
                                                        description={`${dayjs(item.timestamp).format('MM-DD HH:mm:ss')} · ${item.source}`}
                                                    />
                                                    <Tag
                                                        color={severityColorMap[item.severity] || 'blue'}>{item.type}</Tag>
                                                </List.Item>
                                            )}
                                        />
                                    </Space>
                                ) : (
                                    <Empty description="暂无事件数据" />
                                )}
                            </Card>
                        </Col>
                    </Row>

                    <Card
                        title={
                            <Space>
                                <WarningOutlined />
                                <span>慢事件追踪</span>
                            </Space>
                        }
                        variant="borderless"
                    >
                        <Table
                            dataSource={slowEventsData?.events || []}
                            columns={slowEventColumns}
                            pagination={false}
                            rowKey={(record) => `${record.event_type}-${record.timestamp}-${record.duration_ms}`}
                            locale={{ emptyText: '当前时间段暂无慢事件' }}
                        />
                    </Card>
                </Space>
            </Spin>
        </PageContainer>
    )
}

export default PerformanceAnalytics

