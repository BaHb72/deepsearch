import React, {useEffect, useState} from 'react'
import {
    Badge,
    Button,
    Card,
    Col,
    message,
    Progress,
    Row,
    Select,
    Space,
    Switch,
    Table,
    Tag,
    Timeline,
    Tooltip,
    Typography,
} from 'antd'
import {ProCard, StatisticCard} from '@ant-design/pro-components'
import {Area, Column, Gauge, Line, Pie} from '@ant-design/charts'
import {
    ApiOutlined,
    CheckCircleOutlined,
    ClockCircleOutlined,
    CloseCircleOutlined,
    DatabaseOutlined,
    FallOutlined,
    InfoCircleOutlined,
    LineChartOutlined,
    MonitorOutlined,
    ReloadOutlined,
    RiseOutlined,
    ThunderboltOutlined,
    WarningOutlined,
} from '@ant-design/icons'
import {dataSourceAPI} from '../api/dataSource'
import {DATA_SOURCE_STATUS_ORDER, getDataSourceStatusMeta, normalizeTestSummary} from '@/utils/dataSourceStatus'

const { Title } = Typography
const formatDateTime = (value?: string | number | Date | null) => {
  if (!value) {
    return '--'
  }

  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '--'
  }

  const pad = (num: number) => num.toString().padStart(2, '0')

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

