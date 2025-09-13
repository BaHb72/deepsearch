import React, { useState, useEffect } from 'react'
import { 
  Card, 
  Row, 
  Col, 
  Statistic, 
  Progress, 
  Button, 
  Space, 
  Tag,
  Alert,
  Tooltip,
  Spin,
  Badge,
  Table
} from 'antd'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  ApiOutlined
} from '@ant-design/icons'

const Dashboard = () => {
  const [loading, setLoading] = useState(false)
  const [systemInfo, setSystemInfo] = useState({
    cpu_usage: 45.2,
    memory_usage: 62.8,
    disk_usage: 35.5,
    network_in: 1024,
    network_out: 512,
    uptime: 86400,
    status: 'running'
  })

  const [dataSourceStatus, setDataSourceStatus] = useState([
    { name: 'AmazingData', status: 'online', latency: 12 },
    { name: 'CloudFlare', status: 'online', latency: 45 },
    { name: 'QMT', status: 'offline', latency: 0 },
    { name: 'AKShare', status: 'online', latency: 78 }
  ])

  useEffect(() => {
    fetchSystemInfo()
    const interval = setInterval(fetchSystemInfo, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchSystemInfo = async () => {
    // Mock data for now
    setSystemInfo(prev => ({
      ...prev,
      cpu_usage: Math.random() * 100,
      memory_usage: Math.random() * 100,
      network_in: Math.random() * 2048,
      network_out: Math.random() * 1024
    }))
  }

  const handleRefresh = () => {
    setLoading(true)
    setTimeout(() => {
      fetchSystemInfo()
      setLoading(false)
    }, 1000)
  }

  const columns = [
    {
      title: '数据源',
      dataIndex: 'name',
      key: 'name',
      render: (text) => <strong>{text}</strong>
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => (
        <Badge 
          status={status === 'online' ? 'success' : 'error'} 
          text={status === 'online' ? '在线' : '离线'}
        />
      )
    },
    {
      title: '延迟(ms)',
      dataIndex: 'latency',
      key: 'latency',
      render: (latency, record) => (
        record.status === 'online' ? (
          <Tag color={latency < 50 ? 'green' : latency < 100 ? 'orange' : 'red'}>
            {latency}ms
          </Tag>
        ) : '-'
      )
    }
  ]

  return (
    <div>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card>
            <Row justify="space-between" align="middle">
              <Col>
                <Space>
                  <DashboardOutlined style={{ fontSize: 24 }} />
                  <span style={{ fontSize: 20, fontWeight: 500 }}>系统监控仪表板</span>
                </Space>
              </Col>
              <Col>
                <Button 
                  type="primary" 
                  icon={<ReloadOutlined />} 
                  onClick={handleRefresh}
                  loading={loading}
                >
                  刷新
                </Button>
              </Col>
            </Row>
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="CPU 使用率"
              value={systemInfo.cpu_usage}
              precision={1}
              valueStyle={{ color: systemInfo.cpu_usage > 80 ? '#cf1322' : '#3f8600' }}
              prefix={<DashboardOutlined />}
              suffix="%"
            />
            <Progress 
              percent={systemInfo.cpu_usage} 
              strokeColor={systemInfo.cpu_usage > 80 ? '#cf1322' : '#52c41a'}
              showInfo={false}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="内存使用率"
              value={systemInfo.memory_usage}
              precision={1}
              valueStyle={{ color: systemInfo.memory_usage > 80 ? '#cf1322' : '#1890ff' }}
              prefix={<CloudServerOutlined />}
              suffix="%"
            />
            <Progress 
              percent={systemInfo.memory_usage} 
              strokeColor={systemInfo.memory_usage > 80 ? '#cf1322' : '#1890ff'}
              showInfo={false}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="磁盘使用率"
              value={systemInfo.disk_usage}
              precision={1}
              valueStyle={{ color: systemInfo.disk_usage > 80 ? '#cf1322' : '#722ed1' }}
              prefix={<DatabaseOutlined />}
              suffix="%"
            />
            <Progress 
              percent={systemInfo.disk_usage} 
              strokeColor={systemInfo.disk_usage > 80 ? '#cf1322' : '#722ed1'}
              showInfo={false}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="系统状态"
              value="运行中"
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
            <div style={{ marginTop: 10 }}>
              <Space>
                <Tag color="green">正常</Tag>
                <span style={{ fontSize: 12, color: '#999' }}>
                  运行时间: {Math.floor(systemInfo.uptime / 3600)}小时
                </span>
              </Space>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="网络流量" extra={<SyncOutlined spin />}>
            <Row gutter={16}>
              <Col span={12}>
                <Statistic
                  title="下载速度"
                  value={systemInfo.network_in}
                  precision={0}
                  valueStyle={{ color: '#1890ff' }}
                  prefix={<ArrowDownOutlined />}
                  suffix="KB/s"
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="上传速度"
                  value={systemInfo.network_out}
                  precision={0}
                  valueStyle={{ color: '#52c41a' }}
                  prefix={<ArrowUpOutlined />}
                  suffix="KB/s"
                />
              </Col>
            </Row>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="数据源状态" extra={<ApiOutlined />}>
            <Table 
              columns={columns}
              dataSource={dataSourceStatus.map((item, index) => ({ ...item, key: index }))}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>

        <Col span={24}>
          <Alert
            message="系统运行正常"
            description="所有核心服务运行正常，数据源连接稳定。"
            type="success"
            showIcon
            action={
              <Space>
                <Button size="small" type="text">
                  查看详情
                </Button>
              </Space>
            }
          />
        </Col>
      </Row>
    </div>
  )
}

export default Dashboard