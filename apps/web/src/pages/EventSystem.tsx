import React, {useCallback, useEffect, useState} from 'react'
import {
    Button,
    type GlobalToken,
    message,
    Progress,
    Space,
    Statistic,
    Table,
    Tag,
    theme,
    Timeline,
    Typography
} from 'antd'
import {
    ApiOutlined,
    ClockCircleOutlined,
    DatabaseOutlined,
    InboxOutlined,
    ReloadOutlined,
    SendOutlined,
    SyncOutlined,
    ThunderboltOutlined,
} from '@ant-design/icons'
import {PageContainer, ProCard, type ProCardProps} from '@ant-design/pro-components'
import ReactECharts from 'echarts-for-react'

import {type EventSystemOverviewResponse, monitorAPI} from '@/api/monitor'

const {Text} = Typography

// Interfaces and Components
interface EventFlowCardProps extends ProCardProps {
    metrics: EventSystemOverviewResponse['eventMetrics'] | null
    loading: boolean
    token: GlobalToken
}

const EventFlowCard: React.FC<EventFlowCardProps> = ({metrics, loading, token, ...props}) => {
  return (
      <ProCard
          title={<Space><ThunderboltOutlined style={{color: token.colorPrimary}}/><span>事件流量监控</span></Space>}
          loading={loading}
          bordered
          headerBordered
          boxShadow
          {...props}
      >
          {/* ... existing content ... */}
          <ProCard ghost gutter={16}>
              <ProCard colSpan={8}>
          <Statistic
            title="事件产生速率"
            value={metrics?.produceRate || 0}
            suffix="条/秒"
            valueStyle={{color: token.colorPrimary}}
            prefix={<SendOutlined />}
          />
              </ProCard>
              <ProCard colSpan={8}>
          <Statistic
            title="事件处理速率"
            value={metrics?.consumeRate || 0}
            suffix="条/秒"
            valueStyle={{color: token.colorSuccess}}
            prefix={<SyncOutlined />}
          />
              </ProCard>
              <ProCard colSpan={8}>
          <Statistic
            title="队列深度"
            value={metrics?.queueDepth || 0}
            suffix="条"
            valueStyle={{color: (metrics?.queueDepth || 0) > 1000 ? token.colorError : token.colorPrimary}}
            prefix={<InboxOutlined />}
          />
              </ProCard>
          </ProCard>
      <div style={{ marginTop: 24 }}>
          <div style={{marginBottom: 8, display: 'flex', justifyContent: 'space-between'}}>
              <Text>队列使用率</Text>
              <Text>{metrics?.queueUsage || 0}%</Text>
        </div>
          <Progress
              percent={metrics?.queueUsage || 0}
          strokeColor={{
              '0%': token.colorSuccess,
              '50%': token.colorWarning,
              '100%': token.colorError,
          }}
        />
      </div>
      </ProCard>
  )
}

interface EventTypeChartProps extends ProCardProps {
    data: EventSystemOverviewResponse['eventTypes']
    loading: boolean
}

const EventTypeChart: React.FC<EventTypeChartProps> = ({data, loading, ...props}) => {
    // ... existing option ...
  const option = {
    tooltip: {
      trigger: 'item',
        formatter: '{b}: {c} ({d}%)'
    },
    legend: {
        bottom: '0%',
      left: 'center'
    },
    series: [
      {
        name: '事件类型',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
            borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center'
        },
        data: data || []
      }
    ]
  }

  return (
      <ProCard title="事件类型分布" loading={loading} bordered headerBordered boxShadow {...props}>
      <ReactECharts option={option} style={{ height: 300 }} />
      </ProCard>
  )
}

interface EventLatencyChartProps extends ProCardProps {
    data: EventSystemOverviewResponse['latencyDistribution']
    loading: boolean
    token: GlobalToken
}

