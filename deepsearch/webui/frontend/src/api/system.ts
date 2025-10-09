/**
 * 系统API客户端
 * 提供系统状态、监控和资源使用情况的真实数据
 */
import request from './request';

type ApiEnvelope<T> = {
  code?: number;
  message?: string;
  data: T;
};

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

export const systemAPI = {
  /**
   * 获取系统状态信息
   */
  getSystemStatus: async (): Promise<SystemInfo | null> => {
    const response = await request.get<SystemInfo | ApiEnvelope<SystemInfo>>('/system/status');
    return unwrapResponse<SystemInfo>(response);
  },

  /**
   * 获取系统性能指标
   */
  getSystemMetrics: () =>
    request.get<SystemMetrics>('/system/metrics'),

  /**
   * 获取系统健康检查
   */
  getHealthCheck: () =>
    request.get<SystemHealth>('/health'),

  /**
   * 获取系统日志
   */
  getSystemLogs: (params?: {
    level?: string;
    limit?: number;
    offset?: number
  }) =>
    request.get('/system/logs', { params }),

  /**
   * 获取系统配置
   */
  getSystemConfig: () =>
    request.get('/system/config'),

  /**
   * 更新系统配置
   */
  updateSystemConfig: (config: any) =>
    request.post('/system/config', config),

  /**
   * 获取系统监控数据
   */
  getMonitorData: () =>
    request.get('/monitor/metrics'),

  /**
   * 获取组件状态
   */
  getComponentStatus: () =>
    request.get('/monitor/components'),
};

export default systemAPI;
