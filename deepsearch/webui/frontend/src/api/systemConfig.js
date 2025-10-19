/**
 * 系统配置相关API
 * 包括数据库连接、数据源配置、系统模块管理
 */
import request from '@/api/request'
import {extractData, logApiResponse} from '@/utils/apiResponse'

const isPlainObject = value => value != null && typeof value === 'object' && !Array.isArray(value)

const pickMessage = (...candidates) => {
  for (const candidate of candidates) {
    if (typeof candidate === 'string') {
      const trimmed = candidate.trim()
      if (trimmed) {
        return trimmed
      }
    }
  }
  return undefined
}

const normalizeTestResult = (apiResponse, payload) => {
  const payloadObject = isPlainObject(payload) ? payload : undefined
  const apiResponseObject = isPlainObject(apiResponse) ? apiResponse : undefined

  const successFromPayload = typeof payloadObject?.success === 'boolean'
    ? payloadObject.success
    : undefined
  const successFromApi = typeof apiResponseObject?.success === 'boolean'
    ? apiResponseObject.success
    : undefined

  const success = successFromPayload ?? successFromApi ?? true

  const message = pickMessage(
    payloadObject?.message,
    typeof payload === 'string' ? payload : undefined,
    apiResponseObject?.message,
    success ? '连接测试成功' : '连接测试失败'
  )

  const latency = typeof payloadObject?.latency === 'number'
    ? payloadObject.latency
    : typeof payload === 'number'
      ? payload
      : undefined

  const details = isPlainObject(payloadObject?.details)
    ? payloadObject.details
    : undefined

  const error = success
    ? undefined
    : pickMessage(
        typeof payloadObject?.error === 'string'
          ? payloadObject.error
          : isPlainObject(payloadObject?.error)
            ? payloadObject.error.message ?? payloadObject.error.code
            : undefined,
        typeof apiResponseObject?.error === 'string'
          ? apiResponseObject.error
          : isPlainObject(apiResponseObject?.error)
            ? apiResponseObject.error.message ?? apiResponseObject.error.code
            : undefined
      )

  return {
    success,
    message: message ?? (success ? '连接测试成功' : '连接测试失败'),
    latency,
    error,
    details
  }
}

/**
 * 启用数据库连接
 * @param {number} id - 连接ID
 * @param {object} [options] - 启用选项
 */
export async function activateDatabaseConnection(id, options = {}) {
    const response = await request({
        url: `/system/database/connections/${id}/activate`,
        method: 'post',
        data: options
    })
    const apiResponse = extractData(response)
    logApiResponse('activateDatabaseConnection', apiResponse)
    return extractData(apiResponse)
}

/**
 * 停用数据库连接
 * @param {number} id - 连接ID
 * @param {object} [options] - 停用选项
 */
export async function deactivateDatabaseConnection(id, options = {}) {
    const response = await request({
        url: `/system/database/connections/${id}/deactivate`,
        method: 'post',
        data: options
    })
    const apiResponse = extractData(response)
    logApiResponse('deactivateDatabaseConnection', apiResponse)
    return extractData(apiResponse)
}

// ==================== 数据库连接管理 ====================

/**
 * 获取所有数据库连接
 */
export async function fetchDatabaseConnections(forceRefresh = false) {
  console.log('[systemConfig.js] 调用 fetchDatabaseConnections API')
  console.log('  URL: /system/database/connections')
  console.log('  使用的axios实例:', request.defaults?.baseURL || '未设置baseURL')
  try {
    const response = await request({
      url: '/system/database/connections',
      method: 'get',
      params: forceRefresh ? { refresh: 1 } : undefined
    })
    const apiResponse = extractData(response)
    logApiResponse('fetchDatabaseConnections', apiResponse)
    const payload = extractData(apiResponse)
    if (Array.isArray(payload)) {
      return payload
    }
    if (payload && typeof payload === 'object' && Array.isArray(payload.connections)) {
      return payload.connections
    }
    return []
  } catch (err) {
    console.error('[systemConfig.js] fetchDatabaseConnections 请求失败:', err)
    if (err?.config) {
      const base = err.config.baseURL || ''
      const url = err.config.url || ''
      console.error('  请求URL:', url)
      console.error('  完整URL:', `${base}${url}`)
    }
    throw err
  }
}