const EventLatencyChart: React.FC<EventLatencyChartProps> = ({data, loading, token, ...props}) => {
    // ... existing option ...
  const option = {
    tooltip: {
      trigger: 'axis',
        axisPointer: {type: 'shadow'}
    },
      grid: {top: 20, bottom: 20, left: 40, right: 20, containLabel: true},
    xAxis: {
      type: 'category',
      data: data?.categories || ['<10ms', '10-50ms', '50-100ms', '100-500ms', '>500ms']
    },
    yAxis: {
      type: 'value',
        splitLine: {lineStyle: {type: 'dashed'}}
    },
    series: [
      {
        name: '事件数',
        type: 'bar',
        data: data?.values || [],
        itemStyle: {
            color: (params: any) => {
                const colors = [token.colorSuccess, '#73d13d', token.colorWarning, '#fa8c16', token.colorError]
                return colors[params.dataIndex] || token.colorPrimary
            },
            borderRadius: [4, 4, 0, 0]
        }
      }
    ]
  }

  return (
      <ProCard title="事件处理延迟分布" loading={loading} bordered headerBordered boxShadow {...props}>
      <ReactECharts option={option} style={{ height: 300 }} />
      </ProCard>
  )
}

interface MessageBusStatusProps extends ProCardProps {
    buses: EventSystemOverviewResponse['messageBuses']
    loading: boolean
    token: GlobalToken
}

