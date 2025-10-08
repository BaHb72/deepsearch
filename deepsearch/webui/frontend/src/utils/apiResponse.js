/**
 * API响应处理工具
 * 统一处理不同格式的后端响应
 */

import logger from '@/utils/logger'

const apiResponseLogger = logger.child('utils:api-response')

/**
 * 处理API响应，自动解包APIResponse格式
 * @param {Object} response - API响应
 * @returns {any} 解包后的数据
 */
export function extractData(response) {
  // 如果响应是null或undefined，直接返回
  if (response == null) {
    return null
  }

  // 检查是否是APIResponse格式 (包含success字段)
  if (typeof response === 'object' && 'success' in response) {
    // APIResponse格式
    if (response.success) {
      // 成功响应，返回data字段
      return response.data
    } else {
      // 失败响应，抛出错误
      const error = new Error(response.error?.message || response.message || '请求失败')
      error.code = response.error?.code || 'UNKNOWN_ERROR'
      error.details = response.error?.details || {}
      throw error
    }
  }

  // 检查是否是包含data字段的简单响应
  if (typeof response === 'object' && 'data' in response && !('success' in response)) {
    return response.data
  }

  // 其他情况，直接返回原始响应
  return response
}

/**
 * 包装API调用，自动处理响应格式
 * @param {Function} apiCall - API调用函数
 * @returns {Function} 包装后的函数
 */
export function wrapApiCall(apiCall) {
  return async (...args) => {
    try {
      const response = await apiCall(...args)
      return extractData(response)
    } catch (error) {
      // 如果是axios错误，提取响应数据
      if (error.response?.data) {
        const responseData = error.response.data
        if (typeof responseData === 'object' && 'success' in responseData && !responseData.success) {
          // 是APIResponse格式的错误
          const apiError = new Error(responseData.error?.message || responseData.message || '请求失败')
          apiError.code = responseData.error?.code || 'API_ERROR'
          apiError.details = responseData.error?.details || {}
          throw apiError
        }
      }
      throw error
    }
  }
}

/**
 * 检查响应是否为成功的APIResponse
 * @param {Object} response - API响应
 * @returns {boolean} 是否成功
 */
export function isSuccessResponse(response) {
  return response && typeof response === 'object' && response.success === true
}

/**
 * 检查响应是否为错误的APIResponse
 * @param {Object} response - API响应
 * @returns {boolean} 是否错误
 */
export function isErrorResponse(response) {
  return response && typeof response === 'object' && response.success === false
}

/**
 * 获取响应的错误信息
 * @param {Object} response - API响应或错误对象
 * @returns {string} 错误信息
 */
export function getErrorMessage(response) {
  if (!response) {
    return '未知错误'
  }

  // 检查是否是APIResponse格式的错误
  if (typeof response === 'object' && response.error) {
    return response.error.message || response.error.code || '请求失败'
  }

  // 检查是否有message字段
  if (response.message) {
    return response.message
  }

  // 如果是Error对象
  if (response instanceof Error) {
    return response.message
  }

  // 如果是字符串
  if (typeof response === 'string') {
    return response
  }

  return '未知错误'
}

/**
 * 格式化API响应日志
 * @param {string} apiName - API名称
 * @param {Object} response - API响应
 */
export function logApiResponse(apiName, response) {
  const timestamp = new Date().toISOString()
  
  if (isSuccessResponse(response)) {
    apiResponseLogger.info(`[${timestamp}] ✅ ${apiName} 成功:`, response.data)
  } else if (isErrorResponse(response)) {
    apiResponseLogger.error(`[${timestamp}] ❌ ${apiName} 失败:`, response.error)
  } else {
    apiResponseLogger.info(`[${timestamp}] 📡 ${apiName} 响应:`, response)
  }
}

export default {
  extractData,
  wrapApiCall,
  isSuccessResponse,
  isErrorResponse,
  getErrorMessage,
  logApiResponse
}