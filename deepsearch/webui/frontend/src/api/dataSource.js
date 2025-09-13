/**
 * 数据源相关API
 */
import request from '@/utils/request'

/**
 * 获取数据源能力矩阵
 */
export function fetchDataSourceCapabilities() {
  return request({
    url: '/api/datasource/capabilities/matrix',
    method: 'get'
  })
}

/**
 * 获取指定数据源的能力
 * @param {string} source - 数据源ID
 */
export function fetchSourceCapabilities(source) {
  return request({
    url: `/api/datasource/capabilities/${source}`,
    method: 'get'
  })
}

/**
 * 对比多个数据源的能力
 * @param {string} sources - 逗号分隔的数据源ID列表
 */
export function compareDataSources(sources) {
  return request({
    url: '/api/datasource/capabilities/compare',
    method: 'get',
    params: { sources }
  })
}

/**
 * 根据能力需求推荐数据源
 * @param {string} capability - 能力ID
 * @param {boolean} preferFree - 是否优先推荐免费数据源
 */
export function recommendDataSource(capability, preferFree = false) {
  return request({
    url: '/api/datasource/capabilities/recommend',
    method: 'get',
    params: { 
      capability,
      prefer_free: preferFree
    }
  })
}

/**
 * 检查特定功能在数据源上的可用性
 * @param {string} source - 数据源ID
 * @param {string} feature - 功能/能力ID
 */
export function checkFeatureAvailability(source, feature) {
  return request({
    url: '/api/datasource/capabilities/check',
    method: 'get',
    params: { source, feature }
  })
}

/**
 * 获取数据源监控信息
 * @param {string} source - 数据源ID（可选）
 * @param {string} timeRange - 时间范围（1h, 6h, 24h, 7d）
 */
export function fetchDataSourceMonitor(source = null, timeRange = '1h') {
  const params = { time_range: timeRange }
  if (source) {
    params.source = source
  }
  
  return request({
    url: '/api/datasource/monitor/status',
    method: 'get',
    params
  })
}

/**
 * 获取数据源访问统计
 * @param {string} source - 数据源ID（可选）
 * @param {string} startDate - 开始日期
 * @param {string} endDate - 结束日期
 */
export function fetchAccessStatistics(source = null, startDate = null, endDate = null) {
  const params = {}
  if (source) params.source = source
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  
  return request({
    url: '/api/datasource/monitor/statistics',
    method: 'get',
    params
  })
}

/**
 * 获取数据源健康状态
 */
export function fetchDataSourceHealth() {
  return request({
    url: '/api/datasource/monitor/health',
    method: 'get'
  })
}

/**
 * 获取数据源性能指标
 * @param {string} source - 数据源ID
 */
export function fetchSourcePerformance(source) {
  return request({
    url: `/api/datasource/monitor/performance/${source}`,
    method: 'get'
  })
}

/**
 * 测试数据源连接
 * @param {string} source - 数据源ID
 */
export function testDataSourceConnection(source) {
  return request({
    url: `/api/datasource/test/${source}`,
    method: 'post'
  })
}

/**
 * 切换主数据源
 * @param {string} source - 数据源ID
 */
export function switchPrimarySource(source) {
  return request({
    url: '/api/datasource/switch',
    method: 'post',
    data: { source }
  })
}

/**
 * 获取数据源配置
 * @param {string} source - 数据源ID
 */
export function fetchSourceConfig(source) {
  return request({
    url: `/api/datasource/config/${source}`,
    method: 'get'
  })
}

/**
 * 更新数据源配置
 * @param {string} source - 数据源ID
 * @param {object} config - 配置对象
 */
export function updateSourceConfig(source, config) {
  return request({
    url: `/api/datasource/config/${source}`,
    method: 'put',
    data: config
  })
}

/**
 * 获取数据源访问日志
 * @param {object} params - 查询参数
 */
export function fetchAccessLogs(params = {}) {
  return request({
    url: '/api/datasource/monitor/logs',
    method: 'get',
    params
  })
}

/**
 * 获取数据源推荐
 * @param {array} requiredCapabilities - 所需能力列表
 */
export function getSourceRecommendation(requiredCapabilities) {
  return request({
    url: '/api/datasource/monitor/recommend',
    method: 'post',
    data: { required_capabilities: requiredCapabilities }
  })
}

/**
 * 批量检查功能可用性
 * @param {string} source - 数据源ID
 * @param {array} features - 功能ID列表
 */
export function batchCheckFeatures(source, features) {
  return request({
    url: '/api/datasource/capabilities/batch-check',
    method: 'post',
    data: { source, features }
  })
}

/**
 * 获取能力分类
 */
export function fetchCapabilityCategories() {
  return request({
    url: '/api/datasource/capabilities/categories',
    method: 'get'
  })
}

/**
 * 获取能力矩阵（完整版）
 */
export function fetchCapabilityMatrix() {
  return request({
    url: '/api/datasource/capabilities/matrix',
    method: 'get'
  })
}