const DataSourceMonitor = () => {
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshInterval] = useState(5000)
  const [selectedSource, setSelectedSource] = useState('all')
  const [timeRange, setTimeRange] = useState('1h')

    // 妯℃嫙瀹炴椂鏁版嵁
  const [monitorData, setMonitorData] = useState({
    statusSummary: {},
    overview: {
      total: 6,
      active: 3,
      ready: 1,
      degraded: 1,
      error: 1,
      offline: 0,
      totalRequests: 125432,
      avgLatency: 85,
      successRate: 98.5,
    },
    sources: [
      {
        id: 1,
        name: 'AmazingData',
        type: 'amazingdata',
        status: 'active',
        health: 'healthy',
        latency: 45,
        requests: 45678,
        errors: 23,
        successRate: 99.8,
        lastCheck: '10秒前',
        trend: 'up',
        available: true,
      },
      {
        id: 2,
        name: 'CloudFlare Workers',
        type: 'cloudflare',
        status: 'degraded',
        health: 'healthy',
        latency: 120,
        requests: 23456,
        errors: 156,
        successRate: 98.5,
        lastCheck: '15秒前',
        trend: 'stable',
        available: true,
      },
      {
        id: 3,
        name: 'QMT Gateway',
        type: 'qmt',
        status: 'offline',
        health: 'error',
        latency: 0,
        requests: 0,
        errors: 0,
        successRate: 0,
        lastCheck: '5分钟前',
        trend: 'down',
        available: false,
      },
      {
        id: 4,
        name: 'AKShare',
        type: 'akshare',
        status: 'ready',
        health: 'warning',
        latency: 350,
        requests: 12345,
        errors: 234,
        successRate: 95.2,
        lastCheck: '20秒前',
        trend: 'down',
        available: true,
      },
      {
        id: 5,
        name: 'PostgreSQL',
        type: 'postgresql',
        status: 'testing',
        health: 'healthy',
        latency: 5,
        requests: 89012,
        errors: 2,
        successRate: 99.99,
        lastCheck: '5秒前',
        trend: 'up',
        available: true,
      },
      {
        id: 6,
        name: 'Redis Cache',
        type: 'redis',
        status: 'error',
        health: 'error',
        latency: 0,
        requests: 0,
        errors: 0,
        successRate: 0,
        lastCheck: '10分钟前',
        trend: 'down',
        available: false,
      },
    ],
  })

    // 鑷姩鍒锋柊
  useEffect(() => {
      // 鍒濆鍔犺浇鏁版嵁
    fetchMonitorData()

    if (!autoRefresh) return

    const timer = setInterval(() => {
      fetchMonitorData()
    }, refreshInterval)

    return () => clearInterval(timer)
  }, [autoRefresh, refreshInterval])

  const fetchMonitorData = async () => {
    try {
      const data = await dataSourceAPI.getDataSourceMonitor()

      const normalizedSources = Array.isArray(data?.sources)
        ? data.sources.map((source: any, index: number) => {
            const meta = getDataSourceStatusMeta(source?.status)
            const lastTestTime =
              source?.lastTestTime ?? source?.last_test_time ?? source?.last_tested_at ?? null
            const lastTransition =
              source?.lastTransition ?? source?.last_transition ?? source?.updated_at ?? null
            const testSummary = normalizeTestSummary(
              source?.testSummary ?? source?.test_summary ?? null
            )
            const hasSavedCredential =
              typeof source?.hasSavedCredential === 'boolean'
                ? source.hasSavedCredential
                : Boolean(source?.has_saved_credential)

            return {
              ...source,
              status: meta.value,
              available:
                typeof source?.available === 'boolean'
                  ? source.available
                  : typeof source?.is_available === 'boolean'
                    ? source.is_available
                    : undefined,
              lastTestTime,
              lastTransition,
              testSummary,
              hasSavedCredential,
              key: source?.id ?? source?.name ?? index,
            }
          })
        : []

      const overview = (data?.overview as Record<string, any>) ?? {}
      const statusSummary = (data?.statusSummary as Record<string, number>) ?? {}

      setMonitorData({
        overview: {
          total: normalizedSources.length,
          active: statusSummary.active ?? overview.active ?? 0,
          ready: statusSummary.ready ?? overview.ready ?? 0,
          degraded: statusSummary.degraded ?? overview.degraded ?? 0,
          error: statusSummary.error ?? overview.error ?? 0,
          offline: statusSummary.offline ?? overview.offline ?? 0,
          totalRequests: 0,
          avgLatency: 0,
          successRate: 0,
          errorRate: 0,
          requestsPerMinute: 0,
          bytesTransferred: 0,
          cacheHitRate: 0,
          activeConnections: 0,
          ...overview,
        },
        sources: normalizedSources,
        timeline: Array.isArray(data?.timeline) ? data.timeline : [],
        alerts: Array.isArray(data?.alerts) ? data.alerts : [],
        statusSummary,
      })

      if (Array.isArray(data?.timeline) && data.timeline.length > 0) {
        setLatencyTrendData(
          data.timeline.map((item: any) => ({
            time: item.time ?? item.timestamp ?? '',
            source: item.source ?? 'unknown',
            value: item.latency ?? item.latency_ms ?? 0,
          }))
        )

        const grouped = new Map<string, { success: number; total: number }>()
        data.timeline.forEach((item: any) => {
          const key = item.time ?? item.timestamp ?? ''
          const metrics = grouped.get(key) ?? { success: 0, total: 0 }
          metrics.total += item.requests ?? 1
          metrics.success += item.success === false || item.errors ? 0 : 1
          grouped.set(key, metrics)
        })
        setSuccessRateData(
          Array.from(grouped.entries()).map(([time, metrics]) => ({
            time,
            rate: metrics.total > 0 ? (metrics.success / metrics.total) * 100 : 0,
          }))
        )
      } else {
        setLatencyTrendData([])
        setSuccessRateData([])
      }

      if (normalizedSources.length > 0) {
        setRequestDistribution(
          normalizedSources.map(source => ({
            source: source.name || source.type,
            requests: source.metrics?.totalRequests ?? source.requests ?? 0,
          }))
        )
      } else {
        setRequestDistribution([])
      }
    } catch (error) {
      console.error('Failed to fetch monitor data:', error)
      if (!monitorData.overview.totalRequests) {
        setMonitorData({
          overview: {
            total: 0,
            active: 0,
            ready: 0,
            degraded: 0,
            error: 0,
            offline: 0,
            totalRequests: 0,
            avgLatency: 0,
            successRate: 0,
            errorRate: 0,
            requestsPerMinute: 0,
            bytesTransferred: 0,
            cacheHitRate: 0,
            activeConnections: 0,
          },
          sources: [],
          timeline: [],
          alerts: [],
          statusSummary: {},
        })
      }
    }
  }
  const handleRefresh = async () => {
    setLoading(true)
    await fetchMonitorData()
    setLoading(false)
    message.success('监控数据已刷新')
  }

  const getHealthIcon = health => {
    switch (health) {
      case 'healthy':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />
      case 'warning':
        return <WarningOutlined style={{ color: '#faad14' }} />
      case 'error':
        return <CloseCircleOutlined style={{ color: '#f5222d' }} />
      default:
        return <InfoCircleOutlined />
    }
  }

  const getTrendIcon = trend => {
    switch (trend) {
      case 'up':
        return <RiseOutlined style={{ color: '#52c41a' }} />
      case 'down':
        return <FallOutlined style={{ color: '#f5222d' }} />
      default:
        return <span>-</span>
    }
  }

    // 浜嬩欢鏃ュ織
  const eventLogs = [
    { time: '10:30:45', type: 'success', message: 'AmazingData 连接恢复正常' },
    { time: '10:28:12', type: 'error', message: 'Redis Cache 连接失败，错误码: TIMEOUT' },
      {time: '10:25:30', type: 'warning', message: 'AKShare 响应时间超过阈值（350ms）'},
    { time: '10:20:15', type: 'info', message: '开始执行数据源健康检查' },
    { time: '10:15:00', type: 'error', message: 'QMT Gateway 连接中断' },
    { time: '10:10:22', type: 'success', message: 'PostgreSQL 性能优化完成' },
  ]

    // 鍥捐〃鏁版嵁
  const [latencyTrendData, setLatencyTrendData] = useState([
    { time: '10:00', source: 'AmazingData', value: 45 },
    { time: '10:00', source: 'CloudFlare', value: 120 },
    { time: '10:00', source: 'AKShare', value: 350 },
    { time: '10:05', source: 'AmazingData', value: 42 },
    { time: '10:05', source: 'CloudFlare', value: 115 },
    { time: '10:05', source: 'AKShare', value: 380 },
    { time: '10:10', source: 'AmazingData', value: 48 },
    { time: '10:10', source: 'CloudFlare', value: 125 },
    { time: '10:10', source: 'AKShare', value: 320 },
    { time: '10:15', source: 'AmazingData', value: 44 },
    { time: '10:15', source: 'CloudFlare', value: 118 },
    { time: '10:15', source: 'AKShare', value: 360 },
    { time: '10:20', source: 'AmazingData', value: 46 },
    { time: '10:20', source: 'CloudFlare', value: 122 },
    { time: '10:20', source: 'AKShare', value: 340 },
  ])

  const [successRateData, setSuccessRateData] = useState([
    { time: '10:00', rate: 98.5 },
    { time: '10:05', rate: 99.2 },
    { time: '10:10', rate: 97.8 },
    { time: '10:15', rate: 98.9 },
    { time: '10:20', rate: 99.1 },
    { time: '10:25', rate: 98.7 },
    { time: '10:30', rate: 99.3 },
  ])

  const [requestDistribution, setRequestDistribution] = useState([
    { source: 'AmazingData', requests: 45678 },
    { source: 'CloudFlare', requests: 23456 },
    { source: 'AKShare', requests: 12345 },
    { source: 'PostgreSQL', requests: 89012 },
  ])

  const healthScore = 85

  const statusCounts = React.useMemo(() => {
    const counts = DATA_SOURCE_STATUS_ORDER.reduce(
      (acc, status) => {
        acc[status] = 0
        return acc
      },
      {} as Record<string, number>
    )

    const sourcesList = Array.isArray(monitorData.sources) ? monitorData.sources : []
    sourcesList.forEach((source: any) => {
      const meta = getDataSourceStatusMeta(source?.status)
      if (Object.prototype.hasOwnProperty.call(counts, meta.value)) {
        counts[meta.value] += 1
      }
    })

    return counts
  }, [monitorData.sources])

  const totalSources = monitorData.sources?.length || 0

  const availableSources = React.useMemo(
    () =>
      (monitorData.sources || []).reduce(
        (acc: number, source: any) => (source?.available ? acc + 1 : acc),
        0
      ),
    [monitorData.sources]
  )

  const statusDistribution = React.useMemo(
    () =>
      DATA_SOURCE_STATUS_ORDER.map(statusKey => ({
        status: statusKey,
        type: getDataSourceStatusMeta(statusKey).text,
        value: statusCounts[statusKey] || 0,
      })).filter(item => item.value > 0),
    [statusCounts]
  )

  const abnormalCount = statusCounts.degraded + statusCounts.error

    // 鍥捐〃缁勪欢
  const LatencyTrendChart = ({ data }) => {
    const config = {
      data,
      xField: 'time',
      yField: 'value',
      seriesField: 'source',
      smooth: true,
      animation: {
        appear: {
          animation: 'path-in',
          duration: 1000,
        },
      },
      xAxis: {
          title: {text: '鏃堕棿'},
      },
      yAxis: {
          title: {text: '寤惰繜 (ms)'},
      },
      legend: {
        position: 'top-right',
      },
    }
    return <Line {...config} />
  }

  const SuccessRateChart = ({ data }) => {
    const config = {
      data,
      xField: 'time',
      yField: 'rate',
      smooth: true,
      area: {
        style: {
          fill: 'l(270) 0:#ffffff 0.5:#7ec2f3 1:#1890ff',
        },
      },
      xAxis: {
          title: {text: '鏃堕棿'},
      },
      yAxis: {
          title: {text: '鎴愬姛鐜?(%)'},
        min: 95,
        max: 100,
      },
      annotations: [
        {
          type: 'line',
          start: ['min', 98],
          end: ['max', 98],
          style: {
            stroke: '#F4664A',
            lineDash: [2, 2],
          },
        },
      ],
    }
    return <Area {...config} />
  }

  const StatusDistributionChart = ({ data }) => {
    const config = {
      data,
      angleField: 'value',
      colorField: 'status',
      radius: 0.8,
      color: ({ status }) => getDataSourceStatusMeta(status).tagColor,
      label: {
        type: 'inner',
        offset: '-30%',
        content: ({ type, percent }) => `${type} ${(percent * 100).toFixed(0)}%`,
        style: {
          fontSize: 12,
        },
      },
      legend: {
        position: 'bottom',
        itemName: {
          formatter: (value: string) => getDataSourceStatusMeta(value).text,
        },
      },
      tooltip: {
        formatter: datum => ({
          name: datum.type,
          value: datum.value,
        }),
      },
      interactions: [
        {
          type: 'pie-legend-active',
        },
        {
          type: 'element-active',
        },
      ],
    }
    return <Pie {...config} />
  }

  const RequestDistributionChart = ({ data }) => {
    const config = {
      data,
      xField: 'source',
      yField: 'requests',
      color: ({ source }) => {
        const colors = {
          AmazingData: '#ffd700',
          CloudFlare: '#1890ff',
          AKShare: '#faad14',
          PostgreSQL: '#722ed1',
        }
        return colors[source] || '#666'
      },
      label: {
        position: 'top',
        style: {
          fill: '#000',
          opacity: 0.8,
        },
      },
      xAxis: {
        label: {
          autoRotate: false,
        },
      },
      yAxis: {
          title: {text: '请求数量'},
      },
    }
    return <Column {...config} />
  }

  const HealthScoreGauge = ({ score }) => {
    const config = {
      percent: score / 100,
      range: {
        color: 'l(0) 0:#F4664A 0.5:#FAAD14 1:#52c41a',
      },
      indicator: {
        pointer: {
          style: {
            stroke: '#D0D0D0',
          },
        },
        pin: {
          style: {
            stroke: '#D0D0D0',
          },
        },
      },
      statistic: {
        content: {
          formatter: ({ percent }) => `${(percent * 100).toFixed(0)}分`,
          style: {
            fontSize: '24px',
            lineHeight: '36px',
          },
        },
      },
    }
    return <Gauge {...config} />
  }

  const columns = [
    {
      title: '数据源',
      dataIndex: 'name',
      key: 'name',
      fixed: 'left',
      width: 150,
      render: (text, record) => (
        <Space>
          {getHealthIcon(record.health)}
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (_, record) => {
        const meta = getDataSourceStatusMeta(record.status)

        const tooltipLines = [meta.description]

        if (record.reason) {
          tooltipLines.push(`原因: ${record.reason}`)
        }

        if (record.testSummary) {
          tooltipLines.push(`测试摘要: ${record.testSummary}`)
        }

        if (record.lastTestTime) {
          tooltipLines.push(`最近测试: ${formatDateTime(record.lastTestTime)}`)
        } else if (record.lastTransition) {
          tooltipLines.push(`最近变更: ${formatDateTime(record.lastTransition)}`)
        } else if (record.lastCheck) {
          tooltipLines.push(`最近检查: ${formatDateTime(record.lastCheck)}`)
        }

        if (record.hasSavedCredential) {
          tooltipLines.push('凭据: 已保存')
        }

        const tooltipContent = (
          <div>
            {tooltipLines.map((line, index) => (
              <div
                key={index}
                style={{ marginTop: index === 0 ? 0 : 4, fontSize: 12, color: '#8c8c8c' }}
              >
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
              <Tooltip title={record.available ? '当前可用' : '当前不可用'}>
                <Badge status={record.available ? 'success' : 'error'} />
              </Tooltip>
            )}
          </Space>
        )
      },
    },
    {
      title: '健康度',
      dataIndex: 'health',
      key: 'health',
      width: 100,
      render: health => {
        const config = {
          healthy: { color: 'success', text: '健康' },
            warning: {color: 'warning', text: '告警'},
          error: { color: 'error', text: '错误' },
        }
        return <Tag color={config[health]?.color}>{config[health]?.text}</Tag>
      },
    },
    {
        title: '寤惰繜',
      dataIndex: 'latency',
      key: 'latency',
      width: 100,
      sorter: (a, b) => a.latency - b.latency,
      render: latency => {
        const color = latency < 100 ? '#52c41a' : latency < 200 ? '#faad14' : '#f5222d'
        return <span style={{ color }}>{latency}ms</span>
      },
    },
    {
      title: '请求数',
      dataIndex: 'requests',
      key: 'requests',
      width: 120,
      sorter: (a, b) => a.requests - b.requests,
      render: requests => requests.toLocaleString(),
    },
    {
      title: '错误数',
      dataIndex: 'errors',
      key: 'errors',
      width: 100,
      render: errors => <span style={{ color: errors > 100 ? '#f5222d' : '#000' }}>{errors}</span>,
    },
    {
      title: '成功率',
      dataIndex: 'successRate',
      key: 'successRate',
      width: 120,
      render: rate => (
        <Progress
          percent={rate}
          size="small"
          strokeColor={rate > 95 ? '#52c41a' : rate > 90 ? '#faad14' : '#f5222d'}
        />
      ),
    },
    {
      title: '趋势',
      dataIndex: 'trend',
      key: 'trend',
      width: 80,
      render: trend => getTrendIcon(trend),
    },
    {
        title: '最近检查',
      dataIndex: 'lastCheck',
      key: 'lastCheck',
      width: 100,
    },
  ]

  return (
    <div>
      <ProCard gutter={[16, 16]}>
        <ProCard colSpan={24}>
          <Row justify="space-between" align="middle">
            <Col>
              <Space size="large">
                <Title level={4} style={{ margin: 0 }}>
                  <MonitorOutlined /> 数据源实时监控
                </Title>
                <Tag color="blue">
                  <ClockCircleOutlined /> 实时数据
                </Tag>
              </Space>
            </Col>
            <Col>
              <Space>
                <Select
                  value={timeRange}
                  onChange={setTimeRange}
                  style={{ width: 120 }}
                  options={[
                    { label: '最近1小时', value: '1h' },
                    { label: '最近6小时', value: '6h' },
                    { label: '最近24小时', value: '24h' },
                    { label: '最近7天', value: '7d' },
                  ]}
                />
                <Select
                  value={selectedSource}
                  onChange={setSelectedSource}
                  style={{ width: 150 }}
                  options={[
                    { label: '全部数据源', value: 'all' },
                    { label: 'AmazingData', value: 'amazingdata' },
                    { label: 'CloudFlare', value: 'cloudflare' },
                    { label: 'QMT', value: 'qmt' },
                    { label: 'AKShare', value: 'akshare' },
                  ]}
                />
                <Switch
                  checked={autoRefresh}
                  onChange={setAutoRefresh}
                  checkedChildren="自动刷新"
                  unCheckedChildren="手动"
                />
                <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={loading}>
                    鍒锋柊
                </Button>
              </Space>
            </Col>
          </Row>
        </ProCard>

          {/* 姒傝缁熻 */}
        <ProCard colSpan={24}>
          <StatisticCard.Group>
            <StatisticCard
              statistic={{
                  title: '鎬绘暟鎹簮',
                value: totalSources,
                icon: <DatabaseOutlined style={{ fontSize: 24, color: '#1890ff' }} />,
              }}
            />
            <StatisticCard
              statistic={{
                  title: '鍙敤',
                value: availableSources,
                valueStyle: { color: '#52c41a' },
                icon: <CheckCircleOutlined style={{ fontSize: 24, color: '#52c41a' }} />,
              }}
            />
            <StatisticCard
              statistic={{
                  title: '总计异常',
                value: abnormalCount,
                valueStyle: { color: '#faad14' },
                icon: <WarningOutlined style={{ fontSize: 24, color: '#faad14' }} />,
              }}
            />
            <StatisticCard
              statistic={{
                title: '总请求数',
                value: monitorData.overview.totalRequests,
                suffix: '次',
                icon: <ApiOutlined style={{ fontSize: 24, color: '#722ed1' }} />,
              }}
            />
            <StatisticCard
              statistic={{
                title: '平均延迟',
                value: monitorData.overview.avgLatency,
                suffix: 'ms',
                valueStyle: {
                  color: monitorData.overview.avgLatency > 100 ? '#faad14' : '#52c41a',
                },
                icon: <ThunderboltOutlined style={{ fontSize: 24, color: '#faad14' }} />,
              }}
            />
            <StatisticCard
              statistic={{
                title: '总体成功率',
                value: monitorData.overview.successRate,
                suffix: '%',
                precision: 2,
                valueStyle: { color: '#52c41a' },
                icon: <LineChartOutlined style={{ fontSize: 24, color: '#52c41a' }} />,
              }}
            />
          </StatisticCard.Group>
        </ProCard>

        <ProCard colSpan={24}>
          <Card
            title="状态概览"
            variant="borderless"
            extra={
              <Tooltip title="当前可用的数据源数量">
                <span style={{ fontSize: 12, color: '#666' }}>
                  可用: {availableSources}/{totalSources}
                </span>
              </Tooltip>
            }
          >
            <Space size={[12, 8]} wrap>
              {DATA_SOURCE_STATUS_ORDER.map(statusKey => {
                const meta = getDataSourceStatusMeta(statusKey)
                const count = statusCounts[statusKey] || 0
                return (
                  <Tooltip key={statusKey} title={meta.description}>
                    <Tag
                      color={meta.tagColor}
                      style={{ padding: '4px 10px', borderRadius: 14, margin: 0 }}
                    >
                      {meta.text}
                      <span style={{ marginLeft: 6, fontWeight: 600 }}>{count}</span>
                    </Tag>
                  </Tooltip>
                )
              })}
            </Space>
          </Card>
        </ProCard>

        {/* 数据源详情表格 */}
        <ProCard colSpan={24}>
          <Card title="数据源详情" variant="borderless">
            <Table
              columns={columns}
              dataSource={monitorData.sources}
              rowKey="id"
              pagination={false}
              scroll={{ x: 1200 }}
              loading={loading}
            />
          </Card>
        </ProCard>

          {/* 鎬ц兘瓒嬪娍鍥捐〃 */}
        <ProCard colSpan={12}>
          <Card title="延迟趋势" variant="borderless">
            <LatencyTrendChart data={latencyTrendData} />
          </Card>
        </ProCard>

        <ProCard colSpan={12}>
          <Card title="请求成功率" variant="borderless">
            <SuccessRateChart data={successRateData} />
          </Card>
        </ProCard>

        {/* 数据源分布 */}
        <ProCard colSpan={8}>
          <Card title="数据源状态分布" variant="borderless">
            <StatusDistributionChart data={statusDistribution} />
          </Card>
        </ProCard>

        <ProCard colSpan={8}>
          <Card title="请求量分布" variant="borderless">
            <RequestDistributionChart data={requestDistribution} />
          </Card>
        </ProCard>

        <ProCard colSpan={8}>
            <Card title="健康评分" variant="borderless">
            <HealthScoreGauge score={healthScore} />
          </Card>
        </ProCard>

        {/* 事件日志 */}
        <ProCard colSpan={24}>
          <Card title="事件日志" variant="borderless">
            <Timeline mode="left">
              {eventLogs.map((log, index) => {
                const color =
                  log.type === 'success'
                    ? 'green'
                    : log.type === 'error'
                      ? 'red'
                      : log.type === 'warning'
                        ? 'orange'
                        : 'blue'

                return (
                  <Timeline.Item key={index} color={color} label={log.time}>
                    <Tag color={color}>{log.type.toUpperCase()}</Tag>
                    {log.message}
                  </Timeline.Item>
                )
              })}
            </Timeline>
          </Card>
        </ProCard>
      </ProCard>
    </div>
  )
}

export default DataSourceMonitor


