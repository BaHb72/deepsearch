import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { App } from 'antd'
import dayjs from 'dayjs'
import {
  fetchNotificationQuotas,
  resetNotificationQuotas,
  type NotificationChannel,
} from '@/api/notifications'
import { QUOTA_AUTO_REFRESH_INTERVAL } from './constants'

export interface QuotaRow {
  id: string
  category: string
  channel: NotificationChannel
  current: number
  max?: number | null
  remaining?: number | null
  windowSeconds?: number
  resetSeconds?: number
  expiresAt?: number
  resetEta?: string | null
}

interface UseNotificationQuotaOptions {
  enabled: boolean
}

interface UseNotificationQuotaResult {
  quotas: QuotaRow[]
  loading: boolean
  autoRefresh: boolean
  lastUpdated?: number
  setAutoRefresh: (value: boolean) => void
  refresh: () => Promise<void>
  reset: () => Promise<void>
}

const computeResetEta = (detail: {
  reset_seconds?: number | null
  window_seconds?: number | null
  expires_at?: number | null
}) => {
  if (detail.reset_seconds && detail.reset_seconds > 0) {
    return dayjs().add(detail.reset_seconds, 'second').format('YYYY-MM-DD HH:mm:ss')
  }
  if (detail.expires_at) {
    return dayjs(detail.expires_at * 1000).format('YYYY-MM-DD HH:mm:ss')
  }
  if (detail.window_seconds && detail.window_seconds > 0) {
    return dayjs().add(detail.window_seconds, 'second').format('YYYY-MM-DD HH:mm:ss')
  }
  return null
}

export const useNotificationQuota = ({ enabled }: UseNotificationQuotaOptions): UseNotificationQuotaResult => {
  const { message } = App.useApp()
  const [quotas, setQuotas] = useState<QuotaRow[]>([])
  const [loading, setLoading] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<number | undefined>(undefined)
  const timerRef = useRef<number | null>(null)

  const disposeTimer = useCallback(() => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const refresh = useCallback(async () => {
    if (!enabled) {
      setQuotas([])
      setLastUpdated(undefined)
      return
    }
    setLoading(true)
    try {
      const response = await fetchNotificationQuotas()
      const rows: QuotaRow[] = []
      const data = response?.data ?? {}
      Object.entries(data).forEach(([category, channels]) => {
        Object.entries(channels as Record<string, any>).forEach(([channelKey, detail]) => {
          const typedChannel = channelKey as NotificationChannel
          const current = detail?.current ?? 0
          const max = detail?.max_per_window ?? null
          const remaining =
            detail?.remaining ?? (typeof max === 'number' && max >= 0 ? Math.max(max - current, 0) : null)
          rows.push({
            id: `${category}-${channelKey}`,
            category,
            channel: typedChannel,
            current,
            max,
            remaining,
            windowSeconds: detail?.window_seconds ?? undefined,
            resetSeconds: detail?.reset_seconds ?? undefined,
            expiresAt: detail?.expires_at ?? undefined,
            resetEta: computeResetEta(detail || {}),
          })
        })
      })
      setQuotas(rows)
      setLastUpdated(Date.now())
    } catch (error) {
      console.error('[NotificationCenter] 获取通知额度失败', error)
      message.error('获取通知额度失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [enabled, message])

  const reset = useCallback(async () => {
    if (!enabled) {
      return
    }
    setLoading(true)
    try {
      await resetNotificationQuotas()
      message.success('通知额度已重置')
      await refresh()
    } catch (error) {
      console.error('[NotificationCenter] 重置通知额度失败', error)
      message.error('重置通知额度失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [enabled, message, refresh])

  useEffect(() => {
    if (enabled) {
      void refresh()
    } else {
      setQuotas([])
      setLastUpdated(undefined)
    }
    return () => {
      disposeTimer()
    }
  }, [enabled, refresh, disposeTimer])

  useEffect(() => {
    disposeTimer()
    if (!enabled || !autoRefresh) {
      return undefined
    }
    timerRef.current = window.setInterval(() => {
      void refresh()
    }, QUOTA_AUTO_REFRESH_INTERVAL)
    return () => {
      disposeTimer()
    }
  }, [autoRefresh, disposeTimer, enabled, refresh])

  useEffect(() => () => disposeTimer(), [disposeTimer])

  return useMemo(() => ({
    quotas,
    loading,
    autoRefresh,
    lastUpdated,
    setAutoRefresh,
    refresh,
    reset,
  }), [autoRefresh, lastUpdated, loading, quotas, refresh, reset])
}

export default useNotificationQuota
