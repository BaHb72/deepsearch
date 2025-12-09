import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios'
import { message } from 'antd'

// 请求响应接口
interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
  success?: boolean
}

// 创建axios实例
const service: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  }
})

// 请求拦截器
service.interceptors.request.use(
  (config: AxiosRequestConfig) => {
    // 添加token等认证信息
    const token = localStorage.getItem('token')
    if (token && config.headers) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    
    // 添加时间戳防止缓存
    if (config.method === 'get') {
      config.params = {
        ...config.params,
        _t: Date.now()
      }
    }
    
    return config
  },
  (error: AxiosError) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const res = response.data
    
    // 如果返回的状态码不是200，则判定为错误
      if (res && typeof (res as ApiResponse).code !== 'undefined') {
          const code = (res as ApiResponse).code
          if (code !== 200 && code !== 0) {
              message.error(res.message || '请求失败')

              // 401: 未登录
              if (code === 401) {
                  // 跳转到登录页面
                  window.location.href = '/login'
              }

              return Promise.reject(new Error(res.message || '请求失败'))
          }
    }
    
    return response
  },
  (error: AxiosError) => {
    console.error('响应错误:', error)
    
    if (error.response) {
      switch (error.response.status) {
        case 401:
          message.error('未授权，请重新登录')
          window.location.href = '/login'
          break
        case 403:
          message.error('拒绝访问')
          break
        case 404:
          message.error('请求地址不存在')
          break
        case 500:
          message.error('服务器内部错误')
          break
        default:
          message.error(error.message || '请求失败')
      }
    } else if (error.request) {
      message.error('网络错误，请检查网络连接')
    } else {
      message.error('请求配置错误')
    }
    
    return Promise.reject(error)
  }
)

// 封装请求方法
class Request {
  // GET请求
  get<T = any>(url: string, params?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    return service.get(url, { params, ...config }).then(res => res.data)
  }
  
  // POST请求
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    return service.post(url, data, config).then(res => res.data)
  }
  
  // PUT请求
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    return service.put(url, data, config).then(res => res.data)
  }
  
  // DELETE请求
  delete<T = any>(url: string, params?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    return service.delete(url, { params, ...config }).then(res => res.data)
  }
  
  // 上传文件
  upload<T = any>(url: string, file: File | Blob, onProgress?: (progress: number) => void): Promise<ApiResponse<T>> {
    const formData = new FormData()
    formData.append('file', file)
    
    return service.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(progress)
        }
      }
    }).then(res => res.data)
  }
  
  // 下载文件
  download(url: string, params?: any, filename?: string): Promise<void> {
    return service.get(url, {
      params,
      responseType: 'blob'
    }).then(response => {
      const blob = new Blob([response.data])
      const link = document.createElement('a')
      link.href = window.URL.createObjectURL(blob)
      link.download = filename || 'download'
      link.click()
      window.URL.revokeObjectURL(link.href)
    })
  }
}

export default new Request()
export { service, ApiResponse }
