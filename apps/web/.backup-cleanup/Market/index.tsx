import React, { useState, useEffect, useRef } from 'react'
import { Card, Row, Col, Table, Button, Space, Select, DatePicker, Statistic, Tag, Typography } from 'antd'
import { ArrowUpOutlined, ArrowDownOutlined, ReloadOutlined, LineChartOutlined } from '@ant-design/icons'
import * as echarts from 'echarts'
import { useMarketData } from '@/hooks/useWebSocket'
import { getKlineData, getQuote } from '@/services/market'
import type { KlineData, Quote } from '@/types'
import './index.scss'

const { Title, Text } = Typography
const { RangePicker } = DatePicker
const { Option } = Select

const Market: React.FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState('000001.SZ')
  const [period, setPeriod] = useState('1d')
  const [klineData, setKlineData] = useState<KlineData[]>([])
  const [quote, setQuote] = useState<Quote | null>(null)
  const [loading, setLoading] = useState(false)

  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<echarts.ECharts | null>(null)

  // 使用WebSocket订阅实时数据
  const { quotes, trades, orderbooks } = useMarketData([selectedSymbol])

  // 热门股票列表
  const hotStocks = [
    { code: '000001.SZ', name: '平安银行', change: 2.35, price: 12.56 },
    { code: '000002.SZ', name: '万科A', change: -1.23, price: 15.78 },
    { code: '000858.SZ', name: '五粮液', change: 3.45, price: 186.32 },
    { code: '002415.SZ', name: '海康威视', change: 1.56, price: 35.67 },
    { code: '300750.SZ', name: '宁德时代', change: -0.89, price: 456.78 }
  ]

  // 初始化图表
  const initChart = () => {
    if (chartRef.current && !chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current)

      const option = {
        title: {
          text: 'K线图',
          left: 0
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross'
          }
        },
        legend: {
          data: ['日K', 'MA5', 'MA10', 'MA20', 'MA30']
        },
        grid: [
          {
            left: '10%',
            right: '8%',
            height: '50%'
          },
          {
            left: '10%',
            right: '8%',
            top: '63%',
            height: '16%'
          }
        ],
        xAxis: [
          {
            type: 'category',
            data: [],
            boundaryGap: false,
            axisLine: { onZero: false },
            splitLine: { show: false },
            min: 'dataMin',
            max: 'dataMax'
          },
          {
            type: 'category',
            gridIndex: 1,
            data: [],
            boundaryGap: false,
            axisLine: { onZero: false },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
            min: 'dataMin',
            max: 'dataMax'
          }
        ],
        yAxis: [
          {
            scale: true,
            splitArea: {
              show: true
            }
          },
          {
            scale: true,
            gridIndex: 1,
            splitNumber: 2,
            axisLabel: { show: false },
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: { show: false }
          }
        ],
        dataZoom: [
          {
            type: 'inside',
            xAxisIndex: [0, 1],
            start: 50,
            end: 100
          },
          {
            show: true,
            xAxisIndex: [0, 1],
            type: 'slider',
            top: '85%',
            start: 50,
            end: 100
          }
        ],
        series: [
          {
            name: '日K',
            type: 'candlestick',
            data: [],
            itemStyle: {
              color: '#ef232a',
              color0: '#14b143',
              borderColor: '#ef232a',
              borderColor0: '#14b143'
            }
          },
          {
            name: 'MA5',
            type: 'line',
            data: [],
            smooth: true,
            lineStyle: { opacity: 0.5 }
          },
          {
            name: 'MA10',
            type: 'line',
            data: [],
            smooth: true,
            lineStyle: { opacity: 0.5 }
          },
          {
            name: 'MA20',
            type: 'line',
            data: [],
            smooth: true,
            lineStyle: { opacity: 0.5 }
          },
          {
            name: 'MA30',
            type: 'line',
            data: [],
            smooth: true,
            lineStyle: { opacity: 0.5 }
          },
          {
            name: '成交量',
            type: 'bar',
            xAxisIndex: 1,
            yAxisIndex: 1,
            data: []
          }
        ]
      }

      chartInstance.current.setOption(option)
    }
  }

  // 更新图表数据
  const updateChart = (data: KlineData[]) => {
    if (!chartInstance.current || data.length === 0) return

    const dates = data.map(item => item.date)
    const klines = data.map(item => [item.open, item.close, item.low, item.high])
    const volumes = data.map(item => item.volume)

    // 计算移动平均线
    const calculateMA = (dayCount: number) => {
      const result = []
      for (let i = 0; i < data.length; i++) {
        if (i < dayCount) {
          result.push('-')
          continue
        }
        let sum = 0
        for (let j = 0; j < dayCount; j++) {
          sum += data[i - j].close
        }
        result.push((sum / dayCount).toFixed(2))
      }
      return result
    }

    chartInstance.current.setOption({
      xAxis: [
        { data: dates },
        { data: dates }
      ],
      series: [
        { data: klines },
        { data: calculateMA(5) },
        { data: calculateMA(10) },
        { data: calculateMA(20) },
        { data: calculateMA(30) },
        { data: volumes }
      ]
    })
  }

  // 加载数据
  const loadData = async () => {
    setLoading(true)
    try {
      const [klineRes, quoteRes] = await Promise.all([
        getKlineData(selectedSymbol, period),
        getQuote(selectedSymbol)
      ])
      setKlineData(klineRes)
      setQuote(quoteRes)
      updateChart(klineRes)
    } catch (error) {
      console.error('加载数据失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 表格列配置
  const columns = [
    {
      title: '代码',
      dataIndex: 'code',
      key: 'code',
      width: 100
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 120
    },
    {
      title: '最新价',
      dataIndex: 'price',
      key: 'price',
      width: 100,
      render: (price: number) => <Text strong>{price.toFixed(2)}</Text>
    },
    {
      title: '涨跌幅',
      dataIndex: 'change',
      key: 'change',
      width: 100,
      render: (change: number) => (
        <Text type={change > 0 ? 'success' : 'danger'}>
          {change > 0 ? '+' : ''}{change.toFixed(2)}%
        </Text>
      )
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record: any) => (
        <Button
          type="link"
          size="small"
          onClick={() => setSelectedSymbol(record.code)}
        >
          查看
        </Button>
      )
    }
  ]

  useEffect(() => {
    initChart()
    loadData()

    // 定时刷新
    const timer = setInterval(loadData, 5000)

    return () => {
      clearInterval(timer)
      chartInstance.current?.dispose()
    }
  }, [selectedSymbol, period])

  // 监听实时数据更新
  useEffect(() => {
    if (quotes[selectedSymbol]) {
      setQuote(quotes[selectedSymbol])
    }
  }, [quotes, selectedSymbol])

  return (
    <div className="market-page">
      <Title level={2}>市场行情</Title>

      {/* 当前行情 */}
      {quote && (
        <Card className="quote-card">
          <Row gutter={24}>
            <Col span={4}>
              <Statistic
                title={`${selectedSymbol} ${quote.name}`}
                value={quote.price}
                precision={2}
                valueStyle={{ color: quote.change > 0 ? '#3f8600' : '#cf1322' }}
                prefix={quote.change > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="涨跌额"
                value={quote.change_amount}
                precision={2}
                valueStyle={{ color: quote.change > 0 ? '#3f8600' : '#cf1322' }}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="涨跌幅"
                value={quote.change}
                precision={2}
                suffix="%"
                valueStyle={{ color: quote.change > 0 ? '#3f8600' : '#cf1322' }}
              />
            </Col>
            <Col span={4}>
              <Statistic title="成交量" value={quote.volume} suffix="手" />
            </Col>
            <Col span={4}>
              <Statistic title="成交额" value={quote.amount} suffix="万" />
            </Col>
            <Col span={4}>
              <Statistic title="换手率" value={quote.turnover} suffix="%" />
            </Col>
          </Row>
        </Card>
      )}

      {/* 控制栏 */}
      <Card className="control-bar">
        <Space>
          <Select value={selectedSymbol} onChange={setSelectedSymbol} style={{ width: 150 }}>
            {hotStocks.map(stock => (
              <Option key={stock.code} value={stock.code}>
                {stock.code} {stock.name}
              </Option>
            ))}
          </Select>

          <Select value={period} onChange={setPeriod}>
            <Option value="1m">1分钟</Option>
            <Option value="5m">5分钟</Option>
            <Option value="15m">15分钟</Option>
            <Option value="30m">30分钟</Option>
            <Option value="1h">1小时</Option>
            <Option value="1d">日线</Option>
            <Option value="1w">周线</Option>
            <Option value="1M">月线</Option>
          </Select>

          <RangePicker />

          <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>
            刷新
          </Button>
        </Space>
      </Card>

      {/* 图表区域 */}
      <Row gutter={24}>
        <Col span={16}>
          <Card title="K线图" loading={loading}>
            <div ref={chartRef} style={{ height: 500 }} />
          </Card>
        </Col>

        <Col span={8}>
          <Card title="热门股票">
            <Table
              dataSource={hotStocks}
              columns={columns}
              rowKey="code"
              pagination={false}
              size="small"
            />
          </Card>

          {/* 实时成交 */}
          {trades[selectedSymbol] && (
            <Card title="实时成交" style={{ marginTop: 16 }}>
              <div className="trades-list">
                {trades[selectedSymbol].slice(0, 10).map((trade: any, index: number) => (
                  <div key={index} className="trade-item">
                    <Space>
                      <Text>{trade.time}</Text>
                      <Text type={trade.direction === 'buy' ? 'success' : 'danger'}>
                        {trade.price}
                      </Text>
                      <Text>{trade.volume}手</Text>
                    </Space>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  )
}

export default Market
