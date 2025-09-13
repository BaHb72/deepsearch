import { request } from '../base'

/**
 * 系统管理 API
 */
export const systemAPI = {
  // 获取系统状态
  getStatus: () => request.get('/system/status'),
  
  // 启动系统
  start: () => request.post('/system/start'),
  
  // 停止系统
  stop: () => request.post('/system/stop'),
  
  // 重启系统
  restart: () => request.post('/system/restart'),
  
  // 获取系统信息
  getInfo: () => request.get('/system/info'),
  
  // 获取系统配置
  getConfig: () => request.get('/system/config'),
  
  // 更新系统配置
  updateConfig: (data) => request.put('/system/config', data),
  
  // 获取系统日志
  getLogs: (params) => request.get('/system/logs', { params }),
  
  // 清理系统日志
  clearLogs: () => request.delete('/system/logs'),
  
  // 获取系统统计
  getStatistics: () => request.get('/system/statistics'),
  
  // 获取系统健康状态
  getHealth: () => request.get('/health'),
  
  // 获取组件状态
  getComponents: () => request.get('/system/components'),
  
  // 控制组件
  controlComponent: (name, action) => 
    request.post(`/system/components/${name}/${action}`),
  
  // 获取系统指标
  getMetrics: (params) => request.get('/system/metrics', { params }),
  
  // 导出系统配置
  exportConfig: () => request.get('/system/config/export', {
    responseType: 'blob',
  }),
  
  // 导入系统配置
  importConfig: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request.post('/system/config/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

/**
 * 系统监控 API
 */
export const monitorAPI = {
  // CPU 使用率
  getCpuUsage: () => request.get('/monitor/cpu'),
  
  // 内存使用情况
  getMemoryUsage: () => request.get('/monitor/memory'),
  
  // 磁盘使用情况
  getDiskUsage: () => request.get('/monitor/disk'),
  
  // 网络流量
  getNetworkTraffic: () => request.get('/monitor/network'),
  
  // 进程信息
  getProcesses: () => request.get('/monitor/processes'),
  
  // 服务状态
  getServices: () => request.get('/monitor/services'),
  
  // 获取告警
  getAlerts: (params) => request.get('/monitor/alerts', { params }),
  
  // 确认告警
  acknowledgeAlert: (id) => request.put(`/monitor/alerts/${id}/acknowledge`),
  
  // 关闭告警
  closeAlert: (id) => request.put(`/monitor/alerts/${id}/close`),
  
  // 获取监控历史
  getHistory: (metric, params) => 
    request.get(`/monitor/history/${metric}`, { params }),
}