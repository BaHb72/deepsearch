/**
 * 系统API客户端
 * 提供系统状态、监控和资源使用情况的真实数据
 */
import request from './request';
import type { LogSettings } from '@/types/systemConfig';

type ApiEnvelope<T> = {
  code?: number;
  message?: string;
  data: T;
};

export interface ProviderStatusDetails {
  connected: boolean;
  available?: boolean;
  details?: Record<string, any>;
}

export interface BoardStatus {
  ready: boolean;
  count: number;
  sample?: string[];
}

export interface RuntimeStatus {
  pipeline: string;
  runner: string;
}

export interface CacheStatus {
  available: boolean;
}

export interface MarketDataStatus {
  ready: boolean;
  provider: ProviderStatusDetails;
  boards: BoardStatus;
  runtime: RuntimeStatus;
  cache: CacheStatus;
}

function unwrapResponse<T>(response: unknown): T | null {
  if (response == null) {
    return null;
  }

  const payload = (response as any)?.data ?? response;

  if (
    payload &&
    typeof payload === 'object' &&
    'data' in (payload as Record<string, unknown>) &&
    (Object.prototype.hasOwnProperty.call(payload, 'code') ||
      Object.prototype.hasOwnProperty.call(payload, 'message'))
  ) {
    const envelope = payload as ApiEnvelope<T>;
    return (envelope.data ?? null) as T | null;
  }

  return (payload ?? null) as T | null;
}

export interface SystemInfo {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_in: number;
  network_out: number;
  process_count: number;
  uptime: number;
  timestamp: number;
  status?: 'running' | 'stopped' | string;
  updated_at?: string;
  ready?: boolean;
  market_data?: MarketDataStatus;
  engine?: {
    running: boolean;
    uptime: number;
    event_count: number;
    queue_size: number;
  };
  monitor?: {
    running: boolean;
    api_running: boolean;
  };
  components?: Record<string, any>;
  total_components?: number;
  healthy_components?: number;
  key_metrics?: Record<string, any>;
  error?: string;
}

export interface SystemMetrics {
  cpu: {
    cores: number;
    frequency: number;
    user_time: number;
    system_time: number;
    idle_time: number;
  };
  memory: {
    total: number;
    available: number;
    used: number;
    cached: number;
  };
  io: {
    read_bytes: number;
    write_bytes: number;
    read_count: number;
    write_count: number;
  };
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'critical';
  components: {
    [key: string]: {
      status: 'healthy' | 'degraded' | 'critical';
      message?: string;
    };
  };
}

const getSystemStatus = async (): Promise<SystemInfo | null> => {
  const response = await request.get<SystemInfo | ApiEnvelope<SystemInfo>>('/system/status');
  return unwrapResponse<SystemInfo>(response);
};

const getSystemMetrics = () => request.get<SystemMetrics>('/system/metrics');

const getSystemStatistics = () => request.get('/system/statistics');

const getHealthCheck = () => request.get<SystemHealth>('/health');

const getSystemLogs = (params?: { level?: string; limit?: number; offset?: number }) =>
  request.get('/system/logs', { params });

const getRecentLogs = (params?: { lines?: number; level?: string }) =>
  request.get('/system/logs/recent', { params });

const getSystemConfig = () => request.get('/system/config');

const updateSystemConfig = (config: any) => request.post('/system/config', config);

const getLogConfig = async (): Promise<LogSettings | null> => {
  const response = await request.get<LogSettings | ApiEnvelope<LogSettings>>('/system/config/log');
  return unwrapResponse<LogSettings>(response);
};

interface LogConfigUpdateResponse {
  success?: boolean;
  message?: string;
}

const updateLogConfig = async (config: LogSettings): Promise<LogConfigUpdateResponse> => {
  const response = await request.post<LogConfigUpdateResponse | ApiEnvelope<LogConfigUpdateResponse>>('/system/config/log', config);
  return unwrapResponse<LogConfigUpdateResponse>(response) ?? {};
};

const getSystemInfo = () => request.get('/system/info');

const getMonitorData = () => request.get('/monitor/metrics');

const getComponentStatus = () => request.get('/monitor/components');

const startSystem = () => request.post('/system/start');

const stopSystem = () => request.post('/system/stop');

const restartSystem = () => request.post('/system/restart');

const startComponent = (componentName: string) =>
  request.post(`/system/components/${componentName}/start`);

const stopComponent = (componentName: string) =>
  request.post(`/system/components/${componentName}/stop`);

const controlComponent = (componentName: string, action: string) =>
  request.post(`/system/components/${componentName}/${action}`);

const checkComponentHealth = (componentName: string) =>
  request.get(`/system/components/${componentName}/health`);

// ============ 合并自废弃 services/system.ts|js ============

const clearCache = () => request.post('/system/cache/clear');

const getAlerts = () => request.get('/system/alerts');

const getPerformanceMetrics = () => request.get('/system/performance');

export const systemAPI = {
  getSystemStatus,
  getStatus: getSystemStatus,
  getSystemMetrics,
  getMetrics: getSystemMetrics,
  getSystemStatistics,
  getStatistics: getSystemStatistics,
  getHealthCheck,
  getHealth: getHealthCheck,
  getSystemLogs,
  getLogs: getSystemLogs,
  getRecentLogs,
  getSystemConfig,
  getConfig: getSystemConfig,
  updateSystemConfig,
  updateConfig: updateSystemConfig,
  getLogConfig,
  updateLogConfig,
  getSystemInfo,
  getInfo: getSystemInfo,
  getMonitorData,
  getMonitorMetrics: getMonitorData,
  getComponentStatus,
  getComponents: getComponentStatus,
  startSystem,
  stopSystem,
  restartSystem,
  // 兼容 AppContext 使用的短别名
  start: startSystem,
  stop: stopSystem,
  restart: restartSystem,
  startComponent,
  stopComponent,
  controlComponent,
  checkComponentHealth,
  // 合并自废弃 services/system.ts|js
  clearCache,
  getAlerts,
  getPerformanceMetrics,
};

export default systemAPI;
