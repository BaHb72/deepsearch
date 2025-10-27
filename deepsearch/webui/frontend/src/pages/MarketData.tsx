import React, {useCallback, useEffect, useRef, useState} from 'react'
import {
    Badge,
    Button,
    Card,
    Col,
    Input,
    message,
    Row,
    Select,
    Space,
    Spin,
    Switch,
    Table,
    Tabs,
    Tag,
    Typography,
} from 'antd'
import {ProCard, StatisticCard} from '@ant-design/pro-components'
import {Column, DualAxes, Stock} from '@ant-design/charts'
import {
    ExportOutlined,
    FallOutlined,
    FundOutlined,
    ReloadOutlined,
    RiseOutlined,
    SearchOutlined,
    StarFilled,
    StarOutlined,
    StockOutlined
} from '@ant-design/icons'
import {AuctionQualityItem, marketDataLiveApi, OrderImbalanceItem, StrengthItem} from '../api/marketDataLive'

type StrengthState = {
    items: StrengthItem[];
    windows: string[];
    boards: string[];
    retrievedAt: string;
    asOf?: string | null;
    stale?: boolean;
    cache?: { cachedAt?: string; expiresAt?: string };
    dataSource?: string;
    lastSuccessAt?: number;
};

type ImbalanceState = {
    window: string;
    items: OrderImbalanceItem[];
    retrievedAt: string;
    asOf?: string | null;
    stale?: boolean;
    cache?: { cachedAt?: string; expiresAt?: string };
    dataSource?: string;
    lastSuccessAt?: number;
};

type AuctionState = {
    boards: string[];
    items: AuctionQualityItem[];
    retrievedAt: string;
    asOf?: string | null;
    stale?: boolean;
    cache?: { cachedAt?: string; expiresAt?: string };
    dataSource?: string;
    lastSuccessAt?: number;
};

const { Title } = Typography
const { Search } = Input

const FALLBACK_THRESHOLD_MS = 10_000

const STRENGTH_PLACEHOLDER: StrengthState = {
    items: [
        {
            board: '暂无数据',
            window: '--',
            data_source: 'mock',
        },
    ],
    windows: [],
    boards: [],
    retrievedAt: '',
    asOf: null,
    stale: true,
    cache: undefined,
    dataSource: 'mock',
    lastSuccessAt: 0,
}

const IMBALANCE_PLACEHOLDER: ImbalanceState = {
    window: '--',
    items: [
        {
            code: '--',
            name: '暂无数据',
            data_source: 'mock',
        },
    ],
    retrievedAt: '',
    asOf: null,
    stale: true,
    cache: undefined,
    dataSource: 'mock',
    lastSuccessAt: 0,
}

