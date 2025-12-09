// @ts-nocheck
import React, {useCallback, useEffect, useState} from 'react'
import {Button, Card, Col, message, Progress, Row, Space, Statistic, Table, Tag, Timeline} from 'antd'
import {
    ApiOutlined,
    ClockCircleOutlined,
    DatabaseOutlined,
    InboxOutlined,
    ReloadOutlined,
    SendOutlined,
    SyncOutlined,
    ThunderboltOutlined
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'

import {type EventSystemOverviewResponse, monitorAPI} from '@/api/monitor'

// 事件流量监控卡片
const EventFlowCard = ({ metrics, loading }) => {
  return (
    <Card title={<Space><ThunderboltOutlined /> 事件流量监控</Space>} loading={loading}>
      <Row gutter={[16, 16]}>
        <Col span={8}>
          <Statistic
            title="事件产生速率"
            value={metrics?.produceRate || 0}
            suffix="条/秒"
            valueStyle={{ color: '#1890ff' }}
            prefix={<SendOutlined />}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="事件处理速率"
            value={metrics?.consumeRate || 0}
            suffix="条/秒"
            valueStyle={{ color: '#52c41a' }}
            prefix={<SyncOutlined />}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="队列深度"
            value={metrics?.queueDepth || 0}
            suffix="条"
            valueStyle={{ color: metrics?.queueDepth > 1000 ? '#f5222d' : '#1890ff' }}
            prefix={<InboxOutlined />}
          />
        </Col>
      </Row>
      <div style={{ marginTop: 24 }}>
        <div style={{ marginBottom: 8 }}>
          <span>队列使用率</span>
          <span style={{ float: 'right' }}>{metrics?.queueUsage || 0}%</span>
        </div>
        <Progress 
          percent={metrics?.queueUsage || 0} 
          strokeColor={{
            '0%': '#52c41a',
            '50%': '#faad14',
            '100%': '#f5222d',
          }}
        />
      </div>
    </Card>
  )
}

// 事件类型分布图
const EventTypeChart = ({ data, loading }) => {
  const option = {
    title: {
      text: '事件类型分布',
      left: 'center'
    },
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    legend: {
      bottom: '5%',
      left: 'center'
    },
    series: [
      {
        name: '事件类型',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 20,
            fontWeight: 'bold'
          }
        },
        labelLine: {
          show: false
        },
        data: data || []
      }
    ]
  }

  return (
    <Card loading={loading}>
      <ReactECharts option={option} style={{ height: 300 }} />
    </Card>
  )
}

