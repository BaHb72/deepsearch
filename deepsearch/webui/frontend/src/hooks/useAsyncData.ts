import { useState, useEffect, useCallback, useRef } from 'react'
import { message } from 'antd'

/**
 * 异步数据状态
 */
export interface AsyncDataState<T> {
  data: T | null
  loading: boolean
  error: Error | null
  initialized: boolean
}

/**
 * 异步数据 Hook 选项
 */
export interface UseAsyncDataOptions {
  /** 是否立即执行 */
  immediate?: boolean
  /** 成功回调 */
  onSuccess?: (data: any) => void
  /** 失败回调 */
  onError?: (error: Error) => void
  /** 是否显示错误消息 */
  showError?: boolean
  /** 是否显示成功消息 */
  showSuccess?: boolean | string
  /** 成功消息文本 */
  successMessage?: string
  /** 轮询间隔（毫秒） */
  pollingInterval?: number
  /** 重试次数 */
  retryCount?: number
  /** 重试延迟（毫秒） */
  retryDelay?: number
}

/**
 * 异步数据 Hook 返回值
 */
export interface UseAsyncDataReturn<T> {
  data: T | null
  loading: boolean
  error: Error | null
  initialized: boolean
  execute: (...args: any[]) => Promise<T | null>
  refresh: () => Promise<T | null>
  reset: () => void
  setData: (data: T | null) => void
}

/**
 * 通用的异步数据获取 Hook
 * 处理加载状态、错误处理、重试、轮询等常见场景
 * 
 * @example
 * ```tsx
 * // 基础用法
 * const { data, loading, error, refresh } = useAsyncData(
 *   fetchUserData,
 *   { immediate: true }
 * )
 * 
 * // 带参数的异步函数
 * const { data, execute } = useAsyncData(
 *   (id: string) => fetchUserById(id),
 *   { immediate: false }
 * )
 * await execute('user-123')
 * 
 * // 轮询数据
 * const { data } = useAsyncData(
 *   fetchSystemStatus,
 *   { pollingInterval: 5000 }
 * )
 * ```
 */
export const useAsyncData = <T = any>(
  asyncFunction: (...args: any[]) => Promise<T>,
  options: UseAsyncDataOptions = {}
): UseAsyncDataReturn<T> => {
  const {
    immediate = true,
    onSuccess,
    onError,
    showError = true,
    showSuccess = false,
    successMessage = '操作成功',
    pollingInterval,
    retryCount = 0,
    retryDelay = 1000
  } = options

  const [state, setState] = useState<AsyncDataState<T>>({
    data: null,
    loading: false,
    error: null,
    initialized: false
  })

  const mountedRef = useRef(true)
  const pollingTimerRef = useRef<NodeJS.Timeout>()
  const retryCountRef = useRef(0)
  const lastArgsRef = useRef<any[]>([])

  /**
   * 执行异步函数
   */
  const execute = useCallback(async (...args: any[]): Promise<T | null> => {
    // 保存参数供 refresh 使用
    lastArgsRef.current = args

    // 设置加载状态
    setState(prev => ({ ...prev, loading: true, error: null }))

    try {
      const result = await asyncFunction(...args)

      if (!mountedRef.current) return null

      // 更新状态
      setState({
        data: result,
        loading: false,
        error: null,
        initialized: true
      })

      // 成功回调
      onSuccess?.(result)

      // 显示成功消息
      if (showSuccess) {
        const msg = typeof showSuccess === 'string' ? showSuccess : successMessage
        message.success(msg)
      }

      // 重置重试计数
      retryCountRef.current = 0

      return result
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err))

      if (!mountedRef.current) return null

      // 更新错误状态
      setState(prev => ({
        ...prev,
        loading: false,
        error,
        initialized: true
      }))

      // 错误回调
      onError?.(error)

      // 显示错误消息
      if (showError) {
        // 特殊处理503错误
        if (error.message?.includes('503') || error.message?.includes('系统未初始化')) {
          message.error('后端服务未就绪，请确保后端已正确启动。运行: python -m deepsearch run --no-frontend')
        } else {
          message.error(error.message || '请求失败')
        }
      }

      // 重试逻辑
      if (retryCountRef.current < retryCount) {
        retryCountRef.current++
        console.log(`重试第 ${retryCountRef.current} 次...`)
        
        // 延迟后重试
        await new Promise(resolve => setTimeout(resolve, retryDelay))
        
        if (mountedRef.current) {
          return execute(...args)
        }
      }

      return null
    }
  }, [asyncFunction, onSuccess, onError, showError, showSuccess, successMessage, retryCount, retryDelay])

  /**
   * 刷新数据（使用上次的参数）
   */
  const refresh = useCallback(() => {
    return execute(...lastArgsRef.current)
  }, [execute])

  /**
   * 重置状态
   */
  const reset = useCallback(() => {
    setState({
      data: null,
      loading: false,
      error: null,
      initialized: false
    })
    retryCountRef.current = 0
  }, [])

  /**
   * 手动设置数据
   */
  const setData = useCallback((data: T | null) => {
    setState(prev => ({ ...prev, data }))
  }, [])

  // 立即执行
  useEffect(() => {
    if (immediate && !state.initialized) {
      execute()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [immediate]) // 只依赖 immediate，避免循环

  // 轮询
  useEffect(() => {
    if (pollingInterval && state.initialized && !state.error) {
      pollingTimerRef.current = setInterval(() => {
        refresh()
      }, pollingInterval)

      return () => {
        if (pollingTimerRef.current) {
          clearInterval(pollingTimerRef.current)
        }
      }
    }
  }, [pollingInterval, state.initialized, state.error, refresh])

  // 清理
  useEffect(() => {
    return () => {
      mountedRef.current = false
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current)
      }
    }
  }, [])

  return {
    data: state.data,
    loading: state.loading,
    error: state.error,
    initialized: state.initialized,
    execute,
    refresh,
    reset,
    setData
  }
}

/**
 * 带缓存的异步数据 Hook
 * 在指定时间内返回缓存数据，避免重复请求
 */
export const useCachedAsyncData = <T = any>(
  key: string,
  asyncFunction: (...args: any[]) => Promise<T>,
  options: UseAsyncDataOptions & { cacheTime?: number } = {}
): UseAsyncDataReturn<T> => {
  const { cacheTime = 5 * 60 * 1000, ...restOptions } = options // 默认缓存 5 分钟
  
  const cacheRef = useRef<{ data: T | null; timestamp: number }>()
  
  const wrappedFunction = useCallback(async (...args: any[]) => {
    // 检查缓存
    if (cacheRef.current) {
      const { data, timestamp } = cacheRef.current
      if (Date.now() - timestamp < cacheTime) {
        console.log(`使用缓存数据: ${key}`)
        return data as T
      }
    }
    
    // 获取新数据
    const result = await asyncFunction(...args)
    
    // 更新缓存
    cacheRef.current = {
      data: result,
      timestamp: Date.now()
    }
    
    return result
  }, [asyncFunction, cacheTime, key])
  
  return useAsyncData(wrappedFunction, restOptions)
}

export default useAsyncData