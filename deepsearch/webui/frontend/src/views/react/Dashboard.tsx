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
import { marketAPI } from '@/api/market'
import { systemAPI } from '@/api/system'
import './Dashboard.scss'

const { Title, Text, Paragraph } = Typography
const { Ribbon } = Badge

// 默认板块数据（后续从API获取）

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
  const [marketData, setMarketData] = useState([])
  const [stockData, setStockData] = useState([])

  useEffect(() => {
    fetchDashboardData()
  }, [])

  const fetchDashboardData = async () => {
    try {
      setLoading(true)

      // 并行获取数据
      const [marketResponse, stockResponse] = await Promise.all([
        marketAPI.getTimelineData('000001.SH'), // 获取上证指数分时数据
        marketAPI.getStockList({ limit: 10 }) // 获取前10只股票
      ])

      // 处理市场数据
      if (marketResponse.data) {
        const timelineData = marketResponse.data
        // 转换为图表需要的格式
        const formattedMarketData = timelineData.map(item => ({
          time: item.time,
          value: item.price || item.close || 0,
          volume: item.volume || 0
        }))
        setMarketData(formattedMarketData)
      }

      // 处理股票列表数据
      if (stockResponse.data) {
        const formattedStockData = stockResponse.data.map((stock, index) => ({
          key: String(index + 1),
          code: stock.symbol || stock.code,
          name: stock.name,
          price: stock.price || 0,
          change: stock.changePercent || 0,
          volume: stock.volume || 0,
          amount: stock.amount || 0
        }))
        setStockData(formattedStockData)
      }

      // 获取系统状态
      systemStore.fetchStatus().catch(console.error)
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error)
      // 使用默认空数据
      setMarketData([])
      setStockData([])
    } finally {
      setLoading(false)
    }
  }

  // 图表配置
  const lineConfig = {
    data: marketData,
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
    data: marketData,
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

  // 股票数据从API获取，不再使用mock数据

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
          dataSource={stockData}
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