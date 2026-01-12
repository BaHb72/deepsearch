import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Card, Row, Col, Button, Table, Alert, Timeline, Tag, message, Modal, Spin, Space, Typography } from 'antd'
import {
  ReloadOutlined,
  LinkOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  BarChartOutlined,
  DatabaseOutlined
} from '@ant-design/icons'
import * as echarts from 'echarts'
import dayjs from 'dayjs'
import { useSystemStore } from '@/stores/system'
import { useWebSocket } from '@/hooks/useWebSocket'
import StatusCard from '@/components/StatusCard'
import DataSourceCard from '@/components/DataSourceCard'
import CacheStatusCard from '@/components/CacheStatusCard'
import SystemAlerts from '@/components/SystemAlerts'
import { getDashboard, getRealtimeMetrics } from '@/services/monitor'
import { getAllComponents, startComponent, stopComponent } from '@/services/system'
import { throttle } from '@/utils/performance'
import type { ComponentStatus, DashboardData, SystemAlert } from '@/types'
import './index.scss'

const { Title, Text } = Typography

const Dashboard: React.FC = () => {
  // 状态管理
  const systemStore = useSystemStore()
  const [dashboardData, setDashboardData] = useState<DashboardData>({
    current: null,
    trends: null,
    alerts: []
  })
  const [chartPeriod, setChartPeriod] = useState('1h')
  const [loading, setLoading] = useState(false)
  const [componentLoading, setComponentLoading] = useState(false)
  const [lastUpdateTime, setLastUpdateTime] = useState<string>('')
  const [hasAlerts, setHasAlerts] = useState(false)
  const [components, setComponents] = useState<ComponentStatus[]>([])

  // 图表实例引用
  const trendChartRef = useRef<HTMLDivElement>(null)
  const pieChartRef = useRef<HTMLDivElement>(null)
  const trendChartInstance = useRef<echarts.ECharts | null>(null)
  const pieChartInstance = useRef<echarts.ECharts | null>(null)
  const resizeObserver = useRef<ResizeObserver | null>(null)

  // WebSocket连接
  const { connected: wsConnected, subscribe } = useWebSocket({
    url: process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws',
    onMessage: (data) => {
      if (data.type === 'monitor_update') {
        setDashboardData(data.data)
        updateCharts()
      }
    }
  })

  // 初始化图表
  const initCharts = useCallback(() => {
    // 趋势图
    if (trendChartRef.current && !trendChartInstance.current) {
      trendChartInstance.current = echarts.init(trendChartRef.current)

      // ResizeObserver监听
      if (window.ResizeObserver && !resizeObserver.current) {
        resizeObserver.current = new ResizeObserver(() => {
          trendChartInstance.current?.resize()
          pieChartInstance.current?.resize()
        })
        resizeObserver.current.observe(trendChartRef.current)
      }

      trendChartInstance.current.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' }
        },
        legend: {
          data: ['处理数', '成功率']
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: []
        },
        yAxis: [
          {
            type: 'value',
            name: '处理数',
            position: 'left'
          },
          {
            type: 'value',
            name: '成功率 (%)',
            position: 'right',
            max: 100,
            min: 0
          }
        ],
        series: [
          {
            name: '处理数',
            type: 'line',
            data: [],
            smooth: true,
            itemStyle: { color: '#1890ff' }
          },
          {
            name: '成功率',
            type: 'line',
            yAxisIndex: 1,
            data: [],
            smooth: true,
            itemStyle: { color: '#52c41a' }
          }
        ]
      })
    }

    // 饼图
    if (pieChartRef.current && !pieChartInstance.current) {
      pieChartInstance.current = echarts.init(pieChartRef.current)
      pieChartInstance.current.setOption({
        tooltip: {
          trigger: 'item'
        },
        legend: {
          orient: 'vertical',
          left: 'left'
        },
        series: [
          {
            type: 'pie',
            radius: '50%',
            data: [],
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)'
              }
            }
          }
        ]
      })
    }
  }, [])

  // 更新图表
  const updateCharts = async () => {
    try {
      const metrics = await getRealtimeMetrics()

      if (trendChartInstance.current && !trendChartInstance.current.isDisposed() && metrics.series) {
        const timestamps = metrics.timestamps?.map(t => dayjs(t).format('HH:mm:ss')) || []
        let totalCounts: number[] = []
        let avgSuccessRates: number[] = []

        Object.values(metrics.series).forEach((data: any) => {
          if (data.count) {
            totalCounts = data.count
            avgSuccessRates = data.success_rate
          }
        })

        trendChartInstance.current.setOption({
          xAxis: { data: timestamps },
          series: [
            { name: '处理数', data: totalCounts },
            { name: '成功率', data: avgSuccessRates }
          ]
        })
      }

      if (pieChartInstance.current && !pieChartInstance.current.isDisposed() && metrics.series) {
        const pieData = Object.entries(metrics.series).map(([name, data]: [string, any]) => ({
          name,
          value: data.count?.reduce((sum: number, val: number) => sum + val, 0) || 0
        }))

        pieChartInstance.current.setOption({
          series: [{ data: pieData }]
        })
      }
    } catch (error) {
      console.error('更新图表失败:', error)
    }
  }

  // 获取初始数据
  const fetchInitialData = async () => {
    setLoading(true)
    try {
      const data = await getDashboard(chartPeriod)
      setDashboardData(data)
      setHasAlerts(data.alerts && data.alerts.length > 0)
      setLastUpdateTime(new Date().toISOString())
      await updateCharts()
      await refreshComponents()
    } catch (error) {
      message.error('获取仪表板数据失败')
    } finally {
      setLoading(false)
    }
  }

  // 刷新组件列表
  const refreshComponents = async () => {
    setComponentLoading(true)
    try {
      const res = await getAllComponents()
      const componentList = Object.entries(res.components || {})
        .filter(([name]) => name !== 'webui')
        .map(([name, info]: [string, any]) => ({
          name,
          ...info
        }))
      setComponents(componentList)
      systemStore.updateComponents(componentList)
    } catch (error) {
      console.error('获取组件列表失败:', error)
      setComponents([])
      systemStore.updateComponents([])
    } finally {
      setComponentLoading(false)
    }
  }

  // 刷新全部数据（节流）
  const refreshAll = useCallback(
    throttle(async () => {
      setLoading(true)
      try {
        await Promise.all([
          fetchInitialData(),
          refreshComponents()
        ])
        setLastUpdateTime(new Date().toISOString())
        message.success('数据已刷新')
      } catch (error) {
        console.error('刷新失败:', error)
        message.error('刷新失败')
      } finally {
        setLoading(false)
      }
    }, 2000),
    [chartPeriod]
  )

  // 切换图表时间段
  const changeChartPeriod = async (period: string) => {
    setChartPeriod(period)
    try {
      const data = await getDashboard(period)
      setDashboardData(data)
      await updateCharts()
    } catch (error) {
      message.error('更新图表数据失败')
    }
  }

  // 启动组件
  const handleStartComponent = async (component: ComponentStatus) => {
    Modal.confirm({
      title: '启动组件',
      content: `确定要启动组件 "${component.display_name}" 吗？`,
      onOk: async () => {
        const hide = message.loading(`正在启动 ${component.display_name}...`, 0)
        try {
          await startComponent(component.name)
          message.success(`组件 "${component.display_name}" 启动成功`)
          await refreshComponents()
        } catch (error: any) {
          message.error(error.response?.data?.detail || '启动组件失败')
        } finally {
          hide()
        }
      }
    })
  }

  // 停止组件
  const handleStopComponent = async (component: ComponentStatus) => {
    Modal.confirm({
      title: '停止组件',
      content: `确定要停止组件 "${component.display_name}" 吗？`,
      type: 'warning',
      onOk: async () => {
        const hide = message.loading(`正在停止 ${component.display_name}...`, 0)
        try {
          await stopComponent(component.name)
          message.success(`组件 "${component.display_name}" 停止成功`)
          await refreshComponents()
        } catch (error: any) {
          message.error(error.response?.data?.detail || '停止组件失败')
        } finally {
          hide()
        }
      }
    })
  }

  // 工具函数
  const getHealthScore = () => {
    const status = dashboardData.current?.health_status
    const scoreMap: Record<string, number> = {
      'healthy': 100,
      'good': 100,
      'degraded': 75,
      'warning': 50,
      'unhealthy': 25,
      'error': 0
    }
    return scoreMap[status || ''] || 0
  }

  const getComponentStatusType = (status: string) => {
    const types: Record<string, string> = {
      'running': 'success',
      'stopped': 'default',
      'initialized': 'warning',
      'error': 'error',
      'starting': 'processing',
      'stopping': 'processing'
    }
    return types[status] || 'default'
  }

  const getComponentStatusText = (status: string) => {
    const texts: Record<string, string> = {
      'running': '运行中',
      'stopped': '已停止',
      'initialized': '已初始化',
      'uninitialized': '未初始化',
      'error': '错误',
      'starting': '正在启动',
      'stopping': '正在停止'
    }
    return texts[status] || status
  }

  // 组件表格列配置
  const columns = [
    {
      title: '组件名称',
      dataIndex: 'display_name',
      key: 'display_name',
      width: 180
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type: string) => (
        <Tag color={type === 'infrastructure' ? 'blue' : 'green'}>
          {type === 'infrastructure' ? '基础设施' : '业务组件'}
        </Tag>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 180,
      render: (status: string, record: ComponentStatus) => (
        <Space>
          <Tag color={getComponentStatusType(status)}>
            {getComponentStatusText(status)}
          </Tag>
          {record.error_message && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {record.error_message}
            </Text>
          )}
        </Space>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      fixed: 'right' as const,
      render: (_: any, record: ComponentStatus) => (
        record.status !== 'running' ? (
          <Button
            type="primary"
            size="small"
            icon={<PlayCircleOutlined />}
            onClick={() => handleStartComponent(record)}
            disabled={record.dependencies?.some(dep =>
              components.find(c => c.name === dep)?.status !== 'running'
            )}
          >
            启动
          </Button>
        ) : (
          <Button
            danger
            size="small"
            icon={<PauseCircleOutlined />}
            onClick={() => handleStopComponent(record)}
            disabled={components.some(c =>
              c.dependencies?.includes(record.name) && c.status === 'running'
            )}
          >
            停止
          </Button>
        )
      )
    }
  ]

  // 生命周期
  useEffect(() => {
    fetchInitialData()

    // 延迟初始化图表
    const timer = setTimeout(() => {
      initCharts()
    }, 300)

    // 定时刷新
    const refreshTimer = setInterval(async () => {
      try {
        await refreshComponents()
        await systemStore.fetchStatus()
      } catch (error) {
        console.error('定时刷新失败:', error)
      }
    }, 30000)

    return () => {
      clearTimeout(timer)
      clearInterval(refreshTimer)
      resizeObserver.current?.disconnect()
      trendChartInstance.current?.dispose()
      pieChartInstance.current?.dispose()
    }
  }, [])

  // 监听WebSocket连接
  useEffect(() => {
    if (wsConnected) {
      subscribe(['monitor:update'])
    }
  }, [wsConnected, subscribe])

  return (
    <div className="dashboard">
      {/* 页面标题 */}
      <div className="page-header">
        <Title level={2}>监控仪表板</Title>
        <div className="header-actions">
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={refreshAll}
          >
            刷新全部
          </Button>
          {lastUpdateTime && (
            <Text type="secondary" className="update-time">
              最后更新: {dayjs(lastUpdateTime).format('HH:mm:ss')}
            </Text>
          )}
        </div>
      </div>

      {/* 系统告警 */}
      {hasAlerts && <SystemAlerts alerts={dashboardData.alerts} />}

      {/* 状态卡片 */}
      <Row gutter={[24, 24]} className="status-cards">
        <Col xs={24} sm={12} md={6}>
          <StatusCard
            title="事件处理"
            value={dashboardData.current?.total_events || 0}
            unit="个"
            subtitle="累计处理"
            icon={<BarChartOutlined />}
            type="primary"
            progress={Math.min(100, ((dashboardData.current?.total_events || 0) / 10000) * 100)}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatusCard
            title="系统健康"
            value={getHealthScore()}
            unit="%"
            subtitle="所有组件运行状态"
            icon={<CheckCircleOutlined />}
            type={getHealthScore() >= 90 ? 'success' : getHealthScore() >= 70 ? 'warning' : 'danger'}
            progress={getHealthScore()}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatusCard
            title="事件队列"
            value={dashboardData.current?.queue_size || 0}
            unit="个"
            subtitle="当前积压"
            icon={<DatabaseOutlined />}
            type="warning"
            progress={Math.min(100, ((dashboardData.current?.queue_size || 0) / 1000) * 100)}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatusCard
            title="活跃告警"
            value={dashboardData.current?.active_alerts || 0}
            unit="个"
            subtitle="需要关注的问题"
            icon={<WarningOutlined />}
            type={dashboardData.current?.active_alerts ? 'danger' : 'success'}
            progress={Math.min(100, ((dashboardData.current?.active_alerts || 0) / 10) * 100)}
            pulse={dashboardData.current?.active_alerts > 0}
          />
        </Col>
      </Row>

      {/* 数据源和缓存状态 */}
      <Row gutter={[24, 24]} style={{ marginTop: 24 }}>
        <Col xs={24} md={12}>
          <DataSourceCard />
        </Col>
        <Col xs={24} md={12}>
          <CacheStatusCard />
        </Col>
      </Row>

      {/* 系统组件管理 */}
      <Card
        title="系统组件管理"
        className="components-card"
        extra={
          <Button
            size="small"
            shape="circle"
            icon={<ReloadOutlined />}
            onClick={refreshComponents}
          />
        }
      >
        <Spin spinning={componentLoading}>
          <Table
            dataSource={components}
            columns={columns}
            rowKey="name"
            pagination={false}
            scroll={{ x: 'max-content' }}
          />
        </Spin>
        <Alert
          message="温馨提示：基础设施组件已自动启动，业务组件需要手动启动。停止组件时，依赖该组件的其他组件也会被停止。"
          type="info"
          showIcon
          style={{ marginTop: 20 }}
        />
      </Card>

      {/* 图表区域 */}
      <Row gutter={[20, 20]} className="chart-area">
        <Col xs={24} md={16}>
          <Card title="实时趋势">
            <Space style={{ marginBottom: 16 }}>
              {['5m', '1h', '24h'].map(period => (
                <Button
                  key={period}
                  type={chartPeriod === period ? 'primary' : 'default'}
                  onClick={() => changeChartPeriod(period)}
                >
                  {period === '5m' ? '5分钟' : period === '1h' ? '1小时' : '24小时'}
                </Button>
              ))}
            </Space>
            <div ref={trendChartRef} className="chart-container" />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="事件类型分布">
            <div ref={pieChartRef} className="chart-container" />
          </Card>
        </Col>
      </Row>

      {/* 告警列表 */}
      {dashboardData.alerts?.length > 0 && (
        <Card title="系统告警" className="alerts-card">
          <Timeline>
            {dashboardData.alerts.map((alert: SystemAlert, index: number) => (
              <Timeline.Item
                key={index}
                color={alert.level === 'error' ? 'red' : alert.level === 'warning' ? 'orange' : 'blue'}
              >
                <Alert
                  message={alert.message}
                  type={alert.level as 'error' | 'warning' | 'info'}
                  showIcon
                  style={{ marginBottom: 8 }}
                />
                <Text type="secondary">{dayjs(alert.timestamp).format('HH:mm:ss')}</Text>
              </Timeline.Item>
            ))}
          </Timeline>
        </Card>
      )}

      {/* WebSocket 连接状态 */}
      <div className="ws-status">
        <Tag color={wsConnected ? 'success' : 'default'} icon={<LinkOutlined />}>
          {wsConnected ? '实时连接' : '连接断开'}
        </Tag>
      </div>
    </div>
  )
}

export default Dashboard
