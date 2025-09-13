// 全局类型定义

// API 响应类型
export interface ApiResponse<T = any> {
  code: number
  data: T
  message: string
  timestamp?: number
}

// 分页响应
export interface PaginationResponse<T = any> {
  list: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// 用户类型
export interface User {
  id: string
  username: string
  name: string
  email: string
  avatar?: string
  role: UserRole
  permissions: string[]
  createdAt: string
  updatedAt: string
}

export enum UserRole {
  ADMIN = 'admin',
  USER = 'user',
  GUEST = 'guest'
}

// 系统状态
export interface SystemStatus {
  engine: {
    running: boolean
    uptime: number
    version: string
  }
  components: ComponentStatus[]
  statistics: SystemStatistics
  health: HealthStatus
}

export interface ComponentStatus {
  name: string
  status: 'running' | 'stopped' | 'error' | 'warning'
  message?: string
  metadata?: Record<string, any>
}

export interface SystemStatistics {
  totalEvents: number
  eventsPerSecond: number
  activeConnections: number
  memoryUsage: number
  cpuUsage: number
  diskUsage: number
}

export interface HealthStatus {
  overall: 'healthy' | 'degraded' | 'unhealthy'
  checks: HealthCheck[]
}

export interface HealthCheck {
  name: string
  status: 'pass' | 'fail' | 'warn'
  message?: string
  timestamp: string
}

// 市场数据类型
export interface Stock {
  code: string
  name: string
  market: string
  price: number
  change: number
  changePercent: number
  volume: number
  amount: number
  high: number
  low: number
  open: number
  preClose: number
  timestamp: string
}

export interface MarketIndex {
  code: string
  name: string
  value: number
  change: number
  changePercent: number
  volume: number
  amount: number
}

export interface Kline {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
}

export interface OrderBook {
  asks: OrderBookLevel[]
  bids: OrderBookLevel[]
  timestamp: string
}

export interface OrderBookLevel {
  price: number
  volume: number
  count?: number
}

export interface Trade {
  id: string
  price: number
  volume: number
  amount: number
  direction: 'buy' | 'sell'
  timestamp: string
}

// 交易类型
export interface Strategy {
  id: string
  name: string
  description: string
  type: StrategyType
  status: StrategyStatus
  params: Record<string, any>
  performance: StrategyPerformance
  createdAt: string
  updatedAt: string
}

export enum StrategyType {
  TREND = 'trend',
  ARBITRAGE = 'arbitrage',
  MARKET_MAKING = 'market_making',
  GRID = 'grid',
  CUSTOM = 'custom'
}

export enum StrategyStatus {
  ACTIVE = 'active',
  PAUSED = 'paused',
  STOPPED = 'stopped',
  ERROR = 'error'
}

export interface StrategyPerformance {
  totalReturn: number
  annualizedReturn: number
  sharpeRatio: number
  maxDrawdown: number
  winRate: number
  profitFactor: number
  totalTrades: number
}

export interface Position {
  id: string
  strategyId: string
  symbol: string
  side: 'long' | 'short'
  quantity: number
  avgPrice: number
  currentPrice: number
  pnl: number
  pnlPercent: number
  createdAt: string
  updatedAt: string
}

export interface Order {
  id: string
  strategyId: string
  symbol: string
  type: OrderType
  side: OrderSide
  quantity: number
  price?: number
  status: OrderStatus
  filledQuantity: number
  avgFilledPrice?: number
  commission: number
  createdAt: string
  updatedAt: string
}

export enum OrderType {
  MARKET = 'market',
  LIMIT = 'limit',
  STOP = 'stop',
  STOP_LIMIT = 'stop_limit'
}

export enum OrderSide {
  BUY = 'buy',
  SELL = 'sell'
}

export enum OrderStatus {
  PENDING = 'pending',
  SUBMITTED = 'submitted',
  PARTIAL = 'partial',
  FILLED = 'filled',
  CANCELLED = 'cancelled',
  REJECTED = 'rejected'
}

// WebSocket 消息类型
export interface WSMessage<T = any> {
  type: WSMessageType
  data: T
  timestamp: number
  id?: string
}

export enum WSMessageType {
  // 市场数据
  QUOTE = 'quote',
  TRADE = 'trade',
  ORDERBOOK = 'orderbook',
  KLINE = 'kline',
  
  // 交易消息
  ORDER_UPDATE = 'order_update',
  POSITION_UPDATE = 'position_update',
  STRATEGY_UPDATE = 'strategy_update',
  
  // 系统消息
  SYSTEM_STATUS = 'system_status',
  COMPONENT_UPDATE = 'component_update',
  NOTIFICATION = 'notification',
  ALERT = 'alert',
  
  // 控制消息
  SUBSCRIBE = 'subscribe',
  UNSUBSCRIBE = 'unsubscribe',
  HEARTBEAT = 'heartbeat',
  ERROR = 'error'
}

// 通知类型
export interface Notification {
  id: string
  type: NotificationType
  title: string
  message: string
  timestamp: string
  read: boolean
  data?: any
}

export enum NotificationType {
  INFO = 'info',
  SUCCESS = 'success',
  WARNING = 'warning',
  ERROR = 'error'
}

// 配置类型
export interface SystemConfig {
  general: GeneralConfig
  trading: TradingConfig
  data: DataConfig
  monitoring: MonitoringConfig
  notification: NotificationConfig
}

export interface GeneralConfig {
  timezone: string
  language: string
  theme: string
  debug: boolean
}

export interface TradingConfig {
  defaultLeverage: number
  maxPositionSize: number
  riskLimit: number
  commissionRate: number
  slippage: number
}

export interface DataConfig {
  sources: DataSource[]
  updateInterval: number
  cacheEnabled: boolean
  cacheSize: number
}

export interface DataSource {
  id: string
  name: string
  type: string
  enabled: boolean
  priority: number
  config: Record<string, any>
}

export interface MonitoringConfig {
  metricsEnabled: boolean
  loggingLevel: string
  alertsEnabled: boolean
  retentionDays: number
}

export interface NotificationConfig {
  emailEnabled: boolean
  smsEnabled: boolean
  webhookEnabled: boolean
  webhookUrl?: string
}