/**
 * 创建数据库连接
 * @param {object} connection - 连接配置
 */
export async function createDatabaseConnection(connection) {
  const response = await request({
    url: '/system/database/connections',
    method: 'post',
    data: connection
  })
  const apiResponse = extractData(response)
  logApiResponse('createDatabaseConnection', apiResponse)
  return extractData(apiResponse)
}

/**
 * 更新数据库连接
 * @param {number} id - 连接ID
 * @param {object} connection - 连接配置
 */
export async function updateDatabaseConnection(id, connection) {
  const response = await request({
    url: `/system/database/connections/${id}`,
    method: 'put',
    data: connection
  })
  const apiResponse = extractData(response)
  logApiResponse('updateDatabaseConnection', apiResponse)
  return extractData(apiResponse)
}

/**
 * 删除数据库连接
 * @param {number} id - 连接ID
 */
export async function deleteDatabaseConnection(id) {
  const response = await request({
    url: `/system/database/connections/${id}`,
    method: 'delete'
  })
  const apiResponse = extractData(response)
  logApiResponse('deleteDatabaseConnection', apiResponse)
  return extractData(apiResponse)
}

/**
 * 测试数据库连接
 * @param {object} connection - 连接配置
 */
export async function testDatabaseConnection(connection) {
  try {
    const response = await request({
      url: '/system/database/test',
      method: 'post',
      data: connection
    })
    const apiResponse = extractData(response)
    logApiResponse('testDatabaseConnection', apiResponse)
    const payload = extractData(apiResponse)
    return normalizeTestResult(apiResponse, payload)
  } catch (err) {
    console.error('[systemConfig.js] testDatabaseConnection 请求失败:', err)
    throw err
  }
}

// ==================== 数据源配置管理 ====================

// ==================== 工具函数 ====================
function resolveDataSourceId(input) {
  if (input == null) {
    return ''
  }
  if (typeof input === 'string' || typeof input === 'number') {
    return String(input).trim()
  }
  if (typeof input === 'object') {
    const candidates = [input.id, input.source, input.type, input.name]
    for (const candidate of candidates) {
      if (typeof candidate === 'string' && candidate.trim()) {
        return candidate.trim()
      }
    }
  }
  return ''
}

function buildDataSourceConfigPayload(dataSource = {}) {
  if (!dataSource || typeof dataSource !== 'object') {
    return {}
  }

  const payload = {}
  const {
    enabled,
    priority,
    timeout,
    retry_count,
    retryCount,
    fallbackEnabled,
    fallback_enabled,
    fallbackSources,
    fallback_sources,
    config = {},
    name,
    type,
  } = dataSource

  if (enabled !== undefined) {
    payload.enabled = Boolean(enabled)
  }
  if (priority !== undefined) {
    payload.priority = Number(priority)
  }

  const candidateTimeouts = [timeout, config?.timeout, config?.connection?.timeout]
  const timeoutValue = candidateTimeouts.find(value => value !== undefined && value !== null && value !== '')
  if (timeoutValue !== undefined) {
    const parsed = Number(timeoutValue)
    if (!Number.isNaN(parsed)) {
      payload.timeout = parsed
    }
  }

  const candidateRetries = [retry_count, retryCount, config?.retry_count, config?.retryCount]
  const retryValue = candidateRetries.find(value => value !== undefined && value !== null && value !== '')
  if (retryValue !== undefined) {
    const parsed = Number(retryValue)
    if (!Number.isNaN(parsed)) {
      payload.retry_count = parsed
    }
  }

  const fallbackList = fallback_sources ?? fallbackSources
  if (Array.isArray(fallbackList)) {
    payload.fallback_sources = fallbackList
  }
  const fallbackEnabledValue = fallback_enabled ?? fallbackEnabled
  if (fallbackEnabledValue !== undefined) {
    payload.fallback_enabled = Boolean(fallbackEnabledValue)
  }

  const configPayload = { ...config }
  if (name && configPayload.name == null) {
    configPayload.name = name
  }
  if (type && configPayload.type == null) {
    configPayload.type = type
  }

  for (const key of Object.keys(configPayload)) {
    if (configPayload[key] === undefined) {
      delete configPayload[key]
    }
  }

  if (Object.keys(configPayload).length > 0) {
    payload.config = configPayload
  }

  return payload
}

