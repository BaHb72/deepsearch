/**
 * 请求拦截器管理器
 * 管理所有的请求和响应拦截器
 */

import { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { RequestInterceptor, ResponseInterceptor, ErrorInterceptor } from './types'

/**
 * 拦截器管理器
 */
export class RequestInterceptorManager {
  private requestInterceptors: Map<string, RequestInterceptor> = new Map()
  private responseInterceptors: Map<string, ResponseInterceptor> = new Map()
  private errorInterceptors: Map<string, ErrorInterceptor> = new Map()
  
  constructor(private axiosInstance: AxiosInstance) {
    this.setupDefaultInterceptors()
  }
  
  /**
   * 设置默认拦截器
   */
  private setupDefaultInterceptors(): void {
    // 添加默认请求拦截器
    this.addRequestInterceptor('timestamp', (config) => {
      // 添加时间戳防止缓存
      if (config.method === 'get' || config.method === 'GET') {
        config.params = {
          ...config.params,
          _t: Date.now()
        }
      }
      return config
    })
    
    // 添加认证拦截器
    this.addRequestInterceptor('auth', (config) => {
      // TODO: 从状态管理获取 token
      const token = localStorage.getItem('auth_token')
      if (token) {
        config.headers = {
          ...config.headers,
          Authorization: `Bearer ${token}`
        }
      }
      return config
    })
    
    // 添加追踪拦截器
    this.addRequestInterceptor('trace', (config) => {
      // 添加追踪头
      config.headers = {
        ...config.headers,
        'X-Trace-ID': this.generateTraceId()
      }
      return config
    })
  }
  
  /**
   * 添加请求拦截器
   */
  public addRequestInterceptor(name: string, interceptor: RequestInterceptor): void {
    this.requestInterceptors.set(name, interceptor)
    this.rebuildInterceptors()
  }
  
  /**
   * 添加响应拦截器
   */
  public addResponseInterceptor(name: string, interceptor: ResponseInterceptor): void {
    this.responseInterceptors.set(name, interceptor)
    this.rebuildInterceptors()
  }
  
  /**
   * 添加错误拦截器
   */
  public addErrorInterceptor(name: string, interceptor: ErrorInterceptor): void {
    this.errorInterceptors.set(name, interceptor)
    this.rebuildInterceptors()
  }
  
  /**
   * 移除请求拦截器
   */
  public removeRequestInterceptor(name: string): void {
    this.requestInterceptors.delete(name)
    this.rebuildInterceptors()
  }
  
  /**
   * 移除响应拦截器
   */
  public removeResponseInterceptor(name: string): void {
    this.responseInterceptors.delete(name)
    this.rebuildInterceptors()
  }
  
  /**
   * 移除错误拦截器
   */
  public removeErrorInterceptor(name: string): void {
    this.errorInterceptors.delete(name)
    this.rebuildInterceptors()
  }
  
  /**
   * 重建拦截器链
   */
  private rebuildInterceptors(): void {
    // 清除现有拦截器
    this.axiosInstance.interceptors.request.clear()
    this.axiosInstance.interceptors.response.clear()
    
    // 重新添加请求拦截器
    this.axiosInstance.interceptors.request.use(
      async (config: AxiosRequestConfig) => {
        let currentConfig = config
        
        // 按顺序执行所有请求拦截器
        for (const interceptor of this.requestInterceptors.values()) {
          currentConfig = await interceptor(currentConfig)
        }
        
        return currentConfig
      },
      (error) => {
        // 执行错误拦截器
        let currentError = error
        for (const interceptor of this.errorInterceptors.values()) {
          currentError = interceptor(currentError)
        }
        return Promise.reject(currentError)
      }
    )
    
    // 重新添加响应拦截器
    this.axiosInstance.interceptors.response.use(
      async (response: AxiosResponse) => {
        let currentResponse = response
        
        // 按顺序执行所有响应拦截器
        for (const interceptor of this.responseInterceptors.values()) {
          currentResponse = await interceptor(currentResponse)
        }
        
        return currentResponse
      },
      (error) => {
        // 执行错误拦截器
        let currentError = error
        for (const interceptor of this.errorInterceptors.values()) {
          currentError = interceptor(currentError)
        }
        return Promise.reject(currentError)
      }
    )
  }
  
  /**
   * 生成追踪 ID
   */
  private generateTraceId(): string {
    return `trace_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }
  
  /**
   * 获取所有拦截器
   */
  public getInterceptors() {
    return {
      request: Array.from(this.requestInterceptors.keys()),
      response: Array.from(this.responseInterceptors.keys()),
      error: Array.from(this.errorInterceptors.keys())
    }
  }
  
  /**
   * 清除所有拦截器
   */
  public clearAll(): void {
    this.requestInterceptors.clear()
    this.responseInterceptors.clear()
    this.errorInterceptors.clear()
    this.rebuildInterceptors()
  }
}

// axios 拦截器扩展
declare module 'axios' {
  interface AxiosInterceptorManager<V> {
    clear(): void
  }
}

// 实现 clear 方法
if (!('clear' in axios.AxiosInterceptorManager.prototype)) {
  (axios.AxiosInterceptorManager.prototype as any).clear = function() {
    this.handlers = []
  }
}