/**
 * API 故障排查页面
 * 提供 API 日志查看、性能分析和故障诊断功能
 */

import React, { useState, useEffect, useRef } from 'react'
import {
  Card,
  Row,
  Col,
  Table,
  Button,
  Space,
  Tag,
  Input,
  Select,
  DatePicker,
  Statistic,
  Progress,
  Alert,
  Tabs,
  Badge,
  Tooltip,
  Modal,
  Descriptions,
  Timeline,
  message,
  Drawer,
  Switch,
  Divider
} from 'antd'
import {
  SearchOutlined,
  ReloadOutlined,
  ClearOutlined,
  DownloadOutlined,
  BugOutlined,
  DashboardOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  ApiOutlined,
  FilterOutlined,
  LineChartOutlined,
  FileTextOutlined
} from '@ant-design/icons'
import { Chart } from '@antv/g2'
import { getApiLogs, getApiMetrics, ApiCategory, HttpMethod } from '@/api/core'
import type { RequestLog, HealthIssue } from '@/api/core/types'
import './ApiTroubleshooting.scss'

const { RangePicker } = DatePicker
const { TabPane } = Tabs
const { Option } = Select
const { Search } = Input

interface FilterState {
  timeRange: [Date, Date] | null
  category: ApiCategory | 'all'
  method: HttpMethod | 'all'
  status: number[] | 'all'
  hasError: boolean | 'all'
  url: string
  minDuration: number | null
  maxDuration: number | null
}

