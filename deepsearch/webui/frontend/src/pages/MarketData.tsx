import React, { useState, useEffect } from 'react'
import {
  Card,
  Row,
  Col,
  Table,
  Tag,
  Space,
  Button,
  Select,
  DatePicker,
  Tabs,
  Typography,
  Statistic,
  Input,
  Switch,
  Badge,
  Tooltip,
  Dropdown,
  Menu
} from 'antd'
import { ProCard, StatisticCard, ProTable } from '@ant-design/pro-components'
import { Stock, Line, Column, DualAxes, Area } from '@ant-design/charts'
import {
  RiseOutlined,
  FallOutlined,
  ReloadOutlined,
  StarOutlined,
  StarFilled,
  SearchOutlined,
  FilterOutlined,
  ExportOutlined,
  LineChartOutlined,
  BarChartOutlined,
  StockOutlined,
  FundOutlined
} from '@ant-design/icons'

const { Title, Text } = Typography
const { RangePicker } = DatePicker
const { Search } = Input

const MarketData = () => {
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [selectedStock, setSelectedStock] = useState('000001.SZ')
  const [timeRange, setTimeRange] = useState('1d')
  const [chartType, setChartType] = useState('kline')
  
  // Mock market data
  const [marketOverview, setMarketOverview] = useState({
    sh_index: { value: 3087.53, change: 12.34, changePercent: 0.40 },
    sz_index: { value: 10654.87, change: -45.23, changePercent: -0.42 },
    hs300: { value: 3654.21, change: 8.76, changePercent: 0.24 },
    total_volume: 425678900000,
    total_amount: 538976543210,
    up_count: 2456,
    down_count: 1876,
    flat_count: 234
  })

  // K-line data
  const [klineData, setKlineData] = useState([
    { date: '2025-01-15', open: 12.5, close: 13.2, high: 13.5, low: 12.3, volume: 1234567 },
    { date: '2025-01-16', open: 13.2, close: 13.8, high: 14.0, low: 13.0, volume: 1456789 },
    { date: '2025-01-17', open: 13.8, close: 13.5, high: 14.2, low: 13.4, volume: 1345678 },
    { date: '2025-01-18', open: 13.5, close: 14.1, high: 14.3, low: 13.3, volume: 1567890 },
    { date: '2025-01-19', open: 14.1, close: 13.9, high: 14.5, low: 13.8, volume: 1234567 },
  ])

  // Realtime market data
  const [realtimeData, setRealtimeData] = useState([
    { code: '000001', name: 'Ping An Bank', price: 12.35, change: 0.24, changePercent: 1.98, volume: 123456789, amount: 1523456789, pe: 5.8, pb: 0.65, favorite: true },
    { code: '000002', name: 'Vanke A', price: 15.67, change: -0.12, changePercent: -0.76, volume: 98765432, amount: 1548976543, pe: 8.2, pb: 1.12, favorite: false },
    { code: '000858', name: 'Wuliangye', price: 168.90, change: 2.34, changePercent: 1.40, volume: 23456789, amount: 3961234567, pe: 28.5, pb: 6.78, favorite: true },
    { code: '002415', name: 'Hikvision', price: 35.48, change: -0.56, changePercent: -1.55, volume: 45678901, amount: 1620456789, pe: 18.9, pb: 4.23, favorite: false },
    { code: '300750', name: 'CATL', price: 189.50, change: 3.45, changePercent: 1.85, volume: 12345678, amount: 2339876543, pe: 35.6, pb: 5.89, favorite: true },
  ])

  // Sector data
  const [sectorData, setSectorData] = useState([
    { name: 'New Energy', change: 2.34, volume: 234567890, leadStock: 'CATL' },
    { name: 'Semiconductor', change: 1.56, volume: 189234567, leadStock: 'SMIC' },
    { name: 'Banking', change: -0.45, volume: 456789012, leadStock: 'CMB' },
    { name: 'Liquor', change: 0.89, volume: 123456789, leadStock: 'Moutai' },
    { name: 'Healthcare', change: -1.23, volume: 234567890, leadStock: 'Hengrui' },
  ])

  // Auto refresh
  useEffect(() => {
    if (!autoRefresh) return
    
    const timer = setInterval(() => {
      // Simulate data update
      setRealtimeData(prev => prev.map(item => ({
        ...item,
        price: item.price * (1 + (Math.random() - 0.5) * 0.02),
        change: (Math.random() - 0.5) * 2,
        changePercent: (Math.random() - 0.5) * 4,
        volume: item.volume + Math.floor(Math.random() * 1000000)
      })))
    }, 3000)
    
    return () => clearInterval(timer)
  }, [autoRefresh])

  // K-line chart component
  const KLineChart = ({ data }) => {
    const config = {
      data,
      xField: 'date',
      yField: ['open', 'close', 'high', 'low'],
      meta: {
        date: { alias: 'Date' },
        open: { alias: 'Open' },
        close: { alias: 'Close' },
        high: { alias: 'High' },
        low: { alias: 'Low' },
        volume: { alias: 'Volume' },
      },
    }
    return <Stock {...config} />
  }

  // Volume chart
  const VolumeChart = ({ data }) => {
    const config = {
      data,
      xField: 'date',
      yField: 'volume',
      color: ({ close, open }) => (close > open ? '#52c41a' : '#f5222d'),
      columnStyle: {
        radius: [2, 2, 0, 0],
      },
      xAxis: {
        title: { text: 'Date' },
      },
      yAxis: {
        title: { text: 'Volume' },
      },
    }
    return <Column {...config} />
  }

  // Timeline chart
  const TimeLineChart = ({ data }) => {
    const timeData = Array.from({ length: 240 }, (_, i) => {
      const hour = Math.floor(i / 60) + 9
      const minute = i % 60
      if (hour >= 13) {
        const adjustedHour = hour - 1.5
        return {
          time: `${Math.floor(adjustedHour)}:${minute.toString().padStart(2, '0')}`,
          price: 13.5 + Math.sin(i / 20) * 0.5 + (Math.random() - 0.5) * 0.2,
          volume: Math.floor(Math.random() * 1000000),
        }
      }
      return {
        time: `${hour}:${minute.toString().padStart(2, '0')}`,
        price: 13.5 + Math.sin(i / 20) * 0.5 + (Math.random() - 0.5) * 0.2,
        volume: Math.floor(Math.random() * 1000000),
      }
    })

    const config = {
      data: timeData,
      xField: 'time',
      yField: ['price', 'volume'],
      geometryOptions: [
        {
          geometry: 'line',
          smooth: true,
          color: '#1890ff',
        },
        {
          geometry: 'column',
          color: '#faad14',
        },
      ],
      xAxis: {
        tickCount: 8,
      },
      yAxis: {
        price: {
          min: 13,
          max: 14,
        },
        volume: {
          min: 0,
        },
      },
    }
    return <DualAxes {...config} />
  }

  const handleRefresh = () => {
    setLoading(true)
    setTimeout(() => {
      setLoading(false)
    }, 1000)
  }

  const handleToggleFavorite = (record) => {
    setRealtimeData(prev => prev.map(item => 
      item.code === record.code ? { ...item, favorite: !item.favorite } : item
    ))
  }

  const columns = [
    {
      title: 'Code',
      dataIndex: 'code',
      key: 'code',
      width: 80,
      fixed: 'left',
    },
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      width: 100,
      fixed: 'left',
      render: (text, record) => (
        <Space>
          <span onClick={() => handleToggleFavorite(record)} style={{ cursor: 'pointer' }}>
            {record.favorite ? <StarFilled style={{ color: '#faad14' }} /> : <StarOutlined />}
          </span>
          <span>{text}</span>
        </Space>
      ),
    },
    {
      title: 'Price',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      render: (price, record) => (
        <span style={{ color: record.change > 0 ? '#f5222d' : '#52c41a', fontWeight: 'bold' }}>
          {price.toFixed(2)}
        </span>
      ),
    },
    {
      title: 'Change',
      dataIndex: 'change',
      key: 'change',
      width: 100,
      render: (change) => (
        <span style={{ color: change > 0 ? '#f5222d' : '#52c41a' }}>
          {change > 0 ? '+' : ''}{change.toFixed(2)}
        </span>
      ),
    },
    {
      title: 'Change %',
      dataIndex: 'changePercent',
      key: 'changePercent',
      width: 100,
      render: (percent) => (
        <Tag color={percent > 0 ? 'red' : 'green'}>
          {percent > 0 ? '+' : ''}{percent.toFixed(2)}%
        </Tag>
      ),
    },
    {
      title: 'Volume',
      dataIndex: 'volume',
      key: 'volume',
      width: 120,
      render: (volume) => (volume / 10000).toFixed(2) + 'W',
    },
    {
      title: 'Amount',
      dataIndex: 'amount',
      key: 'amount',
      width: 120,
      render: (amount) => (amount / 100000000).toFixed(2) + 'B',
    },
    {
      title: 'PE',
      dataIndex: 'pe',
      key: 'pe',
      width: 80,
    },
    {
      title: 'PB',
      dataIndex: 'pb',
      key: 'pb',
      width: 80,
    },
  ]

  const sectorColumns = [
    {
      title: 'Sector',
      dataIndex: 'name',
      key: 'name',
      render: (text) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: 'Change %',
      dataIndex: 'change',
      key: 'change',
      render: (change) => (
        <Space>
          {change > 0 ? <RiseOutlined style={{ color: '#f5222d' }} /> : <FallOutlined style={{ color: '#52c41a' }} />}
          <span style={{ color: change > 0 ? '#f5222d' : '#52c41a' }}>
            {change > 0 ? '+' : ''}{change.toFixed(2)}%
          </span>
        </Space>
      ),
    },
    {
      title: 'Volume',
      dataIndex: 'volume',
      key: 'volume',
      render: (volume) => (volume / 100000000).toFixed(2) + 'B',
    },
    {
      title: 'Lead Stock',
      dataIndex: 'leadStock',
      key: 'leadStock',
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
                  <StockOutlined /> Market Data
                </Title>
                <Badge status="processing" text="Real-time" />
              </Space>
            </Col>
            <Col>
              <Space>
                <Search
                  placeholder="Search stock code/name"
                  style={{ width: 200 }}
                  prefix={<SearchOutlined />}
                />
                <Select
                  value={timeRange}
                  onChange={setTimeRange}
                  style={{ width: 120 }}
                  options={[
                    { label: 'Minute', value: '1min' },
                    { label: 'Day', value: '1d' },
                    { label: 'Week', value: '1w' },
                    { label: 'Month', value: '1m' },
                  ]}
                />
                <Switch
                  checked={autoRefresh}
                  onChange={setAutoRefresh}
                  checkedChildren="Auto"
                  unCheckedChildren="Manual"
                />
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleRefresh}
                  loading={loading}
                >
                  Refresh
                </Button>
              </Space>
            </Col>
          </Row>
        </ProCard>

        {/* Market Overview */}
        <ProCard colSpan={24}>
          <StatisticCard.Group>
            <StatisticCard
              statistic={{
                title: 'Shanghai Index',
                value: marketOverview.sh_index.value,
                precision: 2,
                valueStyle: { color: marketOverview.sh_index.change > 0 ? '#f5222d' : '#52c41a' },
                prefix: marketOverview.sh_index.change > 0 ? <RiseOutlined /> : <FallOutlined />,
                suffix: <span style={{ fontSize: 14 }}>{marketOverview.sh_index.change > 0 ? '+' : ''}{marketOverview.sh_index.changePercent.toFixed(2)}%</span>,
              }}
            />
            <StatisticCard
              statistic={{
                title: 'Shenzhen Index',
                value: marketOverview.sz_index.value,
                precision: 2,
                valueStyle: { color: marketOverview.sz_index.change > 0 ? '#f5222d' : '#52c41a' },
                prefix: marketOverview.sz_index.change > 0 ? <RiseOutlined /> : <FallOutlined />,
                suffix: <span style={{ fontSize: 14 }}>{marketOverview.sz_index.change > 0 ? '+' : ''}{marketOverview.sz_index.changePercent.toFixed(2)}%</span>,
              }}
            />
            <StatisticCard
              statistic={{
                title: 'CSI 300',
                value: marketOverview.hs300.value,
                precision: 2,
                valueStyle: { color: marketOverview.hs300.change > 0 ? '#f5222d' : '#52c41a' },
                prefix: marketOverview.hs300.change > 0 ? <RiseOutlined /> : <FallOutlined />,
                suffix: <span style={{ fontSize: 14 }}>{marketOverview.hs300.change > 0 ? '+' : ''}{marketOverview.hs300.changePercent.toFixed(2)}%</span>,
              }}
            />
            <StatisticCard
              statistic={{
                title: 'Total Amount',
                value: marketOverview.total_amount / 100000000,
                precision: 0,
                suffix: 'B',
                valueStyle: { color: '#1890ff' },
              }}
            />
            <StatisticCard
              statistic={{
                title: 'Up/Down',
                value: `${marketOverview.up_count}/${marketOverview.down_count}`,
                valueStyle: { color: marketOverview.up_count > marketOverview.down_count ? '#f5222d' : '#52c41a' },
              }}
            />
          </StatisticCard.Group>
        </ProCard>

        {/* Chart Area */}
        <ProCard colSpan={16}>
          <Card>
            <Tabs
              activeKey={chartType}
              onChange={setChartType}
              items={[
                {
                  key: 'kline',
                  label: 'K-Line',
                  children: <KLineChart data={klineData} />,
                },
                {
                  key: 'timeline',
                  label: 'Timeline',
                  children: <TimeLineChart />,
                },
                {
                  key: 'volume',
                  label: 'Volume',
                  children: <VolumeChart data={klineData} />,
                },
              ]}
            />
          </Card>
        </ProCard>

        {/* Sector Data */}
        <ProCard colSpan={8}>
          <Card title="Sector Performance" extra={<FundOutlined />}>
            <Table
              columns={sectorColumns}
              dataSource={sectorData.map((item, index) => ({ ...item, key: index }))}
              pagination={false}
              size="small"
            />
          </Card>
        </ProCard>

        {/* Realtime Market Table */}
        <ProCard colSpan={24}>
          <Card title="Realtime Market" extra={<Button type="link" icon={<ExportOutlined />}>Export</Button>}>
            <Table
              columns={columns}
              dataSource={realtimeData.map((item, index) => ({ ...item, key: index }))}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showQuickJumper: true,
                showTotal: (total) => `Total ${total} items`,
              }}
              scroll={{ x: 1200 }}
              loading={loading}
            />
          </Card>
        </ProCard>
      </ProCard>
    </div>
  )
}

export default MarketData