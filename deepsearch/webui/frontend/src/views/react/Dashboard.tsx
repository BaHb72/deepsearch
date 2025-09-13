import React, { useState, useEffect } from 'react'
import { 
  Row, 
  Col, 
  Card, 
  Statistic, 
  Progress, 
  Space, 
  Tag, 
  Button,
  Typography,
  Skeleton,
  Avatar,
  List,
  Badge,
  Tooltip,
  Divider,
  Alert,
  Timeline,
  Segmented
} from 'antd'
import {
  ProCard,
  ProTable,
  ProList,
  StatisticCard,
  CheckCard
} from '@ant-design/pro-components'
import { Line, Column, Area, Pie } from '@ant-design/charts'
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  ClockCircleOutlined,
  RocketOutlined,
  FireOutlined,
  ThunderboltOutlined,
  DashboardOutlined,
  FundOutlined,
  RiseOutlined,
  FallOutlined,
  StockOutlined
} from '@ant-design/icons'
import { useSystemStore } from '@/stores/systemStore'
import { useMarketStore } from '@/stores/marketStore'
import './Dashboard.scss'

const { Title, Text, Paragraph } = Typography
const { Ribbon } = Badge

// 模拟数据
const mockMarketData = [
  { time: '09:30', value: 3420, volume: 1200 },
  { time: '10:00', value: 3435, volume: 1500 },
  { time: '10:30', value: 3450, volume: 1800 },
  { time: '11:00', value: 3445, volume: 1600 },
  { time: '11:30', value: 3460, volume: 2000 },
  { time: '13:00', value: 3455, volume: 1900 },
  { time: '13:30', value: 3470, volume: 2200 },
  { time: '14:00', value: 3465, volume: 2100 },
  { time: '14:30', value: 3480, volume: 2400 },
  { time: '15:00', value: 3475, volume: 2300 },
]

const sectorData = [
  { type: '科技', value: 27, change: 2.5 },
  { type: '金融', value: 25, change: -1.2 },
  { type: '消费', value: 18, change: 0.8 },
  { type: '医药', value: 15, change: 3.2 },
  { type: '制造', value: 10, change: -0.5 },
  { type: '其他', value: 5, change: 1.1 },
]

