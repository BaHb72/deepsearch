/**
 * 数据源API客户端
 * 提供数据源管理、监控和状态信息
 */
import request from './request';

export interface DataSource {
  name: string;
  type: string;
  status: 'online' | 'offline' | 'degraded';
  priority: number;
  is_available: boolean;
  capabilities?: string[];
  config?: any;
}

export interface DataSourceStatus {
  source: string;
  status: 'online' | 'offline' | 'degraded';
  latency: number;
  success_rate: number;
  last_check: string;
  error_count: number;
  request_count: number;
}

export interface DataSourceMetrics {
  totalRequests: number;
  avgLatency: number;
  successRate: number;
  errorRate: number;
  requestsPerMinute: number;
  bytesTransferred: number;
  cacheHitRate: number;
  activeConnections: number;
}

export interface DataSourceMonitor {
  overview: DataSourceMetrics;
  sources: DataSourceStatus[];
  timeline: {
    time: string;
    requests: number;
    latency: number;
    errors: number;
  }[];
  alerts: {
    level: 'info' | 'warning' | 'error';
    message: string;
    timestamp: string;
    source?: string;
  }[];
}

export const dataSourceAPI = {
  /**
   * 获取所有数据源
   */
  getDataSources: () =>
    request.get<DataSource[]>('/data-sources/list'),

  /**
   * 获取数据源状态
   */
  getDataSourceStatus: () =>
    request.get<Record<string, string>>('/data-sources/status'),

  /**
   * 获取数据源监控信息
   */
  getDataSourceMonitor: () =>
    request.get<DataSourceMonitor>('/data-sources/monitor'),

  /**
   * 获取数据源指标
   */
  getDataSourceMetrics: (source?: string) =>
    request.get<DataSourceMetrics>('/data-sources/metrics', {
      params: { source }
    }),

  /**
   * 切换数据源
   */
  switchDataSource: (sourceName: string) =>
    request.post('/data-sources/switch', { source: sourceName }),

  /**
   * 测试数据源连接
   */
  testDataSource: (sourceName: string) =>
    request.post(`/data-sources/test/${sourceName}`),

  /**
   * 获取数据源配置
   */
  getDataSourceConfig: (sourceName: string) =>
    request.get(`/data-sources/config/${sourceName}`),

  /**
   * 更新数据源配置
   */
  updateDataSourceConfig: (sourceName: string, config: any) =>
    request.put(`/data-sources/config/${sourceName}`, config),

  /**
   * 获取数据源能力列表
   */
  getDataSourceCapabilities: (sourceName: string) =>
    request.get<string[]>(`/data-sources/capabilities/${sourceName}`),

  /**
   * 刷新数据源缓存
   */
  refreshDataSourceCache: (sourceName?: string) =>
    request.post('/data-sources/cache/refresh', { source: sourceName }),

  /**
   * 获取数据源历史记录
   */
  getDataSourceHistory: (params?: {
    source?: string;
    start_time?: string;
    end_time?: string;
    limit?: number;
  }) =>
    request.get('/data-sources/history', { params }),

  /**
   * 获取数据源错误日志
   */
  getDataSourceErrors: (params?: {
    source?: string;
    level?: string;
    limit?: number;
  }) =>
    request.get('/data-sources/errors', { params }),
};

export default dataSourceAPI;