const ApiTroubleshooting: React.FC = () => {
  // 状态
  const [logs, setLogs] = useState<RequestLog[]>([])
  const [filteredLogs, setFilteredLogs] = useState<RequestLog[]>([])
  const [metrics, setMetrics] = useState<any>(null)
  const [healthIssues, setHealthIssues] = useState<HealthIssue[]>([])
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [selectedLog, setSelectedLog] = useState<RequestLog | null>(null)
  const [detailVisible, setDetailVisible] = useState(false)
  
  // 过滤器状态
  const [filters, setFilters] = useState<FilterState>({
    timeRange: null,
    category: 'all',
    method: 'all',
    status: 'all',
    hasError: 'all',
    url: '',
    minDuration: null,
    maxDuration: null
  })
  
  // 图表引用
  const performanceChartRef = useRef<HTMLDivElement>(null)
  const errorRateChartRef = useRef<HTMLDivElement>(null)
  const throughputChartRef = useRef<HTMLDivElement>(null)
  
  // 自动刷新
  useEffect(() => {
    if (autoRefresh) {
      const timer = setInterval(fetchData, 5000)
      return () => clearInterval(timer)
    }
  }, [autoRefresh])
  
  // 初始加载
  useEffect(() => {
    fetchData()
  }, [])
  
  // 过滤日志
  useEffect(() => {
    applyFilters()
  }, [logs, filters])
  
  // 获取数据
  const fetchData = async () => {
    setLoading(true)
    try {
      // 获取日志
      const logsData = await getApiLogs()
      setLogs(logsData)
      
      // 获取指标
      const metricsData = await getApiMetrics()
      setMetrics(metricsData)
      
      // 提取健康问题
      if (metricsData?.health?.issues) {
        setHealthIssues(metricsData.health.issues)
      }
      
      // 更新图表
      updateCharts(metricsData)
    } catch (error) {
      message.error('获取数据失败')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }
  
  // 应用过滤器
  const applyFilters = () => {
    let filtered = [...logs]
    
    // 时间范围过滤
    if (filters.timeRange) {
      const [start, end] = filters.timeRange
      filtered = filtered.filter(log => {
        const logTime = new Date(log.timestamp)
        return logTime >= start && logTime <= end
      })
    }
    
    // 分类过滤
    if (filters.category !== 'all') {
      filtered = filtered.filter(log => log.category === filters.category)
    }
    
    // 方法过滤
    if (filters.method !== 'all') {
      filtered = filtered.filter(log => log.method === filters.method)
    }
    
    // 状态码过滤
    if (filters.status !== 'all') {
      filtered = filtered.filter(log => 
        log.status && filters.status.includes(Math.floor(log.status / 100))
      )
    }
    
    // 错误过滤
    if (filters.hasError !== 'all') {
      filtered = filtered.filter(log => (log.error !== undefined) === filters.hasError)
    }
    
    // URL 过滤
    if (filters.url) {
      filtered = filtered.filter(log => 
        log.url.toLowerCase().includes(filters.url.toLowerCase())
      )
    }
    
    // 响应时间过滤
    if (filters.minDuration !== null) {
      filtered = filtered.filter(log => 
        log.duration && log.duration >= filters.minDuration!
      )
    }
    if (filters.maxDuration !== null) {
      filtered = filtered.filter(log => 
        log.duration && log.duration <= filters.maxDuration!
      )
    }
    
    setFilteredLogs(filtered)
  }
  
  // 更新图表
  const updateCharts = (metricsData: any) => {
    if (!metricsData) return
    
    // 性能图表
    if (performanceChartRef.current) {
      renderPerformanceChart(metricsData.global)
    }
    
    // 错误率图表
    if (errorRateChartRef.current) {
      renderErrorRateChart(metricsData.categories)
    }
    
    // 吞吐量图表
    if (throughputChartRef.current) {
      renderThroughputChart(metricsData.endpoints)
    }
  }
  
  // 渲染性能图表
  const renderPerformanceChart = (data: any) => {
    // TODO: 实现图表渲染
  }
  
  // 渲染错误率图表
  const renderErrorRateChart = (data: any) => {
    // TODO: 实现图表渲染
  }
  
  // 渲染吞吐量图表
  const renderThroughputChart = (data: any) => {
    // TODO: 实现图表渲染
  }
  
  // 导出日志
  const exportLogs = () => {
    const dataStr = JSON.stringify(filteredLogs, null, 2)
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr)
    
    const exportFileDefaultName = `api_logs_${Date.now()}.json`
    
    const linkElement = document.createElement('a')
    linkElement.setAttribute('href', dataUri)
    linkElement.setAttribute('download', exportFileDefaultName)
    linkElement.click()
  }
  
  // 清除过滤器
  const clearFilters = () => {
    setFilters({
      timeRange: null,
      category: 'all',
      method: 'all',
      status: 'all',
      hasError: 'all',
      url: '',
      minDuration: null,
      maxDuration: null
    })
  }
  
  // 显示日志详情
  const showLogDetail = (log: RequestLog) => {
    setSelectedLog(log)
    setDetailVisible(true)
  }
  
  // 获取状态标签
  const getStatusTag = (status?: number) => {
    if (!status) return <Tag>N/A</Tag>
    
    if (status >= 200 && status < 300) {
      return <Tag color="success">{status}</Tag>
    } else if (status >= 300 && status < 400) {
      return <Tag color="warning">{status}</Tag>
    } else if (status >= 400 && status < 500) {
      return <Tag color="error">{status}</Tag>
    } else {
      return <Tag color="error">{status}</Tag>
    }
  }
  
  // 获取方法标签
  const getMethodTag = (method: HttpMethod) => {
    const colors: Record<HttpMethod, string> = {
      [HttpMethod.GET]: 'blue',
      [HttpMethod.POST]: 'green',
      [HttpMethod.PUT]: 'orange',
      [HttpMethod.DELETE]: 'red',
      [HttpMethod.PATCH]: 'purple'
    }
    return <Tag color={colors[method]}>{method}</Tag>
  }
  
  // 获取健康状态
  const getHealthStatus = () => {
    if (!metrics?.health?.status) return 'unknown'
    return metrics.health.status
  }
  
  // 获取健康状态颜色
  const getHealthColor = () => {
    const status = getHealthStatus()
    switch (status) {
      case 'healthy':
        return '#52c41a'
      case 'degraded':
        return '#faad14'
      case 'unhealthy':
        return '#f5222d'
      default:
        return '#d9d9d9'
    }
  }
  
  // 表格列定义
  const columns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 150,
      render: (timestamp: number) => new Date(timestamp).toLocaleString(),
      sorter: (a: RequestLog, b: RequestLog) => a.timestamp - b.timestamp
    },
    {
      title: '方法',
      dataIndex: 'method',
      key: 'method',
      width: 80,
      render: (method: HttpMethod) => getMethodTag(method),
      filters: Object.values(HttpMethod).map(m => ({ text: m, value: m })),
      onFilter: (value: any, record: RequestLog) => record.method === value
    },
    {
      title: 'URL',
      dataIndex: 'url',
      key: 'url',
      ellipsis: true,
      render: (url: string) => (
        <Tooltip title={url}>
          <span>{url}</span>
        </Tooltip>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status?: number) => getStatusTag(status),
      sorter: (a: RequestLog, b: RequestLog) => (a.status || 0) - (b.status || 0)
    },
    {
      title: '耗时',
      dataIndex: 'duration',
      key: 'duration',
      width: 100,
      render: (duration?: number) => {
        if (!duration) return '-'
        if (duration < 1000) {
          return <span style={{ color: '#52c41a' }}>{duration}ms</span>
        } else if (duration < 3000) {
          return <span style={{ color: '#faad14' }}>{duration}ms</span>
        } else {
          return <span style={{ color: '#f5222d' }}>{duration}ms</span>
        }
      },
      sorter: (a: RequestLog, b: RequestLog) => (a.duration || 0) - (b.duration || 0)
    },
    {
      title: '错误',
      dataIndex: 'error',
      key: 'error',
      width: 100,
      render: (error?: any) => {
        if (!error) {
          return <Tag icon={<CheckCircleOutlined />} color="success">成功</Tag>
        } else {
          return <Tag icon={<CloseCircleOutlined />} color="error">失败</Tag>
        }
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: RequestLog) => (
        <Button type="link" size="small" onClick={() => showLogDetail(record)}>
          详情
        </Button>
      )
    }
  ]
  
  return (
    <div className="api-troubleshooting">
      {/* 页面标题 */}
      <div className="page-header">
        <h2><BugOutlined /> API 故障排查</h2>
        <Space>
          <Switch
            checked={autoRefresh}
            onChange={setAutoRefresh}
            checkedChildren="自动刷新"
            unCheckedChildren="手动"
          />
          <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>
      
      {/* 健康状态概览 */}
      <Card className="health-overview" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic
              title="健康状态"
              value={getHealthStatus()}
              valueStyle={{ color: getHealthColor() }}
              prefix={<ApiOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="总请求数"
              value={metrics?.global?.requestCount || 0}
              suffix="次"
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="错误率"
              value={(metrics?.global?.errorRate || 0) * 100}
              precision={2}
              suffix="%"
              valueStyle={{ 
                color: (metrics?.global?.errorRate || 0) > 0.1 ? '#f5222d' : '#52c41a' 
              }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="平均响应时间"
              value={metrics?.global?.avgDuration || 0}
              precision={0}
              suffix="ms"
              valueStyle={{ 
                color: (metrics?.global?.avgDuration || 0) > 3000 ? '#f5222d' : '#52c41a' 
              }}
            />
          </Col>
        </Row>
      </Card>
      
      {/* 健康问题提示 */}
      {healthIssues.length > 0 && (
        <Alert
          message="检测到健康问题"
          description={
            <div>
              {healthIssues.map((issue, index) => (
                <div key={index} style={{ marginBottom: 8 }}>
                  <Badge 
                    status={
                      issue.severity === 'critical' ? 'error' :
                      issue.severity === 'high' ? 'warning' :
                      'default'
                    }
                    text={`${issue.message} - ${issue.suggestedAction}`}
                  />
                </div>
              ))}
            </div>
          }
          type="warning"
          showIcon
          closable
          style={{ marginBottom: 16 }}
        />
      )}
      
      {/* 主要内容区 */}
      <Tabs defaultActiveKey="logs">
        <TabPane tab="日志查询" key="logs">
          {/* 过滤器 */}
          <Card title="过滤条件" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              <Col span={6}>
                <label>时间范围</label>
                <RangePicker
                  showTime
                  style={{ width: '100%' }}
                  onChange={(dates) => {
                    if (dates) {
                      setFilters({ ...filters, timeRange: [dates[0]!.toDate(), dates[1]!.toDate()] })
                    } else {
                      setFilters({ ...filters, timeRange: null })
                    }
                  }}
                />
              </Col>
              <Col span={4}>
                <label>分类</label>
                <Select
                  style={{ width: '100%' }}
                  value={filters.category}
                  onChange={(value) => setFilters({ ...filters, category: value })}
                >
                  <Option value="all">全部</Option>
                  {Object.values(ApiCategory).map(cat => (
                    <Option key={cat} value={cat}>{cat}</Option>
                  ))}
                </Select>
              </Col>
              <Col span={4}>
                <label>方法</label>
                <Select
                  style={{ width: '100%' }}
                  value={filters.method}
                  onChange={(value) => setFilters({ ...filters, method: value })}
                >
                  <Option value="all">全部</Option>
                  {Object.values(HttpMethod).map(method => (
                    <Option key={method} value={method}>{method}</Option>
                  ))}
                </Select>
              </Col>
              <Col span={6}>
                <label>URL</label>
                <Search
                  placeholder="搜索 URL"
                  value={filters.url}
                  onChange={(e) => setFilters({ ...filters, url: e.target.value })}
                />
              </Col>
              <Col span={4}>
                <label>&nbsp;</label>
                <div>
                  <Button onClick={clearFilters} style={{ marginRight: 8 }}>
                    清除
                  </Button>
                  <Button type="primary" icon={<DownloadOutlined />} onClick={exportLogs}>
                    导出
                  </Button>
                </div>
              </Col>
            </Row>
          </Card>
          
          {/* 日志表格 */}
          <Card>
            <Table
              columns={columns}
              dataSource={filteredLogs}
              rowKey="id"
              loading={loading}
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                showQuickJumper: true,
                showTotal: (total) => `共 ${total} 条记录`
              }}
              scroll={{ x: 1200 }}
            />
          </Card>
        </TabPane>
        
        <TabPane tab="性能分析" key="performance">
          <Row gutter={16}>
            <Col span={24}>
              <Card title="响应时间分布">
                <div ref={performanceChartRef} style={{ height: 300 }} />
              </Card>
            </Col>
            <Col span={12} style={{ marginTop: 16 }}>
              <Card title="错误率趋势">
                <div ref={errorRateChartRef} style={{ height: 300 }} />
              </Card>
            </Col>
            <Col span={12} style={{ marginTop: 16 }}>
              <Card title="吞吐量">
                <div ref={throughputChartRef} style={{ height: 300 }} />
              </Card>
            </Col>
          </Row>
        </TabPane>
        
        <TabPane tab="端点统计" key="endpoints">
          <Card>
            <Table
              dataSource={Object.entries(metrics?.endpoints || {}).map(([key, value]: any) => ({
                key,
                endpoint: key,
                ...value
              }))}
              columns={[
                { title: '端点', dataIndex: 'endpoint', key: 'endpoint' },
                { title: '请求数', dataIndex: 'requestCount', key: 'requestCount' },
                { title: '成功数', dataIndex: 'successCount', key: 'successCount' },
                { title: '错误数', dataIndex: 'errorCount', key: 'errorCount' },
                { title: '平均耗时', dataIndex: 'avgDuration', key: 'avgDuration' },
                { title: '错误率', dataIndex: 'errorRate', key: 'errorRate' }
              ]}
              pagination={false}
            />
          </Card>
        </TabPane>
      </Tabs>
      
      {/* 日志详情抽屉 */}
      <Drawer
        title="日志详情"
        placement="right"
        width={600}
        visible={detailVisible}
        onClose={() => setDetailVisible(false)}
      >
        {selectedLog && (
          <div>
            <Descriptions bordered column={1}>
              <Descriptions.Item label="请求 ID">{selectedLog.id}</Descriptions.Item>
              <Descriptions.Item label="时间">
                {new Date(selectedLog.timestamp).toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="方法">{selectedLog.method}</Descriptions.Item>
              <Descriptions.Item label="URL">{selectedLog.url}</Descriptions.Item>
              <Descriptions.Item label="完整 URL">{selectedLog.fullUrl}</Descriptions.Item>
              <Descriptions.Item label="状态">{selectedLog.status || 'N/A'}</Descriptions.Item>
              <Descriptions.Item label="耗时">{selectedLog.duration}ms</Descriptions.Item>
              <Descriptions.Item label="分类">{selectedLog.category}</Descriptions.Item>
            </Descriptions>
            
            {selectedLog.params && (
              <>
                <Divider>请求参数</Divider>
                <pre>{JSON.stringify(selectedLog.params, null, 2)}</pre>
              </>
            )}
            
            {selectedLog.data && (
              <>
                <Divider>请求数据</Divider>
                <pre>{JSON.stringify(selectedLog.data, null, 2)}</pre>
              </>
            )}
            
            {selectedLog.responseData && (
              <>
                <Divider>响应数据</Divider>
                <pre>{JSON.stringify(selectedLog.responseData, null, 2)}</pre>
              </>
            )}
            
            {selectedLog.error && (
              <>
                <Divider>错误信息</Divider>
                <Alert type="error" message={selectedLog.errorMessage} />
                {selectedLog.errorStack && (
                  <pre style={{ marginTop: 8 }}>{selectedLog.errorStack}</pre>
                )}
              </>
            )}
            
            {selectedLog.trace && selectedLog.trace.length > 0 && (
              <>
                <Divider>追踪信息</Divider>
                <Timeline>
                  {selectedLog.trace.map((item, index) => (
                    <Timeline.Item key={index}>{item}</Timeline.Item>
                  ))}
                </Timeline>
              </>
            )}
          </div>
        )}
      </Drawer>
    </div>
  )
}

export default ApiTroubleshooting