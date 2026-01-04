import axios from 'axios'
import { message, notification } from 'antd'
import { storage } from '@/utils/storage'

// API 响应码
export const API_CODE = {
  SUCCESS: 0,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  SERVER_ERROR: 500,
  TIMEOUT: 408,
  NETWORK_ERROR: -1,
}

// 创建 axios 实例
const createRequest = (config = {}) => {
  const instance = axios.create({
      baseURL: (import.meta.env.VITE_API_BASE_URL || '').trim() || '/api',
    timeout: config.timeout || 30000,
    headers: {
      'Content-Type': 'application/json',
      ...config.headers,
    },
    ...config,
  })

  // 请求拦截器
  instance.interceptors.request.use(
    (config) => {
      // 添加 token
      const token = storage.get('token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }

      // 添加时间戳防止缓存
      if (config.method === 'get') {
        config.params = {
          ...config.params,
          _t: Date.now(),
        }
      }

      // 请求开始时间（用于计算请求耗时）
      config.metadata = { startTime: Date.now() }

      return config
    },
    (error) => {
      console.error('Request error:', error)
      return Promise.reject(error)
    }
  )

  // 响应拦截器
  instance.interceptors.response.use(
    (response) => {
      // 计算请求耗时
      const duration = Date.now() - response.config.metadata.startTime
      console.log(`[API] ${response.config.method.toUpperCase()} ${response.config.url} - ${duration}ms`)

      const res = response.data

      // 处理不同的响应格式
      if (res.code !== undefined) {
        // 标准格式 { code, data, message }
        if (res.code === API_CODE.SUCCESS) {
          return res.data
        } else {
          handleError(res.code, res.message || '请求失败')
          return Promise.reject(new Error(res.message || '请求失败'))
        }
      }

      // 直接返回数据
      return res
    },
    (error) => {
      // 计算请求耗时
      if (error.config?.metadata) {
        const duration = Date.now() - error.config.metadata.startTime
        console.error(`[API] ${error.config.method.toUpperCase()} ${error.config.url} - ${duration}ms - Error`)
      }

      if (error.response) {
        // 服务器返回错误
        handleHttpError(error.response)
      } else if (error.request) {
        // 请求发送失败
        handleNetworkError(error)
      } else {
        // 其他错误
        message.error(error.message || '请求配置错误')
      }

      return Promise.reject(error)
    }
  )

  return instance
}

// 处理业务错误
const handleError = (code, msg) => {
  switch (code) {
    case API_CODE.UNAUTHORIZED:
      message.error('登录已过期，请重新登录')
      storage.remove('token')
      window.location.href = '/login'
      break
    case API_CODE.FORBIDDEN:
      message.error('没有权限访问该资源')
      break
    case API_CODE.NOT_FOUND:
      message.error('请求的资源不存在')
      break
    default:
      message.error(msg || '请求失败')
  }
}

// 处理 HTTP 错误
const handleHttpError = (response) => {
  const { status, data } = response
  let errorMsg = data?.message || '请求失败'

  switch (status) {
    case 400:
      errorMsg = '请求参数错误'
      break
    case 401:
      errorMsg = '未授权，请重新登录'
      storage.remove('token')
      window.location.href = '/login'
      break
    case 403:
      errorMsg = '拒绝访问'
      break
    case 404:
      errorMsg = '请求地址不存在'
      break
    case 408:
      errorMsg = '请求超时'
      break
    case 500:
      errorMsg = '服务器内部错误'
      break
    case 501:
      errorMsg = '服务未实现'
      break
    case 502:
      errorMsg = '网关错误'
      break
    case 503:
      errorMsg = '服务不可用'
      break
    case 504:
      errorMsg = '网关超时'
      break
    default:
      errorMsg = `请求失败 (${status})`
  }

  message.error(errorMsg)
}

// 处理网络错误
const handleNetworkError = (error) => {
  if (error.code === 'ECONNABORTED') {
    message.error('请求超时，请检查网络连接')
  } else if (error.message === 'Network Error') {
    notification.error({
      message: '网络连接失败',
      description: '请检查网络连接或联系管理员',
      duration: 5,
    })
  } else {
    message.error('网络错误，请稍后重试')
  }
}

// 默认实例
export const request = createRequest()

// WebSocket 实例
export const wsRequest = createRequest({
    baseURL: (import.meta.env.VITE_WS_URL || '').trim() || 'ws://localhost:8000',
})

// 文件上传实例
export const uploadRequest = createRequest({
  headers: {
    'Content-Type': 'multipart/form-data',
  },
  timeout: 60000, // 文件上传超时时间设长一些
})

// 导出创建函数
export default createRequest