/**
 * 获取所有数据源配置
 */
export async function fetchDataSources() {
  console.log('[systemConfig.js] 调用 fetchDataSources API')
  console.log('  URL: /data-sources/list')
  try {
    const response = await request({
      url: '/data-sources/list',
      method: 'get'
    })
    const apiResponse = extractData(response)
    logApiResponse('fetchDataSources', apiResponse)
    return extractData(apiResponse)
  } catch (err) {
    console.error('[systemConfig.js] fetchDataSources 错误:', err)
    throw err
  }
}

/**
 * 获取数据源配置详情
 * @param {number} id - 数据源ID
 */
export async function fetchDataSourceDetail(id) {
  const sourceId = resolveDataSourceId(id)
  if (!sourceId) {
    throw new Error('缺少数据源标识，无法获取详情')
  }

  const response = await request({
    url: `/data-sources/config/${encodeURIComponent(sourceId)}`,
    method: 'get'
  })
  const apiResponse = extractData(response)
  logApiResponse('fetchDataSourceDetail', apiResponse)
  return extractData(apiResponse) ?? apiResponse
}


/**
 * 创建数据源
 * @param {object} dataSource - 数据源配置
 */
export async function createDataSource(dataSource) {
  const sourceId = resolveDataSourceId(dataSource)
  if (!sourceId) {
    throw new Error('缺少数据源标识，无法创建数据源')
  }

  const payload = buildDataSourceConfigPayload(dataSource)
  const response = await request({
    url: `/data-sources/config/${encodeURIComponent(sourceId)}`,
    method: 'put',
    data: payload
  })
  const apiResponse = extractData(response)
  logApiResponse('createDataSource', apiResponse)
  return extractData(apiResponse) ?? apiResponse
}


/**
 * 更新数据源
 * @param {number} id - 数据源ID
 * @param {object} dataSource - 数据源配置
 */
export async function updateDataSource(id, dataSource) {
  const sourceId = resolveDataSourceId(id)
  if (!sourceId) {
    throw new Error('缺少数据源标识，无法更新数据源')
  }

  const payload = buildDataSourceConfigPayload(dataSource)
  const response = await request({
    url: `/data-sources/config/${encodeURIComponent(sourceId)}`,
    method: 'put',
    data: payload
  })
  const apiResponse = extractData(response)
  logApiResponse('updateDataSource', apiResponse)
  return extractData(apiResponse) ?? apiResponse
}


/**
 * 删除数据源
 * @param {number} id - 数据源ID
 */
export async function deleteDataSource(id) {
  const sourceId = resolveDataSourceId(id)
  if (!sourceId) {
    throw new Error('缺少数据源标识，无法禁用数据源')
  }

  // 统一通过配置接口执行软删除：禁用数据源并保留其配置
  const response = await request({
    url: `/data-sources/config/${encodeURIComponent(sourceId)}`,
    method: 'put',
    data: { enabled: false }
  })
  const apiResponse = extractData(response)
  logApiResponse('deleteDataSource', apiResponse)
  return extractData(apiResponse) ?? apiResponse
}


/**
 * 测试数据源连接
 * @param {object} dataSource - 数据源配置
 */
