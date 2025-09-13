/**
 * 系统配置相关API
 * 包括数据库连接、数据源配置、系统模块管理
 */
import request from '@/api/request'
import { extractData, logApiResponse } from '@/utils/apiResponse'

// ==================== 数据库连接管理 ====================

/**
 * 获取所有数据库连接
 */
export function fetchDatabaseConnections() {
  console.log('[systemConfig.js] 调用 fetchDatabaseConnections API')
  console.log('  URL: /database/status')
  console.log('  使用的axios实例:', request.defaults?.baseURL || '未设置baseURL')
  return request({
    url: '/database/status',
    method: 'get'
  }).then(res => {
    logApiResponse('fetchDatabaseConnections', res)
    const statusData = extractData(res)
    // 将状态数据转换为连接列表格式
    const connections = []
    if (statusData && statusData.config) {
      connections.push({
        id: 1,
        name: '主数据库',
        type: statusData.config.type || 'postgresql',
        host: statusData.config.host,
        port: statusData.config.port,
        database: statusData.config.database,
        username: statusData.config.username,
        isDefault: true,
        connected: statusData.connected || false,
        status: statusData.connection_status || 'disconnected'
      })
    }
    return connections
  }).catch(err => {
    console.error('[systemConfig.js] fetchDatabaseConnections 错误:', err)
    console.error('  请求URL:', err.config?.url)
    console.error('  完整URL:', err.config?.baseURL + err.config?.url)
    throw err
  })
}

/**
 * 创建数据库连接
 * @param {object} connection - 连接配置
 */
export function createDatabaseConnection(connection) {
  return request({
    url: '/database/connect',
    method: 'post',
    data: connection
  })
}

/**
 * 更新数据库连接
 * @param {number} id - 连接ID
 * @param {object} connection - 连接配置
 */
export function updateDatabaseConnection(id, connection) {
  return request({
    url: '/database/reconnect',
    method: 'post',
    data: connection
  })
}

/**
 * 删除数据库连接
 * @param {number} id - 连接ID
 */
export function deleteDatabaseConnection(id) {
  return request({
    url: '/database/disconnect',
    method: 'post'
  })
}

/**
 * 测试数据库连接
 * @param {object} connection - 连接配置
 */
export function testDatabaseConnection(connection) {
  return request({
    url: '/database/connect',
    method: 'post',
    data: connection
  })
}

// ==================== 数据源配置管理 ====================

/**
 * 获取所有数据源配置
 */
export function fetchDataSources() {
  console.log('[systemConfig.js] 调用 fetchDataSources API')
  console.log('  URL: /data-sources/list')
  return request({
    url: '/data-sources/list',
    method: 'get'
  }).then(res => {
    logApiResponse('fetchDataSources', res)
    return extractData(res)
  }).catch(err => {
    console.error('[systemConfig.js] fetchDataSources 错误:', err)
    throw err
  })
}

/**
 * 获取数据源配置详情
 * @param {number} id - 数据源ID
 */
export function fetchDataSourceDetail(id) {
  return request({
    url: `/data-source/${id}`,
    method: 'get'
  })
}

/**
 * 创建数据源
 * @param {object} dataSource - 数据源配置
 */
export function createDataSource(dataSource) {
  return request({
    url: '/data-source',
    method: 'post',
    data: dataSource
  })
}

/**
 * 更新数据源
 * @param {number} id - 数据源ID
 * @param {object} dataSource - 数据源配置
 */
export function updateDataSource(id, dataSource) {
  return request({
    url: `/data-source/${id}`,
    method: 'put',
    data: dataSource
  })
}

/**
 * 删除数据源
 * @param {number} id - 数据源ID
 */
export function deleteDataSource(id) {
  return request({
    url: `/data-source/${id}`,
    method: 'delete'
  })
}

/**
 * 测试数据源连接
 * @param {object} dataSource - 数据源配置
 */
export function testDataSource(dataSource) {
  return request({
    url: '/data-source/test',
    method: 'post',
    data: dataSource
  })
}

/**
 * 切换数据源启用状态
 * @param {number} id - 数据源ID
 * @param {boolean} enabled - 是否启用
 */
export function toggleDataSource(id, enabled) {
  return request({
    url: `/data-source/${id}/toggle`,
    method: 'patch',
    data: { enabled }
  })
}

/**
 * 获取数据源健康状态
 */