const MessageBusStatus: React.FC<MessageBusStatusProps> = ({buses, loading, token, ...props}) => {
    // ... existing columns ...
  const columns = [
    {
      title: '总线类型',
      dataIndex: 'type',
      key: 'type',
        render: (type: string) => (
        <Space>
            <ApiOutlined style={{color: token.colorPrimary}}/>
            <Text strong>{type}</Text>
        </Space>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
        render: (status: string) => (
            <Tag color={status === 'connected' ? 'success' : 'error'}>
          {status === 'connected' ? '已连接' : '断开'}
        </Tag>
      )
    },
    {
      title: '吞吐量',
      dataIndex: 'throughput',
      key: 'throughput',
        render: (val: number) => `${val} msg/s`
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
        render: (usage: number) => (
            <Progress percent={usage} size="small" strokeColor={usage > 80 ? token.colorError : token.colorSuccess}/>
      )
    },
  ]

  return (
      <ProCard
          title={<Space><DatabaseOutlined style={{color: token.colorPrimary}}/><span>消息总线状态</span></Space>}
      loading={loading}
          bordered
          headerBordered
          boxShadow
          {...props}
    >
      <Table
        columns={columns}
        dataSource={buses || []}
        rowKey="type"
        size="middle"
        pagination={false}
      />
      </ProCard>
  )
}

interface EventHandlerPerformanceProps extends ProCardProps {
    handlers: EventSystemOverviewResponse['eventHandlers']
    loading: boolean
    token: GlobalToken
}

const EventHandlerPerformance: React.FC<EventHandlerPerformanceProps> = ({handlers, loading, token, ...props}) => {
    // ... existing columns ...
  const columns = [
    {
      title: '处理器',
      dataIndex: 'name',
      key: 'name',
        render: (text: string) => <Text strong>{text}</Text>
    },
    {
      title: '处理事件数',
      dataIndex: 'processed',
      key: 'processed',
        sorter: (a: any, b: any) => a.processed - b.processed,
    },
    {
      title: '成功率',
      dataIndex: 'successRate',
      key: 'successRate',
        render: (rate: number) => (
            <Progress
                percent={rate}
                size="small"
                strokeColor={rate >= 95 ? token.colorSuccess : rate >= 80 ? token.colorWarning : token.colorError}
        />
      ),
        sorter: (a: any, b: any) => a.successRate - b.successRate,
    },
    {
      title: '平均处理时间',
      dataIndex: 'avgTime',
      key: 'avgTime',
        render: (time: number | undefined) => (typeof time === 'number' ? `${time.toFixed(2)} ms` : (time ?? '-')),
        sorter: (a: any, b: any) => a.avgTime - b.avgTime,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
        render: (status: string) => (
            <Tag color={status === 'active' ? 'processing' : 'default'}>
          {status === 'active' ? '活跃' : '空闲'}
        </Tag>
      )
    },
  ]

  return (
      <ProCard
          title={<Space><ClockCircleOutlined style={{color: token.colorPrimary}}/><span>事件处理器性能</span></Space>}
      loading={loading}
          bordered
          headerBordered
          boxShadow
          {...props}
    >
      <Table
        columns={columns}
        dataSource={handlers || []}
        rowKey="name"
        size="middle"
        pagination={{pageSize: 5}}
      />
      </ProCard>
  )
}

interface EventStreamProps extends ProCardProps {
    events: EventSystemOverviewResponse['eventStream']
    loading: boolean
    token: GlobalToken
}

const EventStream: React.FC<EventStreamProps> = ({events, loading, token, ...props}) => {
  return (
      <ProCard
          title={<Space><SyncOutlined spin style={{color: token.colorPrimary}}/><span>实时事件流</span></Space>}
      loading={loading}
          bordered
          headerBordered
          boxShadow
          bodyStyle={{maxHeight: 400, overflowY: 'auto'}}
          {...props}
    >
      <Timeline mode="left">
        {(events || []).map((event, index) => (
            <Timeline.Item
            key={index}
            color={event.type === 'error' ? 'red' : event.type === 'warning' ? 'gold' : 'green'}
            label={<Text type="secondary"
                         style={{fontSize: 12}}>{new Date(event.time).toLocaleTimeString('zh-CN')}</Text>}
          >
                <Space direction="vertical" size={2}>
                    <Tag color={event.type === 'error' ? 'error' : event.type === 'warning' ? 'warning' : 'processing'}>
                {event.eventType}
              </Tag>
                    <Text>{event.message}</Text>
            </Space>
          </Timeline.Item>
        ))}
      </Timeline>
      </ProCard>
  )
}

// 主页面组件
const EventSystem = () => {
    const {token} = theme.useToken()
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
                const response = await monitorAPI.getEventSystemOverview()
                // @ts-ignore
                const data = response.data || response

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
      <PageContainer
          header={{
              title: '事件系统监控',
              ghost: true,
              extra: [
                  <Button
                      key="refresh"
                      type="primary"
            icon={<ReloadOutlined spin={refreshing} />}
            onClick={refreshAll}
            loading={refreshing}
          >
            刷新
          </Button>
              ]
          }}
      >
          <Space direction="vertical" size={48} style={{width: '100%'}}>
              {/* 事件流量监控 - 独占一行 */}
              <EventFlowCard
                  metrics={eventMetrics}
                  loading={loading}
                  token={token}
                  hoverable
              />

              {/* 事件分布图表 - 并排显示 */}
              <ProCard gutter={[24, 24]} ghost>
                  <EventTypeChart
                      colSpan={{xs: 24, md: 12}}
                      data={eventTypes}
                      loading={loading}
                      hoverable
                  />
                  <EventLatencyChart
                      colSpan={{xs: 24, md: 12}}
                      data={latencyData}
                      loading={loading}
                      token={token}
                      hoverable
                  />
              </ProCard>

              {/* 消息总线状态 - 独占一行 */}
              <MessageBusStatus
                  buses={messageBuses}
                  loading={loading}
                  token={token}
                  hoverable
              />

              {/* 事件处理器和实时流 - 并排显示 */}
              <ProCard gutter={[24, 24]} ghost>
                  <EventHandlerPerformance
                      colSpan={{xs: 24, md: 16}}
                      handlers={eventHandlers}
                      loading={loading}
                      token={token}
                      hoverable
                  />
                  <EventStream
                      colSpan={{xs: 24, md: 8}}
                      events={eventStream}
                      loading={loading}
                      token={token}
                      hoverable
                  />
              </ProCard>
          </Space>
      </PageContainer>
  )
}

export default EventSystem