export async function testDataSource(dataSource) {
  const sourceId = resolveDataSourceId(dataSource) || dataSource?.type || 'amazingdata'
  const symbol = dataSource?.symbol || dataSource?.config?.symbol || '000001'
  const testType = dataSource?.test_type || dataSource?.testType || 'realtime'
  const normalizedSource = typeof sourceId === 'string' ? sourceId.toLowerCase() : sourceId
  const requestPayload = buildDataSourceConfigPayload(dataSource)
  if (typeof dataSource?.rememberCredential === 'boolean') {
    requestPayload.rememberCredential = dataSource.rememberCredential
  }
  const isLoginTest = normalizedSource === 'amazingdata'

  console.log('[systemConfig.js] 测试数据源:', { sourceId, symbol, testType })

  try {
    const requestConfig = {
      url: `/data-sources/test/${encodeURIComponent(sourceId)}`,
      method: 'post'
    }

    if (!isLoginTest) {
      requestConfig.params = { symbol, test_type: testType }
    }

    if (isLoginTest || Object.keys(requestPayload).length > 0) {
      requestConfig.data = requestPayload
    }

    const response = await request({
      ...requestConfig
    })
    const apiResponse = extractData(response)
    logApiResponse('testDataSource', apiResponse)
    const payload = extractData(apiResponse) ?? apiResponse

    if (payload && typeof payload === 'object') {
      return {
        success: payload.success !== false,
        source: payload.source || sourceId,
        latency_ms: payload.latency_ms ?? payload.latencyMs ?? null,
        data_size: payload.data_size ?? payload.dataSize ?? 0,
        message: payload.message || (payload.success === false ? '测试失败' : '测试成功'),
        data: payload.data ?? payload.result ?? payload
      }
    }

    return {
      success: true,
      source: sourceId,
      latency_ms: null,
      data_size: 0,
      message: '测试完成',
      data: payload
    }
  } catch (err) {
    console.error('[systemConfig.js] 测试数据源失败:', err)
    return {
      success: false,
      source: sourceId,
      message: '测试失败',
      error: err.message || '未知错误',
      latency_ms: 0,
      data_size: 0
    }
  }
}


/**
 * 切换数据源启用状态
 * @param {number} id - 数据源ID
 * @param {boolean} enabled - 是否启用
 */
export function toggleDataSource(id, enabled) {
  const sourceId = resolveDataSourceId(id)
  if (!sourceId) {
    throw new Error('缺少数据源标识，无法切换数据源状态')
  }

  const encodedId = encodeURIComponent(sourceId)
  return request({
    url: `/data-sources/config/${encodedId}`,
    method: 'put',
    data: { enabled }
  })
}

/**
 * 获取数据源健康状态
 */
export async function fetchDataSourceHealth() {
  console.log('[systemConfig.js] 调用 fetchDataSourceHealth API')
  console.log('  URL: /data-sources/status')
  try {
    const response = await request({
      url: '/data-sources/status',
      method: 'get'
    })
    const apiResponse = extractData(response)
    logApiResponse('fetchDataSourceHealth', apiResponse)
    return extractData(apiResponse)
  } catch (err) {
    console.error('[systemConfig.js] fetchDataSourceHealth 错误:', err)
    throw err
  }
}

/**
 * 刷新数据源状态
 */
export async function refreshDataSources() {
  const response = await request({
    url: '/data-sources/cache/refresh',
    method: 'post',
    data: {}
  })
  const apiResponse = extractData(response)
  logApiResponse('refreshDataSources', apiResponse)
  return extractData(apiResponse) ?? apiResponse
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
 * 获取数据源配置（全局API）
 */
export function fetchGlobalDataSourceConfig() {
  return request({
    url: '/data-source-config/config',
    method: 'get'
  }).then(res => {
    logApiResponse('fetchGlobalDataSourceConfig', res)
    return extractData(res) ?? {}
  }).catch(err => {
    console.error('[systemConfig.js] fetchGlobalDataSourceConfig 错误:', err)
    throw err
  })
}

/**
 * 兼容旧命名（已弃用）
 */
export function fetchDataSourceConfig() {
  return fetchGlobalDataSourceConfig()
}

/**
 * 更新数据源配置（全局API）
 * @param {object} config - 配置对象
 */
export async function updateDataSourceConfig(config) {
  try {
    const response = await request({
      url: '/data-source-config/update',
      method: 'post',
      data: config
    })
    logApiResponse('updateDataSourceConfig', response)
    return extractData(response) ?? {}
  } catch (error) {
    console.error('[systemConfig.js] updateDataSourceConfig 错误:', error)
    throw error
  }
}

/**
 * 兼容旧命名（后续逐步移除）
 */
export const updateDataSourceConfigAlt = updateDataSourceConfig

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