export function fetchDataSourceHealth() {
  console.log('[systemConfig.js] 调用 fetchDataSourceHealth API')
  console.log('  URL: /data-sources/status')
  return request({
    url: '/data-sources/status',
    method: 'get'
  }).then(res => {
    logApiResponse('fetchDataSourceHealth', res)
    return extractData(res)
  }).catch(err => {
    console.error('[systemConfig.js] fetchDataSourceHealth 错误:', err)
    throw err
  })
}

/**
 * 刷新数据源状态
 */
export function refreshDataSources() {
  return request({
    url: '/data-sources/refresh',
    method: 'post'
  })
}

// ==================== 系统模块管理 ====================

/**
 * 获取所有系统模块
 */
export function fetchSystemModules() {
  return request({
    url: '/system/modules',
    method: 'get'
  })
}

/**
 * 获取模块详情
 * @param {string} moduleId - 模块ID
 */
export function fetchModuleDetail(moduleId) {
  return request({
    url: `/system/modules/${moduleId}`,
    method: 'get'
  })
}

/**
 * 启动模块
 * @param {string} moduleId - 模块ID
 */
export function startModule(moduleId) {
  return request({
    url: `/system/modules/${moduleId}/start`,
    method: 'post'
  })
}

/**
 * 停止模块
 * @param {string} moduleId - 模块ID
 */
export function stopModule(moduleId) {
  return request({
    url: `/system/modules/${moduleId}/stop`,
    method: 'post'
  })
}

/**
 * 重启模块
 * @param {string} moduleId - 模块ID
 */
export function restartModule(moduleId) {
  return request({
    url: `/system/modules/${moduleId}/restart`,
    method: 'post'
  })
}

/**
 * 更新模块配置
 * @param {string} moduleId - 模块ID
 * @param {object} config - 模块配置
 */
export function updateModuleConfig(moduleId, config) {
  return request({
    url: `/system/modules/${moduleId}/config`,
    method: 'put',
    data: config
  })
}

/**
 * 设置模块自动启动
 * @param {string} moduleId - 模块ID
 * @param {boolean} autoStart - 是否自动启动
 */
export function setModuleAutoStart(moduleId, autoStart) {
  return request({
    url: `/system/modules/${moduleId}/auto-start`,
    method: 'patch',
    data: { autoStart }
  })
}

/**
 * 获取模块日志
 * @param {string} moduleId - 模块ID
 * @param {object} params - 查询参数
 */
export function fetchModuleLogs(moduleId, params = {}) {
  return request({
    url: `/system/modules/${moduleId}/logs`,
    method: 'get',
    params
  })
}

/**
 * 批量操作模块
 * @param {string} action - 操作类型 (start|stop|restart)
 * @param {array} moduleIds - 模块ID列表
 */
export function batchModuleOperation(action, moduleIds) {
  return request({
    url: '/system/modules/batch',
    method: 'post',
    data: { action, moduleIds }
  })
}

// ==================== 系统配置导入导出 ====================

/**
 * 导出系统配置
 */
export function exportSystemConfig() {
  return request({
    url: '/system/config/export',
    method: 'get',
    responseType: 'blob'
  })
}

/**
 * 导入系统配置
 * @param {File} file - 配置文件
 */
export function importSystemConfig(file) {
  const formData = new FormData()
  formData.append('file', file)
  
  return request({
    url: '/system/config/import',
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

/**
 * 保存所有配置
 */
export function saveAllConfig() {
  return request({
    url: '/system/config/save-all',
    method: 'post'
  })
}

// ==================== 使用现有的数据源配置API ====================

/**
 * 获取数据源配置（使用现有API）
 */
export function fetchDataSourceConfig() {
  return request({
    url: '/data-source-config/config',
    method: 'get'
  })
}

/**
 * 更新数据源配置（使用现有API）
 * @param {object} config - 配置对象
 */
export function updateDataSourceConfig(config) {
  return request({
    url: '/data-source-config/update',
    method: 'post',
    data: config
  })
}

/**
 * 获取数据源统计信息
 */
export function fetchDataSourceStats() {
  return request({
    url: '/data-source-config/stats',
    method: 'get'
  })
}

/**
 * 获取数据源预设配置
 */
export function fetchDataSourcePresets() {
  return request({
    url: '/data-source-config/presets',
    method: 'get'
  })
}

/**
 * 应用预设配置
 * @param {string} mode - 预设模式
 */
export function applyDataSourcePreset(mode) {
  return request({
    url: '/data-source-config/preset',
    method: 'post',
    data: { mode }
  })
}