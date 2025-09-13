import React, { useState, useEffect } from 'react'
import {
  Card,
  Row,
  Col,
  Statistic,
  Progress,
  Table,
  Tag,
  Space,
  Button,
  Alert,
  Badge,
  Timeline,
  Typography,
  Tabs,
  List,
  Avatar,
  Tooltip,
  Switch,
  Select,
  DatePicker
} from 'antd'
import { ProCard, StatisticCard, ProTable } from '@ant-design/pro-components'
import { Line, Column, Pie, Area, Gauge } from '@ant-design/charts'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  CloudOutlined,
  ApiOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  LineChartOutlined,
  MonitorOutlined,
  ClockCircleOutlined,
  RiseOutlined,
  FallOutlined,
  ReloadOutlined
} from '@ant-design/icons'

const { Title, Text } = Typography
const { RangePicker } = DatePicker

const DataSourceMonitor = () => {
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshInterval, setRefreshInterval] = useState(5000)
  const [selectedSource, setSelectedSource] = useState('all')
  const [timeRange, setTimeRange] = useState('1h')
  
  // 模拟实时数据
  const [monitorData, setMonitorData] = useState({
    overview: {
      total: 6,
      online: 4,
      offline: 2,
      healthy: 3,
      warning: 1,
      error: 2,
      totalRequests: 125432,
      avgLatency: 85,
      successRate: 98.5
    },
    sources: [
      {
        id: 1,
        name: 'AmazingData',
        type: 'amazingdata',
        status: 'online',
        health: 'healthy',
        latency: 45,
        requests: 45678,
        errors: 23,
        successRate: 99.8,
        lastCheck: '10秒前',
        trend: 'up'
      },
      {
        id: 2,
        name: 'CloudFlare Workers',
        type: 'cloudflare',
        status: 'online',
        health: 'healthy',
        latency: 120,
        requests: 23456,
        errors: 156,
        successRate: 98.5,
        lastCheck: '15秒前',
        trend: 'stable'
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
        trend: 'down'
      },
      {
        id: 4,
        name: 'AKShare',
        type: 'akshare',
        status: 'online',
        health: 'warning',
        latency: 350,
        requests: 12345,
        errors: 234,
        successRate: 95.2,
        lastCheck: '20秒前',
        trend: 'down'
      },
      {
        id: 5,
        name: 'PostgreSQL',
        type: 'postgresql',
        status: 'online',
        health: 'healthy',
        latency: 5,
        requests: 89012,
        errors: 2,
        successRate: 99.99,
        lastCheck: '5秒前',
        trend: 'up'
      },
      {
        id: 6,
        name: 'Redis Cache',
        type: 'redis',
        status: 'offline',
        health: 'error',
        latency: 0,
        requests: 0,
        errors: 0,
        successRate: 0,
        lastCheck: '10分钟前',
        trend: 'down'
      }
    ]
  })

  // 自动刷新
  useEffect(() => {
    if (!autoRefresh) return
    
    const timer = setInterval(() => {
      // 模拟数据更新
      setMonitorData(prev => ({
        ...prev,
        overview: {
          ...prev.overview,
          totalRequests: prev.overview.totalRequests + Math.floor(Math.random() * 100),
          avgLatency: 80 + Math.floor(Math.random() * 20),
          successRate: 97 + Math.random() * 3
        }
      }))
    }, refreshInterval)
    
    return () => clearInterval(timer)
  }, [autoRefresh, refreshInterval])

  const handleRefresh = () => {
    setLoading(true)
    setTimeout(() => {
      setLoading(false)
    }, 1000)
  }

  const getHealthIcon = (health) => {
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

  const getTrendIcon = (trend) => {
    switch (trend) {
      case 'up':
        return <RiseOutlined style={{ color: '#52c41a' }} />
      case 'down':
        return <FallOutlined style={{ color: '#f5222d' }} />
      default:
        return <span>-</span>
    }
  }

  // 事件日志
  const eventLogs = [
    { time: '10:30:45', type: 'success', message: 'AmazingData 连接恢复正常' },
    { time: '10:28:12', type: 'error', message: 'Redis Cache 连接失败，错误码: TIMEOUT' },
    { time: '10:25:30', type: 'warning', message: 'AKShare 响应时间超过阈值 (350ms)' },
    { time: '10:20:15', type: 'info', message: '开始执行数据源健康检查' },
    { time: '10:15:00', type: 'error', message: 'QMT Gateway 连接中断' },
    { time: '10:10:22', type: 'success', message: 'PostgreSQL 性能优化完成' },
  ]

  // 图表数据
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

  const statusDistribution = [
    { type: '在线', value: 4 },
    { type: '离线', value: 2 },
  ]

  const requestDistribution = [
    { source: 'AmazingData', requests: 45678 },
    { source: 'CloudFlare', requests: 23456 },
    { source: 'AKShare', requests: 12345 },
    { source: 'PostgreSQL', requests: 89012 },
  ]

  const healthScore = 85

  // 图表组件
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
        title: { text: '时间' },
      },
      yAxis: {
        title: { text: '延迟 (ms)' },
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
        title: { text: '时间' },
      },
      yAxis: {
        title: { text: '成功率 (%)' },
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
      colorField: 'type',
      radius: 0.8,
      label: {
        type: 'inner',
        offset: '-30%',
        content: '{name} {percentage}',
      },
      interactions: [
        {
          type: 'pie-legend-active',
        },
        {
          type: 'element-active',
        },
      ],
      color: ['#52c41a', '#f5222d'],
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
          'AmazingData': '#ffd700',
          'CloudFlare': '#1890ff',
          'AKShare': '#faad14',
          'PostgreSQL': '#722ed1',
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
        title: { text: '请求数' },
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
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status) => (
        <Badge
          status={status === 'online' ? 'success' : 'error'}
          text={status === 'online' ? '在线' : '离线'}
        />
      )
    },
    {
      title: '健康度',
      dataIndex: 'health',
      key: 'health',
      width: 100,
      render: (health) => {
        const config = {
          healthy: { color: 'success', text: '健康' },
          warning: { color: 'warning', text: '警告' },
          error: { color: 'error', text: '错误' }
        }
        return <Tag color={config[health]?.color}>{config[health]?.text}</Tag>
      }
    },
    {
      title: '延迟',
      dataIndex: 'latency',
      key: 'latency',
      width: 100,
      sorter: (a, b) => a.latency - b.latency,
      render: (latency) => {
        const color = latency < 100 ? '#52c41a' : latency < 200 ? '#faad14' : '#f5222d'
        return <span style={{ color }}>{latency}ms</span>
      }
    },
    {
      title: '请求数',
      dataIndex: 'requests',
      key: 'requests',
      width: 120,
      sorter: (a, b) => a.requests - b.requests,
      render: (requests) => requests.toLocaleString()
    },
    {
      title: '错误数',
      dataIndex: 'errors',
      key: 'errors',
      width: 100,
      render: (errors) => (
        <span style={{ color: errors > 100 ? '#f5222d' : '#000' }}>
          {errors}
        </span>
      )
    },
    {
      title: '成功率',
      dataIndex: 'successRate',
      key: 'successRate',
      width: 120,
      render: (rate) => (
        <Progress
          percent={rate}
          size="small"
          strokeColor={rate > 95 ? '#52c41a' : rate > 90 ? '#faad14' : '#f5222d'}
        />
      )
    },
    {
      title: '趋势',
      dataIndex: 'trend',
      key: 'trend',
      width: 80,
      render: (trend) => getTrendIcon(trend)
    },
    {
      title: '最后检查',
      dataIndex: 'lastCheck',
      key: 'lastCheck',
      width: 100
    }
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
                    { label: '最近7天', value: '7d' }
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
                    { label: 'AKShare', value: 'akshare' }
                  ]}
                />
                <Switch
                  checked={autoRefresh}
                  onChange={setAutoRefresh}
                  checkedChildren="自动刷新"
                  unCheckedChildren="手动"
                />
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleRefresh}
                  loading={loading}
                >
                  刷新
                </Button>
              </Space>
            </Col>
          </Row>
        </ProCard>

        {/* 概览统计 */}
        <ProCard colSpan={24}>
          <StatisticCard.Group>
            <StatisticCard
              statistic={{
                title: '总数据源',
                value: monitorData.overview.total,
                icon: <DatabaseOutlined style={{ fontSize: 24, color: '#1890ff' }} />
              }}
            />
            <StatisticCard
              statistic={{
                title: '在线',
                value: monitorData.overview.online,
                valueStyle: { color: '#52c41a' },
                icon: <CheckCircleOutlined style={{ fontSize: 24, color: '#52c41a' }} />
              }}
            />
            <StatisticCard
              statistic={{
                title: '离线',
                value: monitorData.overview.offline,
                valueStyle: { color: '#f5222d' },
                icon: <CloseCircleOutlined style={{ fontSize: 24, color: '#f5222d' }} />
              }}
            />
            <StatisticCard
              statistic={{
                title: '总请求数',
                value: monitorData.overview.totalRequests,
                suffix: '次',
                icon: <ApiOutlined style={{ fontSize: 24, color: '#722ed1' }} />
              }}
            />
            <StatisticCard
              statistic={{
                title: '平均延迟',
                value: monitorData.overview.avgLatency,
                suffix: 'ms',
                valueStyle: { color: monitorData.overview.avgLatency > 100 ? '#faad14' : '#52c41a' },
                icon: <ThunderboltOutlined style={{ fontSize: 24, color: '#faad14' }} />
              }}
            />
            <StatisticCard
              statistic={{
                title: '总体成功率',
                value: monitorData.overview.successRate,
                suffix: '%',
                precision: 2,
                valueStyle: { color: '#52c41a' },
                icon: <LineChartOutlined style={{ fontSize: 24, color: '#52c41a' }} />
              }}
            />
          </StatisticCard.Group>
        </ProCard>

        {/* 数据源详情表格 */}
        <ProCard colSpan={24}>
          <Card title="数据源详情" bordered={false}>
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

        {/* 性能趋势图表 */}
        <ProCard colSpan={12}>
          <Card title="延迟趋势" bordered={false}>
            <LatencyTrendChart data={latencyTrendData} />
          </Card>
        </ProCard>

        <ProCard colSpan={12}>
          <Card title="请求成功率" bordered={false}>
            <SuccessRateChart data={successRateData} />
          </Card>
        </ProCard>

        {/* 数据源分布 */}
        <ProCard colSpan={8}>
          <Card title="数据源状态分布" bordered={false}>
            <StatusDistributionChart data={statusDistribution} />
          </Card>
        </ProCard>

        <ProCard colSpan={8}>
          <Card title="请求量分布" bordered={false}>
            <RequestDistributionChart data={requestDistribution} />
          </Card>
        </ProCard>

        <ProCard colSpan={8}>
          <Card title="健康度评分" bordered={false}>
            <HealthScoreGauge score={healthScore} />
          </Card>
        </ProCard>

        {/* 事件日志 */}
        <ProCard colSpan={24}>
          <Card title="事件日志" bordered={false}>
            <Timeline mode="left">
              {eventLogs.map((log, index) => {
                const color = log.type === 'success' ? 'green' : 
                             log.type === 'error' ? 'red' : 
                             log.type === 'warning' ? 'orange' : 'blue'
                
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