const Dashboard = () => {
  const systemStore = useSystemStore()
  const marketStore = useMarketStore()
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState('overview')
  const [selectedTimeRange, setSelectedTimeRange] = useState('1d')

  useEffect(() => {
    // 模拟数据加载
    setTimeout(() => {
      setLoading(false)
    }, 1000)

    // 获取系统状态
    systemStore.fetchStatus().catch(console.error)
  }, [])

  // 图表配置
  const lineConfig = {
    data: mockMarketData,
    xField: 'time',
    yField: 'value',
    smooth: true,
    animation: {
      appear: {
        animation: 'path-in',
        duration: 1000,
      },
    },
    point: {
      size: 3,
      shape: 'circle',
      style: {
        fill: 'white',
        stroke: '#1890ff',
        lineWidth: 2,
      },
    },
    tooltip: {
      showMarkers: true,
    },
    state: {
      active: {
        style: {
          shadowBlur: 4,
          stroke: '#000',
          fill: 'red',
        },
      },
    },
    interactions: [
      {
        type: 'marker-active',
      },
    ],
  }

  const columnConfig = {
    data: mockMarketData,
    xField: 'time',
    yField: 'volume',
    label: {
      position: 'middle',
      style: {
        fill: '#FFFFFF',
        opacity: 0.6,
      },
    },
    xAxis: {
      label: {
        autoHide: true,
        autoRotate: false,
      },
    },
    meta: {
      volume: {
        alias: '成交量',
      },
    },
  }

  const pieConfig = {
    data: sectorData,
    angleField: 'value',
    colorField: 'type',
    radius: 0.8,
    label: {
      type: 'spider',
      labelHeight: 28,
      content: '{name}\n{percentage}',
    },
    interactions: [
      {
        type: 'element-selected',
      },
      {
        type: 'element-active',
      },
    ],
  }

  // ProTable 列配置
  const columns = [
    {
      title: '股票代码',
      dataIndex: 'code',
      key: 'code',
      render: (text) => <a>{text}</a>,
      width: 100,
    },
    {
      title: '股票名称',
      dataIndex: 'name',
      key: 'name',
      width: 120,
    },
    {
      title: '最新价',
      dataIndex: 'price',
      key: 'price',
      align: 'right',
      render: (val) => <Text strong>¥{val}</Text>,
      sorter: (a, b) => a.price - b.price,
    },
    {
      title: '涨跌幅',
      dataIndex: 'change',
      key: 'change',
      align: 'right',
      render: (val) => (
        <Tag color={val > 0 ? 'red' : 'green'}>
          {val > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
          {Math.abs(val)}%
        </Tag>
      ),
      sorter: (a, b) => a.change - b.change,
    },
    {
      title: '成交量',
      dataIndex: 'volume',
      key: 'volume',
      align: 'right',
      render: (val) => `${(val / 10000).toFixed(2)}万手`,
    },
    {
      title: '成交额',
      dataIndex: 'amount',
      key: 'amount',
      align: 'right',
      render: (val) => `¥${(val / 100000000).toFixed(2)}亿`,
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space size="middle">
          <a>交易</a>
          <a>详情</a>
          <a>加自选</a>
        </Space>
      ),
    },
  ]

  const mockStockData = [
    { key: '1', code: '000001', name: '平安银行', price: 12.56, change: 2.34, volume: 125634, amount: 1580000000 },
    { key: '2', code: '000002', name: '万科A', price: 15.89, change: -1.23, volume: 89234, amount: 1420000000 },
    { key: '3', code: '000858', name: '五粮液', price: 168.90, change: 3.45, volume: 45678, amount: 7720000000 },
    { key: '4', code: '002415', name: '海康威视', price: 35.67, change: -0.89, volume: 67890, amount: 2420000000 },
    { key: '5', code: '300750', name: '宁德时代', price: 189.50, change: 4.56, volume: 34567, amount: 6550000000 },
  ]

  if (loading) {
    return (
      <div style={{ padding: 24 }}>
        <Skeleton active paragraph={{ rows: 10 }} />
      </div>
    )
  }

  return (
    <div className="dashboard-container">
      {/* 页面标题区域 */}
      <div className="dashboard-header">
        <Title level={2}>
          <DashboardOutlined /> 监控仪表板
        </Title>
        <Space>
          <Segmented
            value={viewMode}
            onChange={setViewMode}
            options={[
              { label: '总览', value: 'overview', icon: <DashboardOutlined /> },
              { label: '市场', value: 'market', icon: <FundOutlined /> },
              { label: '交易', value: 'trading', icon: <StockOutlined /> },
            ]}
          />
          <Button type="primary" icon={<SyncOutlined />} onClick={() => window.location.reload()}>
            刷新数据
          </Button>
        </Space>
      </div>

      {/* 系统状态提醒 */}
      <Alert
        message="系统运行正常"
        description="所有服务运行正常，数据同步完成，最后更新时间：2025-01-09 15:30:00"
        type="success"
        showIcon
        icon={<CheckCircleOutlined />}
        closable
        style={{ marginBottom: 16 }}
      />

      {/* 统计卡片 - 使用 ProComponents */}
      <ProCard
        title="核心指标"
        extra={
          <Segmented
            value={selectedTimeRange}
            onChange={setSelectedTimeRange}
            options={[
              { label: '1天', value: '1d' },
              { label: '1周', value: '1w' },
              { label: '1月', value: '1m' },
              { label: '1年', value: '1y' },
            ]}
          />
        }
        ghost
        gutter={16}
        style={{ marginBottom: 16 }}
      >
        <ProCard colSpan={6} layout="center" hoverable>
          <StatisticCard
            statistic={{
              title: '总资产',
              value: 1893560,
              prefix: '¥',
              description: (
                <Statistic
                  title="较昨日"
                  value={9.3}
                  trend="up"
                  suffix="%"
                />
              ),
            }}
          />
        </ProCard>
        <ProCard colSpan={6} layout="center" hoverable>
          <StatisticCard
            statistic={{
              title: '今日盈亏',
              value: 93560,
              prefix: '¥',
              valueStyle: { color: '#3f8600' },
              description: (
                <Statistic
                  title="盈亏比"
                  value={5.2}
                  suffix="%"
                />
              ),
            }}
          />
        </ProCard>
        <ProCard colSpan={6} layout="center" hoverable>
          <StatisticCard
            statistic={{
              title: '持仓市值',
              value: 1523650,
              prefix: '¥',
              description: (
                <Statistic
                  title="仓位"
                  value={80.5}
                  suffix="%"
                />
              ),
            }}
          />
        </ProCard>
        <ProCard colSpan={6} layout="center" hoverable>
          <StatisticCard
            statistic={{
              title: '可用资金',
              value: 369910,
              prefix: '¥',
              description: (
                <Statistic
                  title="资金使用率"
                  value={19.5}
                  suffix="%"
                />
              ),
            }}
          />
        </ProCard>
      </ProCard>

      {/* 图表区域 */}
      <Row gutter={[16, 16]}>
        <Col span={16}>
          <Card 
            title="市场走势" 
            extra={<Tag color="blue">实时</Tag>}
            hoverable
          >
            <Line {...lineConfig} height={300} />
          </Card>
        </Col>
        <Col span={8}>
          <Card 
            title="板块分布" 
            extra={<Tag color="orange">今日</Tag>}
            hoverable
          >
            <Pie {...pieConfig} height={300} />
          </Card>
        </Col>
      </Row>

      {/* 成交量图表 */}
      <Card 
        title="成交量分析" 
        style={{ marginTop: 16 }}
        extra={
          <Space>
            <Tag color="green">量能充足</Tag>
            <Text type="secondary">更新于 15:00</Text>
          </Space>
        }
      >
        <Column {...columnConfig} height={200} />
      </Card>

      {/* 股票列表 - 使用 ProTable */}
      <Card 
        title="热门股票" 
        style={{ marginTop: 16 }}
        extra={
          <Space>
            <Badge status="processing" text="实时更新" />
            <Button type="link">查看全部</Button>
          </Space>
        }
      >
        <ProTable
          columns={columns}
          dataSource={mockStockData}
          rowKey="key"
          pagination={false}
          search={false}
          toolBarRender={false}
          bordered
        />
      </Card>

      {/* 系统组件状态 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={12}>
          <Card title="系统组件状态">
            <Timeline
              items={[
                {
                  color: 'green',
                  children: (
                    <>
                      <Text strong>数据采集服务</Text>
                      <Tag color="success" style={{ marginLeft: 8 }}>运行中</Tag>
                      <br />
                      <Text type="secondary">CPU: 23% | 内存: 45%</Text>
                    </>
                  ),
                },
                {
                  color: 'green',
                  children: (
                    <>
                      <Text strong>交易引擎</Text>
                      <Tag color="success" style={{ marginLeft: 8 }}>运行中</Tag>
                      <br />
                      <Text type="secondary">延迟: 2ms | TPS: 10,000</Text>
                    </>
                  ),
                },
                {
                  color: 'blue',
                  children: (
                    <>
                      <Text strong>风控系统</Text>
                      <Tag color="processing" style={{ marginLeft: 8 }}>监控中</Tag>
                      <br />
                      <Text type="secondary">规则: 128条 | 触发: 0次</Text>
                    </>
                  ),
                },
                {
                  color: 'gray',
                  children: (
                    <>
                      <Text strong>回测引擎</Text>
                      <Tag style={{ marginLeft: 8 }}>空闲</Tag>
                      <br />
                      <Text type="secondary">上次运行: 2小时前</Text>
                    </>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="快速操作">
            <CheckCard.Group
              onChange={(value) => {
                console.log('Selected:', value)
              }}
              defaultValue="A"
            >
              <CheckCard
                title="启动所有策略"
                avatar={<RocketOutlined style={{ fontSize: 24 }} />}
                description="一键启动所有已配置的交易策略"
                value="A"
              />
              <CheckCard
                title="停止所有交易"
                avatar={<CloseCircleOutlined style={{ fontSize: 24 }} />}
                description="紧急停止所有正在运行的交易"
                value="B"
              />
              <CheckCard
                title="数据同步"
                avatar={<SyncOutlined style={{ fontSize: 24 }} />}
                description="手动触发数据同步任务"
                value="C"
              />
              <CheckCard
                title="系统诊断"
                avatar={<ThunderboltOutlined style={{ fontSize: 24 }} />}
                description="运行系统健康检查"
                value="D"
              />
            </CheckCard.Group>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default Dashboard