import { useState, useEffect, useCallback, useRef } from 'react'
import { message } from 'antd'

/**
 * 通用请求 Hook
 * @param {Function} service - API 服务函数
 * @param {Object} options - 配置选项
 * @returns {Object} 请求状态和方法
 */
export const useRequest = (service, options = {}) => {
  const {
    manual = false, // 是否手动触发
    defaultParams = [], // 默认参数
    onSuccess, // 成功回调
    onError, // 失败回调
    onFinally, // 完成回调
    loadingDelay = 0, // loading 延迟显示
    pollingInterval = 0, // 轮询间隔
    retryCount = 0, // 重试次数
    retryInterval = 1000, // 重试间隔
    cacheKey = '', // 缓存键
    cacheTime = 0, // 缓存时间（毫秒）
    refreshDeps = [], // 刷新依赖
    ready = true, // 是否准备好
    debounceWait = 0, // 防抖延迟
    throttleWait = 0, // 节流延迟
  } = options

  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  
  const paramsRef = useRef(defaultParams)
  const countRef = useRef(0)
  const pollingTimerRef = useRef(null)
  const loadingTimerRef = useRef(null)
  const cacheRef = useRef(new Map())
  const debounceTimerRef = useRef(null)
  const throttleLastRunRef = useRef(0)
  const unmountedRef = useRef(false)

  // 清理函数
  const cleanup = useCallback(() => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current)
      pollingTimerRef.current = null
    }
    if (loadingTimerRef.current) {
      clearTimeout(loadingTimerRef.current)
      loadingTimerRef.current = null
    }
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
      debounceTimerRef.current = null
    }
  }, [])

  // 获取缓存
  const getCache = useCallback((key) => {
    const cache = cacheRef.current.get(key)
    if (cache && Date.now() - cache.time < cacheTime) {
      return cache.data
    }
    cacheRef.current.delete(key)
    return null
  }, [cacheTime])

  // 设置缓存
  const setCache = useCallback((key, data) => {
    cacheRef.current.set(key, {
      data,
      time: Date.now(),
    })
  }, [])

  // 执行请求
  const executeRequest = useCallback(async (...args) => {
    if (!ready || unmountedRef.current) return

    // 检查缓存
    if (cacheKey && cacheTime > 0) {
      const cacheData = getCache(cacheKey)
      if (cacheData !== null) {
        setData(cacheData)
        return cacheData
      }
    }

    // 设置 loading 状态
    if (loadingDelay > 0) {
      loadingTimerRef.current = setTimeout(() => {
        if (!unmountedRef.current) {
          setLoading(true)
        }
      }, loadingDelay)
    } else {
      setLoading(true)
    }

    setError(null)
    countRef.current = 0

    const request = async () => {
      try {
        const result = await service(...args)
        
        if (!unmountedRef.current) {
          setData(result)
          setError(null)
          
          // 设置缓存
          if (cacheKey && cacheTime > 0) {
            setCache(cacheKey, result)
          }
          
          // 成功回调
          onSuccess?.(result, args)
        }
        
        return result
      } catch (err) {
        if (!unmountedRef.current) {
          // 重试逻辑
          if (countRef.current < retryCount) {
            countRef.current++
            await new Promise(resolve => setTimeout(resolve, retryInterval))
            return request()
          }
          
          setError(err)
          setData(null)
          
          // 错误回调
          onError?.(err, args)
          
          // 显示错误消息
          if (!options.silent) {
            message.error(err.message || '请求失败')
          }
        }
        
        throw err
      } finally {
        if (!unmountedRef.current) {
          if (loadingTimerRef.current) {
            clearTimeout(loadingTimerRef.current)
          }
          setLoading(false)
          onFinally?.(args)
        }
      }
    }

    return request()
  }, [
    ready,
    service,
    cacheKey,
    cacheTime,
    loadingDelay,
    retryCount,
    retryInterval,
    onSuccess,
    onError,
    onFinally,
    getCache,
    setCache,
    options.silent,
  ])

  // 防抖执行
  const debounceRun = useCallback((...args) => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }
    
    return new Promise((resolve, reject) => {
      debounceTimerRef.current = setTimeout(() => {
        executeRequest(...args).then(resolve).catch(reject)
      }, debounceWait)
    })
  }, [debounceWait, executeRequest])

  // 节流执行
  const throttleRun = useCallback((...args) => {
    const now = Date.now()
    const timeSinceLastRun = now - throttleLastRunRef.current
    
    if (timeSinceLastRun >= throttleWait) {
      throttleLastRunRef.current = now
      return executeRequest(...args)
    }
    
    return Promise.resolve(data)
  }, [throttleWait, executeRequest, data])

  // 运行函数
  const run = useCallback((...args) => {
    paramsRef.current = args
    
    if (debounceWait > 0) {
      return debounceRun(...args)
    }
    
    if (throttleWait > 0) {
      return throttleRun(...args)
    }
    
    return executeRequest(...args)
  }, [debounceWait, throttleWait, debounceRun, throttleRun, executeRequest])

  // 刷新（使用上次参数）
  const refresh = useCallback(() => {
    return run(...paramsRef.current)
  }, [run])

  // 取消请求
  const cancel = useCallback(() => {
    cleanup()
    setLoading(false)
  }, [cleanup])

  // 重置状态
  const reset = useCallback(() => {
    cancel()
    setData(null)
    setError(null)
    countRef.current = 0
  }, [cancel])

  // 修改数据
  const mutate = useCallback((newData) => {
    if (typeof newData === 'function') {
      setData(newData)
    } else {
      setData(newData)
    }
  }, [])

  // 轮询逻辑
  useEffect(() => {
    if (pollingInterval > 0 && !pollingTimerRef.current) {
      pollingTimerRef.current = setInterval(() => {
        refresh()
      }, pollingInterval)
    }
    
    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current)
        pollingTimerRef.current = null
      }
    }
  }, [pollingInterval, refresh])

  // 依赖刷新
  useEffect(() => {
    if (!manual && ready) {
      run(...defaultParams)
    }
  }, [...refreshDeps, ready])

  // 初始化请求
  useEffect(() => {
    if (!manual && ready) {
      run(...defaultParams)
    }
    
    return () => {
      unmountedRef.current = true
      cleanup()
    }
  }, [])

  return {
    data,
    error,
    loading,
    run,
    runAsync: run,
    refresh,
    refreshAsync: refresh,
    cancel,
    reset,
    mutate,
  }
}