// 事件处理延迟分布
const EventLatencyChart = ({ data, loading }) => {
  const option = {
    title: {
      text: '事件处理延迟分布',
      left: 'center'
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    xAxis: {
      type: 'category',
      data: data?.categories || ['<10ms', '10-50ms', '50-100ms', '100-500ms', '>500ms']
    },
    yAxis: {
      type: 'value',
      name: '事件数量'
    },
    series: [
      {
        name: '事件数',
        type: 'bar',
        data: data?.values || [],
        itemStyle: {
          color: (params) => {
            const colors = ['#52c41a', '#73d13d', '#faad14', '#fa8c16', '#f5222d']
            return colors[params.dataIndex]
          }
        }
      }
    ]
  }

  return (
    <Card loading={loading}>
      <ReactECharts option={option} style={{ height: 300 }} />
    </Card>
  )
}

// 消息总线状态
const MessageBusStatus = ({ buses, loading }) => {
  const columns = [
    {
      title: '总线类型',
      dataIndex: 'type',
      key: 'type',
      render: (type) => (
        <Space>
          <ApiOutlined />
          <span>{type}</span>
        </Space>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => (
        <Tag color={status === 'connected' ? 'green' : 'red'}>
          {status === 'connected' ? '已连接' : '断开'}
        </Tag>
      )
    },
    {
      title: '吞吐量',
      dataIndex: 'throughput',
      key: 'throughput',
      render: (val) => `${val} msg/s`
    },
    {
      title: '连接数',
      dataIndex: 'connections',
      key: 'connections',
    },
    {
      title: '缓冲区使用',
      dataIndex: 'bufferUsage',
      key: 'bufferUsage',
      render: (usage) => (
        <Progress percent={usage} size="small" strokeColor={usage > 80 ? '#f5222d' : '#52c41a'} />
      )
    },
  ]

  return (
    <Card 
      title={<Space><DatabaseOutlined /> 消息总线状态</Space>} 
      loading={loading}
    >
      <Table
        columns={columns}
        dataSource={buses || []}
        rowKey="type"
        size="small"
        pagination={false}
      />
    </Card>
  )
}

// 事件处理器性能
const EventHandlerPerformance = ({ handlers, loading }) => {
  const columns = [
    {
      title: '处理器',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '处理事件数',
      dataIndex: 'processed',
      key: 'processed',
      sorter: (a, b) => a.processed - b.processed,
    },
    {
      title: '成功率',
      dataIndex: 'successRate',
      key: 'successRate',
      render: (rate) => (
        <Progress 
          percent={rate} 
          size="small" 
          strokeColor={rate >= 95 ? '#52c41a' : rate >= 80 ? '#faad14' : '#f5222d'}
        />
      ),
      sorter: (a, b) => a.successRate - b.successRate,
    },
    {
      title: '平均处理时间',
      dataIndex: 'avgTime',
      key: 'avgTime',
      render: (time) => (typeof time === 'number' ? `${time.toFixed(2)} ms` : (time ?? '-')),
      sorter: (a, b) => a.avgTime - b.avgTime,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => (
        <Tag color={status === 'active' ? 'green' : 'orange'}>
          {status === 'active' ? '活跃' : '空闲'}
        </Tag>
      )
    },
  ]

  return (
    <Card 
      title={<Space><ClockCircleOutlined /> 事件处理器性能</Space>} 
      loading={loading}
    >
      <Table
        columns={columns}
        dataSource={handlers || []}
        rowKey="name"
        size="small"
        pagination={{ pageSize: 10 }}
      />
    </Card>
  )
}

// 实时事件流
const EventStream = ({ events, loading }) => {
  return (
    <Card 
      title={<Space><SyncOutlined spin /> 实时事件流</Space>} 
      loading={loading}
      styles={{ body: { maxHeight: 400, overflowY: 'auto' } }}
    >
      <Timeline mode="left">
        {(events || []).map((event, index) => (
          <Timeline.Item 
            key={index}
            color={event.type === 'error' ? 'red' : event.type === 'warning' ? 'orange' : 'green'}
            label={new Date(event.time).toLocaleTimeString('zh-CN')}
          >
            <Space direction="vertical" size="small">
              <Tag color={event.type === 'error' ? 'red' : event.type === 'warning' ? 'orange' : 'blue'}>
                {event.eventType}
              </Tag>
              <span>{event.message}</span>
            </Space>
          </Timeline.Item>
        ))}
      </Timeline>
    </Card>
  )
}

// 主页面组件
const EventSystem = () => {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
    const [eventMetrics, setEventMetrics] =
        useState<EventSystemOverviewResponse['eventMetrics'] | null>(null)
    const [eventTypes, setEventTypes] = useState<EventSystemOverviewResponse['eventTypes']>([])
    const [latencyData, setLatencyData] =
        useState<EventSystemOverviewResponse['latencyDistribution']>({
            categories: [],
            values: [],
        })
    const [messageBuses, setMessageBuses] =
        useState<EventSystemOverviewResponse['messageBuses']>([])
    const [eventHandlers, setEventHandlers] =
        useState<EventSystemOverviewResponse['eventHandlers']>([])
    const [eventStream, setEventStream] =
        useState<EventSystemOverviewResponse['eventStream']>([])

    const fetchOverview = useCallback(
        async (options: { showSuccess?: boolean } = {}) => {
            try {
                const data = await monitorAPI.getEventSystemOverview()
                setEventMetrics(data.eventMetrics ?? null)
                setEventTypes(data.eventTypes ?? [])
                setLatencyData(data.latencyDistribution ?? {categories: [], values: []})
                setMessageBuses(data.messageBuses ?? [])
                setEventHandlers(data.eventHandlers ?? [])
                setEventStream(data.eventStream ?? [])

                if (options.showSuccess) {
                    message.success('数据刷新成功')
                }
                return true
            } catch (error) {
                const errorMessage = error instanceof Error ? error.message : String(error)
                message.error(`获取事件系统数据失败：${errorMessage}`)
                return false
            } finally {
                setLoading(false)
            }
        },
        []
    )

    useEffect(() => {
        fetchOverview()
        const interval = setInterval(() => {
            fetchOverview()
        }, 5000)

    return () => clearInterval(interval)
    }, [fetchOverview])

  const refreshAll = async () => {
    setRefreshing(true)
      await fetchOverview({showSuccess: true})
      setRefreshing(false)
  }

  return (
    <div>
      {/* 页面标题 */}
      <div style={{ marginBottom: 24 }}>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <h1 style={{ margin: 0 }}>
            <ApiOutlined /> 事件系统监控
          </h1>
          <Button 
            type="primary" 
            icon={<ReloadOutlined spin={refreshing} />}
            onClick={refreshAll}
            loading={refreshing}
          >
            刷新
          </Button>
        </Space>
      </div>

      {/* 事件流量监控 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={24}>
          <EventFlowCard metrics={eventMetrics} loading={loading} />
        </Col>
      </Row>

      {/* 事件分布图表 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <EventTypeChart data={eventTypes} loading={loading} />
        </Col>
        <Col xs={24} lg={12}>
          <EventLatencyChart data={latencyData} loading={loading} />
        </Col>
      </Row>

      {/* 消息总线状态 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={24}>
          <MessageBusStatus buses={messageBuses} loading={loading} />
        </Col>
      </Row>

      {/* 事件处理器和实时流 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <EventHandlerPerformance handlers={eventHandlers} loading={loading} />
        </Col>
        <Col xs={24} lg={8}>
          <EventStream events={eventStream} loading={loading} />
        </Col>
      </Row>
    </div>
  )
}

export default EventSystem

