import {useCallback, useEffect, useRef, useState} from 'react'
import {message} from 'antd'
import backendStatus from '@/utils/backendStatus'

type AsyncFunction<Args extends unknown[], T> = (...args: Args) => Promise<T>

export interface AsyncDataState<T> {
  data: T | null
  loading: boolean
  error: Error | null
  initialized: boolean
}

export interface UseAsyncDataOptions<T> {
  immediate?: boolean
    onSuccess?: (data: T) => void
  onError?: (error: Error) => void
  showError?: boolean
  showSuccess?: boolean | string
  successMessage?: string
  pollingInterval?: number
  retryCount?: number
  retryDelay?: number
}

export interface UseAsyncDataReturn<T, Args extends unknown[]> {
  data: T | null
  loading: boolean
  error: Error | null
  initialized: boolean
    execute: (...args: Args) => Promise<T | null>
  refresh: () => Promise<T | null>
  reset: () => void
  setData: (data: T | null) => void
}

const DEFAULT_SUCCESS_MESSAGE = '操作成功'
const DEFAULT_ERROR_MESSAGE = '请求失败，请稍后重试'

const BACKEND_ERROR_SIGNATURES = ['服务不可用', 'BACKEND_UNAVAILABLE', 'ECONNREFUSED']

const sleep = (duration: number) =>
    new Promise<void>((resolve) => {
        setTimeout(resolve, duration)
    })

function shouldRetry(error: Error, attempt: number, retryCount: number): boolean {
    if (attempt >= retryCount) {
        return false
    }
    return !error.message.includes('AbortError')
}

function isBackendUnavailable(error: Error | null): boolean {
    if (!error) {
        return false
    }
    return BACKEND_ERROR_SIGNATURES.some((keyword) => error.message.includes(keyword))
}

export function useAsyncData<T, Args extends unknown[] = []>(
    asyncFunction: AsyncFunction<Args, T>,
    options: UseAsyncDataOptions<T> = {}
): UseAsyncDataReturn<T, Args> {
  const {
    immediate = true,
    onSuccess,
    onError,
    showError = true,
    showSuccess = false,
      successMessage = DEFAULT_SUCCESS_MESSAGE,
    pollingInterval,
    retryCount = 0,
      retryDelay = 1000,
  } = options

  const [state, setState] = useState<AsyncDataState<T>>({
    data: null,
    loading: false,
    error: null,
      initialized: false,
  })

  const mountedRef = useRef(true)
    const pollingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const lastArgsRef = useRef<Args>([] as unknown as Args)
    const abortControllerRef = useRef<AbortController | null>(null)

    const execute = useCallback(
        async (...args: Args): Promise<T | null> => {
            lastArgsRef.current = args

            if (abortControllerRef.current) {
                abortControllerRef.current.abort()
            }

            const controller = new AbortController()
            abortControllerRef.current = controller

            setState((prev) => ({
                ...prev,
                loading: true,
                error: null,
            }))

            let attempt = 0

            while (attempt <= retryCount) {
                try {
                    const result = await asyncFunction(...args)

                    if (!mountedRef.current || controller.signal.aborted) {
                        return null
                    }

                    setState({
                        data: result,
                        loading: false,
                        error: null,
                        initialized: true,
                    })

                    if (showSuccess) {
                        const content = typeof showSuccess === 'string' ? showSuccess : successMessage
                        message.success(content)
                    }

                    onSuccess?.(result)
                    return result
                } catch (err) {
                    const error = err instanceof Error ? err : new Error(String(err))

                    if (!mountedRef.current || controller.signal.aborted) {
                        return null
                    }

                    attempt += 1

                    if (shouldRetry(error, attempt, retryCount)) {
                        if (retryDelay > 0) {
                            await sleep(retryDelay)
                        }
                        continue
                    }

                    setState({
                        data: null,
                        loading: false,
                        error,
                        initialized: true,
                    })

                    if (showError) {
                        message.error(error.message || DEFAULT_ERROR_MESSAGE)
                    }

                    onError?.(error)
                    return null
        }
      }

      return null
        },
        [
            asyncFunction,
            onError,
            onSuccess,
            retryCount,
            retryDelay,
            showError,
            showSuccess,
            successMessage,
        ]
    )

    const refresh = useCallback(async (): Promise<T | null> => {
    return execute(...lastArgsRef.current)
  }, [execute])

  const reset = useCallback(() => {
    setState({
      data: null,
      loading: false,
      error: null,
        initialized: false,
    })
  }, [])

  const setData = useCallback((data: T | null) => {
      setState((prev) => ({...prev, data}))
  }, [])

  useEffect(() => {
    if (immediate && !state.initialized) {
        void execute(...lastArgsRef.current)
    }
  }, [immediate, state.initialized, execute])

  useEffect(() => {
    if (pollingInterval && state.initialized && !state.error) {
      pollingTimerRef.current = setInterval(() => {
          void refresh()
      }, pollingInterval)

      return () => {
        if (pollingTimerRef.current) {
          clearInterval(pollingTimerRef.current)
        }
      }
    }

      return undefined
  }, [pollingInterval, state.initialized, state.error, refresh])

  useEffect(() => {
    const handleBackendStatusChange = (available: boolean) => {
        if (available && isBackendUnavailable(state.error)) {
            void refresh()
      }
    }

    backendStatus.addListener(handleBackendStatusChange)
    return () => {
      backendStatus.removeListener(handleBackendStatusChange)
    }
  }, [state.error, refresh])

  useEffect(() => {
    return () => {
      mountedRef.current = false

      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }

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
      setData,
  }
}

export function useCachedAsyncData<T, Args extends unknown[] = []>(
  key: string,
  asyncFunction: AsyncFunction<Args, T>,
  options: UseAsyncDataOptions<T> & { cacheTime?: number } = {}
): UseAsyncDataReturn<T, Args> {
    const {cacheTime = 5 * 60 * 1000, ...restOptions} = options

    const cacheRef = useRef<{ data: T; timestamp: number } | null>(null)

    const wrappedFunction = useCallback(
        async (...args: Args): Promise<T> => {
            if (cacheRef.current && Date.now() - cacheRef.current.timestamp < cacheTime) {
                console.debug(`[useCachedAsyncData] 使用缓存数据: ${key}`)
                return cacheRef.current.data
            }

            const result = await asyncFunction(...args)
            cacheRef.current = {
                data: result,
                timestamp: Date.now(),
            }
            return result
        },
        [asyncFunction, cacheTime, key]
    )

  return useAsyncData(wrappedFunction, restOptions)
}

export default useAsyncData