/**
 * 分页请求 Hook
 */
export const usePagination = (service, options = {}) => {
  const {
    defaultPageSize = 10,
    defaultCurrent = 1,
    ...restOptions
  } = options

  const [pagination, setPagination] = useState({
    current: defaultCurrent,
    pageSize: defaultPageSize,
    total: 0,
  })

  const result = useRequest(
    async (params = {}) => {
      const { current, pageSize } = pagination
      const res = await service({
        ...params,
        page: current,
        pageSize,
      })
      
      setPagination(prev => ({
        ...prev,
        total: res.total || 0,
      }))
      
      return res
    },
    {
      ...restOptions,
      refreshDeps: [pagination.current, pagination.pageSize],
    }
  )

  const changeCurrent = useCallback((current) => {
    setPagination(prev => ({ ...prev, current }))
  }, [])

  const changePageSize = useCallback((pageSize) => {
    setPagination(prev => ({ ...prev, pageSize, current: 1 }))
  }, [])

  return {
    ...result,
    pagination,
    changeCurrent,
    changePageSize,
  }
}

/**
 * 加载更多 Hook
 */
export const useLoadMore = (service, options = {}) => {
  const {
    defaultPageSize = 10,
    ...restOptions
  } = options

  const [loadingMore, setLoadingMore] = useState(false)
  const [noMore, setNoMore] = useState(false)
  const currentRef = useRef(1)
  
  const result = useRequest(
    async () => {
      const res = await service({
        page: 1,
        pageSize: defaultPageSize,
      })
      
      currentRef.current = 1
      setNoMore((res.list || []).length < defaultPageSize)
      
      return res
    },
    restOptions
  )

  const loadMore = useCallback(async () => {
    if (loadingMore || noMore) return
    
    setLoadingMore(true)
    
    try {
      const res = await service({
        page: currentRef.current + 1,
        pageSize: defaultPageSize,
      })
      
      const list = res.list || []
      
      result.mutate(prev => ({
        ...prev,
        list: [...(prev?.list || []), ...list],
      }))
      
      currentRef.current++
      setNoMore(list.length < defaultPageSize)
    } catch (error) {
      message.error('加载失败')
    } finally {
      setLoadingMore(false)
    }
  }, [loadingMore, noMore, service, defaultPageSize, result])

  return {
    ...result,
    loadMore,
    loadingMore,
    noMore,
  }
}