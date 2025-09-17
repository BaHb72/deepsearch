/**
 * 系统API客户端
 * 提供系统状态、监控和资源使用情况的真实数据
 */
import request from './request';

export interface SystemInfo {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_in: number;
  network_out: number;
  process_count: number;
  uptime: number;
  timestamp: number;
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
  getSystemStatus: () =>
    request.get<SystemInfo>('/system/status'),

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