const AUCTION_PLACEHOLDER: AuctionState = {
    boards: [],
    items: [
        {
            board: '暂无数据',
            data_source: 'mock',
        },
    ],
    retrievedAt: '',
    asOf: null,
    stale: true,
    cache: undefined,
    dataSource: 'mock',
    lastSuccessAt: 0,
}

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

    const [insightLoading, setInsightLoading] = useState(false)
    const [strengthState, setStrengthState] = useState<StrengthState>({
        items: [],
        windows: [],
        boards: [],
        retrievedAt: '',
        asOf: null,
        stale: false,
        cache: undefined,
        dataSource: 'amazingdata',
        lastSuccessAt: 0,
    })
    const [imbalanceState, setImbalanceState] = useState<ImbalanceState>({
        window: '',
        items: [],
        retrievedAt: '',
        asOf: null,
        stale: false,
        cache: undefined,
        dataSource: 'amazingdata',
        lastSuccessAt: 0,
    })
    const [auctionState, setAuctionState] = useState<AuctionState>({
        boards: [],
        items: [],
        retrievedAt: '',
        asOf: null,
        stale: false,
        cache: undefined,
        dataSource: 'amazingdata',
        lastSuccessAt: 0,
    })
    const insightRequestRef = useRef(false)

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
  const TimeLineChart = () => {
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
      setMarketOverview(prev => ({
        ...prev,
        sh_index: {
          ...prev.sh_index,
          value: Number((prev.sh_index.value * (1 + (Math.random() - 0.5) * 0.004)).toFixed(2)),
          change: Number(((Math.random() - 0.5) * 2).toFixed(2)),
          changePercent: Number(((Math.random() - 0.5) * 1.5).toFixed(2)),
        },
        sz_index: {
          ...prev.sz_index,
          value: Number((prev.sz_index.value * (1 + (Math.random() - 0.5) * 0.004)).toFixed(2)),
          change: Number(((Math.random() - 0.5) * 2).toFixed(2)),
          changePercent: Number(((Math.random() - 0.5) * 1.5).toFixed(2)),
        },
        hs300: {
          ...prev.hs300,
          value: Number((prev.hs300.value * (1 + (Math.random() - 0.5) * 0.004)).toFixed(2)),
          change: Number(((Math.random() - 0.5) * 2).toFixed(2)),
          changePercent: Number(((Math.random() - 0.5) * 1.5).toFixed(2)),
        },
        total_amount: Math.max(0, prev.total_amount * (1 + (Math.random() - 0.5) * 0.01)),
        up_count: Math.max(0, prev.up_count + Math.round((Math.random() - 0.5) * 30)),
        down_count: Math.max(0, prev.down_count + Math.round((Math.random() - 0.5) * 30)),
      }))

      setKlineData(prev => prev.map(item => {
        const delta = (Math.random() - 0.5) * 0.6
        const newClose = Number((item.close + delta).toFixed(2))
        const newOpen = Number((item.open + delta / 2).toFixed(2))
        const newHigh = Number(Math.max(newOpen, newClose, item.high + Math.random() * 0.3).toFixed(2))
        const newLow = Number(Math.min(newOpen, newClose, item.low - Math.random() * 0.3).toFixed(2))
        return {
          ...item,
          open: newOpen,
          close: newClose,
          high: newHigh,
          low: newLow,
          volume: item.volume + Math.floor(Math.random() * 500000),
        }
      }))

      setSectorData(prev => prev.map(sector => ({
        ...sector,
        change: Number((sector.change + (Math.random() - 0.5)).toFixed(2)),
        volume: Math.max(0, sector.volume + Math.floor((Math.random() - 0.5) * 1000000)),
      })))

      setLoading(false)
    }, 1000)
  }

  const handleToggleFavorite = (record) => {
    setRealtimeData(prev => prev.map(item => 
      item.code === record.code ? { ...item, favorite: !item.favorite } : item
    ))
  }
    const formatAmountUnit = (value?: number) => {
        if (typeof value !== 'number' || Number.isNaN(value)) return '--'
        const abs = Math.abs(value)
        if (abs >= 1e9) return `${(value / 1e9).toFixed(2)}十亿`
        if (abs >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
        if (abs >= 1e6) return `${(value / 1e6).toFixed(2)}百万`
        if (abs >= 1e4) return `${(value / 1e4).toFixed(2)}万`
        return value.toFixed(2)
    }

    const formatNumberValue = (value?: number, digits = 2) => {
        if (typeof value !== 'number' || Number.isNaN(value)) return '--'
        return value.toFixed(digits)
    }

    const formatTimestamp = (value?: string) => {
        if (!value) return '--'
        const date = new Date(value)
        if (Number.isNaN(date.getTime())) return value
        return date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'})
    }

    const fetchMarketInsights = useCallback(async () => {
        if (insightRequestRef.current) {
            return
        }
        insightRequestRef.current = true
        setInsightLoading(true)
        try {
            const results = await Promise.allSettled([
                marketDataLiveApi.getStrength(),
                marketDataLiveApi.getOrderImbalance({limit: 30}),
                marketDataLiveApi.getAuctionQuality(),
            ])

            const now = Date.now()
            const fallbackIso = new Date(now).toISOString()
            let hasFailure = false
            let usedPlaceholder = false
            let reusedPrevious = false
            const [strengthResult, imbalanceResult, auctionResult] = results

            setStrengthState((prev) => {
                const success =
                    strengthResult.status === 'fulfilled' &&
                    strengthResult.value?.data &&
                    Array.isArray(strengthResult.value.data.items) &&
                    strengthResult.value.data.items.length > 0

                if (success) {
                    const payload = strengthResult.value.data
                    return {
                        items: payload.items ?? [],
                        windows: payload.windows ?? prev.windows,
                        boards: payload.boards ?? prev.boards,
                        retrievedAt: payload.retrieved_at ?? fallbackIso,
                        asOf: payload.asOf ?? (payload as any).as_of ?? null,
                        stale: payload.stale ?? false,
                        cache: payload.cache ?? undefined,
                        dataSource: payload.data_source ?? 'amazingdata',
                        lastSuccessAt: now,
                    }
                }

                hasFailure = true
                const hasRecentData =
                    prev.items.length > 0 && prev.lastSuccessAt && now - prev.lastSuccessAt <= FALLBACK_THRESHOLD_MS

                if (hasRecentData) {
                    reusedPrevious = true
                    return {
                        ...prev,
                        stale: true,
                        retrievedAt: fallbackIso,
                    }
                }

                usedPlaceholder = true
                return {
                    ...STRENGTH_PLACEHOLDER,
                    retrievedAt: fallbackIso,
                    lastSuccessAt: prev.lastSuccessAt,
                }
            })

            setImbalanceState((prev) => {
                const success =
                    imbalanceResult.status === 'fulfilled' &&
                    imbalanceResult.value?.data &&
                    Array.isArray(imbalanceResult.value.data.items) &&
                    imbalanceResult.value.data.items.length > 0

                if (success) {
                    const payload = imbalanceResult.value.data
                    return {
                        window: (payload.window ?? prev.window ?? '').trim(),
                        items: payload.items ?? [],
                        retrievedAt: payload.retrieved_at ?? fallbackIso,
                        asOf: payload.asOf ?? (payload as any).as_of ?? null,
                        stale: payload.stale ?? false,
                        cache: payload.cache ?? undefined,
                        dataSource: payload.data_source ?? 'amazingdata',
                        lastSuccessAt: now,
                    }
                }

                hasFailure = true
                const hasRecentData =
                    prev.items.length > 0 && prev.lastSuccessAt && now - prev.lastSuccessAt <= FALLBACK_THRESHOLD_MS

                if (hasRecentData) {
                    reusedPrevious = true
                    return {
                        ...prev,
                        stale: true,
                        retrievedAt: fallbackIso,
                    }
                }

                usedPlaceholder = true
                return {
                    ...IMBALANCE_PLACEHOLDER,
                    window: prev.window || IMBALANCE_PLACEHOLDER.window,
                    retrievedAt: fallbackIso,
                    lastSuccessAt: prev.lastSuccessAt,
                }
            })

            setAuctionState((prev) => {
                const success =
                    auctionResult.status === 'fulfilled' &&
                    auctionResult.value?.data &&
                    Array.isArray(auctionResult.value.data.items) &&
                    auctionResult.value.data.items.length > 0

                if (success) {
                    const payload = auctionResult.value.data
                    return {
                        boards: payload.boards ?? prev.boards,
                        items: payload.items ?? [],
                        retrievedAt: payload.retrieved_at ?? fallbackIso,
                        asOf: payload.asOf ?? (payload as any).as_of ?? null,
                        stale: payload.stale ?? false,
                        cache: payload.cache ?? undefined,
                        dataSource: payload.data_source ?? 'amazingdata',
                        lastSuccessAt: now,
                    }
                }

                hasFailure = true
                const hasRecentData =
                    prev.items.length > 0 && prev.lastSuccessAt && now - prev.lastSuccessAt <= FALLBACK_THRESHOLD_MS

                if (hasRecentData) {
                    reusedPrevious = true
                    return {
                        ...prev,
                        stale: true,
                        retrievedAt: fallbackIso,
                    }
                }

                usedPlaceholder = true
                return {
                    ...AUCTION_PLACEHOLDER,
                    boards: prev.boards.length ? prev.boards : AUCTION_PLACEHOLDER.boards,
                    retrievedAt: fallbackIso,
                    lastSuccessAt: prev.lastSuccessAt,
                }
            })

            if (usedPlaceholder) {
                message.warning({
                    key: 'market-insight-fallback',
                    content: '实时指标暂不可用，已展示占位数据',
                })
            } else if (reusedPrevious) {
                message.info({
                    key: 'market-insight-fallback',
                    content: '实时指标更新失败，已保留上一版数据',
                })
            } else if (hasFailure) {
                message.warning({
                    key: 'market-insight-fallback',
                    content: '实时指标部分数据加载失败',
                })
            } else {
                message.destroy('market-insight-fallback')
            }
        } catch (error) {
            console.warn('Failed to load realtime market insights', error)
            const now = Date.now()
            const fallbackIso = new Date(now).toISOString()
            setStrengthState((prev) => {
                if (prev.items.length > 0 && prev.lastSuccessAt && now - prev.lastSuccessAt <= FALLBACK_THRESHOLD_MS) {
                    return {
                        ...prev,
                        stale: true,
                        retrievedAt: fallbackIso,
                    }
                }
                return {
                    ...STRENGTH_PLACEHOLDER,
                    retrievedAt: fallbackIso,
                    lastSuccessAt: prev.lastSuccessAt,
                }
            })
            setImbalanceState((prev) => {
                if (prev.items.length > 0 && prev.lastSuccessAt && now - prev.lastSuccessAt <= FALLBACK_THRESHOLD_MS) {
                    return {
                        ...prev,
                        stale: true,
                        retrievedAt: fallbackIso,
                    }
                }
                return {
                    ...IMBALANCE_PLACEHOLDER,
                    window: prev.window || IMBALANCE_PLACEHOLDER.window,
                    retrievedAt: fallbackIso,
                    lastSuccessAt: prev.lastSuccessAt,
                }
            })
            setAuctionState((prev) => {
                if (prev.items.length > 0 && prev.lastSuccessAt && now - prev.lastSuccessAt <= FALLBACK_THRESHOLD_MS) {
                    return {
                        ...prev,
                        stale: true,
                        retrievedAt: fallbackIso,
                    }
                }
                return {
                    ...AUCTION_PLACEHOLDER,
                    boards: prev.boards.length ? prev.boards : AUCTION_PLACEHOLDER.boards,
                    retrievedAt: fallbackIso,
                    lastSuccessAt: prev.lastSuccessAt,
                }
            })
            message.error({
                key: 'market-insight-fallback',
                content: '实时指标加载失败，已展示占位数据',
            })
        } finally {
            insightRequestRef.current = false
            setInsightLoading(false)
        }
    }, [])
    const handleInsightRefresh = () => {
        fetchMarketInsights()
    }

    useEffect(() => {
        fetchMarketInsights()
    }, [fetchMarketInsights])

    useEffect(() => {
        if (!autoRefresh) {
            return
        }
        const timer = setInterval(() => {
            fetchMarketInsights()
        }, 15000)
        return () => clearInterval(timer)
    }, [autoRefresh, fetchMarketInsights])



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

    const strengthColumns = [
        {
            title: '板块',
            dataIndex: 'board',
            key: 'board',
            width: 100,
        },
        {
            title: '窗口',
            dataIndex: 'window',
            key: 'window',
            width: 80,
        },
        {
            title: '资金总额',
            dataIndex: 'amount_total',
            key: 'amount_total',
            render: (value?: number) => formatAmountUnit(value),
        },
        {
            title: '资金速度',
            dataIndex: 'speed_per_min',
            key: 'speed_per_min',
            render: (value?: number) => formatAmountUnit(value),
        },
        {
            title: '加速度',
            dataIndex: 'accel_per_min2',
            key: 'accel_per_min2',
            render: (value?: number) => formatNumberValue(value),
        },
    ]

    const orderImbalanceColumns = [
        {
            title: '代码',
            dataIndex: 'code',
            key: 'code',
            width: 100,
        },
        {
            title: '名称',
            dataIndex: 'name',
            key: 'name',
            width: 120,
            render: (value?: string) => value || '--',
        },
        {
            title: 'OBI',
            dataIndex: 'obi',
            key: 'obi',
            render: (value?: number) => formatNumberValue(value),
        },
        {
            title: 'EIS',
            dataIndex: 'eis',
            key: 'eis',
            render: (value?: number) => formatNumberValue(value),
        },
        {
            title: 'NTM',
            dataIndex: 'ntm',
            key: 'ntm',
            render: (value?: number) => formatNumberValue(value, 0),
        },
    ]

    const auctionColumns = [
        {
            title: '板块',
            dataIndex: 'board',
            key: 'board',
            width: 120,
        },
        {
            title: '资金速度',
            dataIndex: 'speed_per_min',
            key: 'speed_per_min',
            render: (value?: number) => formatAmountUnit(value),
        },
        {
            title: '累计成交额',
            dataIndex: 'amount_acc',
            key: 'amount_acc',
            render: (value?: number) => formatAmountUnit(value),
        },
        {
            title: '价格稳定度',
            dataIndex: 'price_stability',
            key: 'price_stability',
            render: (value?: number) => formatNumberValue(value),
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
                  <StockOutlined /> Market Data · {selectedStock}
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
                  allowClear
                  onSearch={(value) => value && setSelectedStock(value)}
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
          <ProCard colSpan={24}>
              <Spin spinning={insightLoading}>
                  <Row gutter={16}>
                      <Col span={12}>
                          <Card
                              title="板块资金脉冲"
                              size="small"
                              extra={(
                                  <Space size="small">
                                      {strengthState.windows.length > 0 && (
                                          <Tag color="blue">窗口 {strengthState.windows.join(' / ')}</Tag>
                                      )}
                                      {strengthState.retrievedAt && (
                                          <Tag>{formatTimestamp(strengthState.retrievedAt)}</Tag>
                                      )}
                                      {strengthState.asOf && (
                                          <Tag color={strengthState.stale ? 'orange' : 'blue'}>
                                              AsOf {formatTimestamp(strengthState.asOf)}
                                          </Tag>
                                      )}
                                      {strengthState.stale && (
                                          <Tag color="red">数据暂未刷新</Tag>
                                      )}
                                      <Button
                                          type="link"
                                          size="small"
                                          icon={<ReloadOutlined spin={insightLoading}/>}
                                          onClick={handleInsightRefresh}
                                      >
                                          刷新
                                      </Button>
                                  </Space>
                              )}
                          >
                              <Table
                                  columns={strengthColumns}
                                  dataSource={strengthState.items.map((item, index) => ({...item, key: index}))}
                                  pagination={{pageSize: 8, size: 'small'}}
                                  size="small"
                                  rowKey="key"
                              />
                          </Card>
                      </Col>
                      <Col span={6}>
                          <Card
                              title="委托失衡 TOP"
                              size="small"
                              extra={(
                                  <Space size="small">
                                      {imbalanceState.window && <Tag color="purple">窗口 {imbalanceState.window}</Tag>}
                                      {imbalanceState.retrievedAt && (
                                          <Tag>{formatTimestamp(imbalanceState.retrievedAt)}</Tag>
                                      )}
                                      {imbalanceState.asOf && (
                                          <Tag color={imbalanceState.stale ? 'orange' : 'blue'}>
                                              AsOf {formatTimestamp(imbalanceState.asOf)}
                                          </Tag>
                                      )}
                                      {imbalanceState.stale && (
                                          <Tag color="red">排名可能滞后</Tag>
                                      )}
                                  </Space>
                              )}
                          >
                              <Table
                                  columns={orderImbalanceColumns}
                                  dataSource={imbalanceState.items.map((item, index) => ({...item, key: index}))}
                                  pagination={{pageSize: 6, size: 'small'}}
                                  size="small"
                                  rowKey="key"
                              />
                          </Card>
                      </Col>
                      <Col span={6}>
                          <Card
                              title="竞价质量"
                              size="small"
                              extra={(
                                  <Space size="small">
                                      {auctionState.retrievedAt && (
                                          <Tag>{formatTimestamp(auctionState.retrievedAt)}</Tag>
                                      )}
                                      {auctionState.asOf && (
                                          <Tag color={auctionState.stale ? 'orange' : 'blue'}>
                                              AsOf {formatTimestamp(auctionState.asOf)}
                                          </Tag>
                                      )}
                                      {auctionState.stale && (
                                          <Tag color="red">数据延迟</Tag>
                                      )}
                                  </Space>
                              )}
                          >
                              <Table
                                  columns={auctionColumns}
                                  dataSource={auctionState.items.map((item, index) => ({...item, key: index}))}
                                  pagination={false}
                                  size="small"
                                  rowKey="key"
                              />
                          </Card>
                      </Col>
                  </Row>
              </Spin>
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
