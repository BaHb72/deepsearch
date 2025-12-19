import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { message } from 'antd'

import { marketDataLiveApi, type DataSourceSwitchResponse } from '@/api/marketDataLive'
import { formatDataSourceLabel, normalizeDataSourceList, normalizeDataSourceValue } from '@/utils/dataSource'

type RealtimeSourceState = {
  activeSource: string | null
  availableSources: string[]
  detail: Record<string, unknown> | null
  adapters: Record<string, unknown>
  loading: boolean
  switching: boolean
  error: Error | null
  lastUpdated: string | null
}

interface RealtimeSourceContextValue extends RealtimeSourceState {
  refreshStatus: () => Promise<void>
  switchSource: (
    target: string,
    options?: { silent?: boolean },
  ) => Promise<DataSourceSwitchResponse | null>
}

const initialState: RealtimeSourceState = {
  activeSource: null,
  availableSources: [],
  detail: null,
  adapters: {},
  loading: false,
  switching: false,
  error: null,
  lastUpdated: null,
}

const noopAsync = async (): Promise<void> => { /* noop */ }
const noopSwitchSource = async (): Promise<DataSourceSwitchResponse | null> => null

const RealtimeSourceContext = createContext<RealtimeSourceContextValue>({
  ...initialState,
  refreshStatus: noopAsync,
  switchSource: noopSwitchSource,
})

interface ProviderProps {
  children: React.ReactNode
}

export const RealtimeSourceProvider: React.FC<ProviderProps> = ({ children }) => {
  const [state, setState] = useState<RealtimeSourceState>(initialState)
  const mountedRef = useRef(true)
  const switchingLockRef = useRef(false)

  useEffect(() => {
    return () => {
      mountedRef.current = false
    }
  }, [])

  const refreshStatus = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    try {
      const payload = await marketDataLiveApi.getDataSourceStatus()
      if (!mountedRef.current) {
        return
      }
      const normalizedActive = normalizeDataSourceValue(payload?.active ?? null)
      const normalizedAvailable = normalizeDataSourceList(payload?.available ?? [])
      setState({
        activeSource: normalizedActive,
        availableSources: normalizedAvailable,
        detail: (payload?.detail as Record<string, unknown>) ?? null,
        adapters: (payload?.adapters as Record<string, unknown>) ?? {},
        loading: false,
        switching: false,
        error: null,
        lastUpdated: payload?.timestamp ?? new Date().toISOString(),
      })
    } catch (error) {
      if (!mountedRef.current) {
        return
      }
      const normalizedError = error instanceof Error ? error : new Error(String(error))
      setState(prev => ({ ...prev, loading: false, error: normalizedError }))
      throw normalizedError
    }
  }, [])

  const switchSource = useCallback(
    async (target: string, options?: { silent?: boolean }) => {
      const normalized = normalizeDataSourceValue(target)
      if (!normalized || switchingLockRef.current) {
        return null
      }

      switchingLockRef.current = true
      setState(prev => ({ ...prev, switching: true, error: null }))

      try {
        const response = await marketDataLiveApi.switchDataSource(normalized)
        if (!options?.silent) {
          const label = formatDataSourceLabel(response.active ?? normalized)
          message.success(`已切换到 ${label}`)
        }
        await refreshStatus()
        return response
      } catch (error) {
        const normalizedError = error instanceof Error ? error : new Error(String(error))
        if (!options?.silent) {
          const text = normalizedError.message || '切换数据源失败，请稍后重试'
          message.error(text)
        }
        if (mountedRef.current) {
          setState(prev => ({ ...prev, switching: false, error: normalizedError }))
        }
        throw normalizedError
      } finally {
        switchingLockRef.current = false
      }
    },
    [refreshStatus],
  )

  useEffect(() => {
    refreshStatus().catch(() => undefined)
  }, [refreshStatus])

  const contextValue = useMemo<RealtimeSourceContextValue>(
    () => ({
      ...state,
      refreshStatus,
      switchSource,
    }),
    [state, refreshStatus, switchSource],
  )

  return (
    <RealtimeSourceContext.Provider value={contextValue}>
      {children}
    </RealtimeSourceContext.Provider>
  )
}

export const useRealtimeSource = (): RealtimeSourceContextValue => {
  return useContext(RealtimeSourceContext)
}
