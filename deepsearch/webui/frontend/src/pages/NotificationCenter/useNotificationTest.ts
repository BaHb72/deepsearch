import { useCallback, useMemo, useState } from 'react'
import { App } from 'antd'
import { AxiosError } from 'axios'
import {
  sendNotification,
  type NotificationChannel,
  type NotificationSendPayload,
  type NotificationSendResult,
} from '@/api/notifications'
import {
  TEST_HISTORY_MAX_ITEMS,
  TEST_HISTORY_STORAGE_KEY,
} from './constants'

export interface NotificationTestInput {
  title: string
  content?: string
  channel?: NotificationChannel
  category?: string
  bypassQuota: boolean
}

export interface NotificationTestRecord {
  id: string
  title: string
  content?: string
  channel?: NotificationChannel
  category?: string
  success: boolean
  statusCode?: number
  errorMessage?: string
  createdAt: number
  response?: unknown
}

interface UseNotificationTestResult {
  loading: boolean
  history: NotificationTestRecord[]
  lastRecord: NotificationTestRecord | null
  sendTest: (input: NotificationTestInput) => Promise<NotificationTestRecord>
  clearHistory: () => void
}

const safeParseHistory = (): NotificationTestRecord[] => {
  if (typeof window === 'undefined') {
    return []
  }
  try {
    const raw = window.localStorage.getItem(TEST_HISTORY_STORAGE_KEY)
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      return parsed
        .filter(item => item && typeof item === 'object')
        .slice(0, TEST_HISTORY_MAX_ITEMS)
    }
    return []
  } catch (error) {
    console.warn('[NotificationCenter] 读取测试历史失败', error)
    return []
  }
}

const persistHistory = (items: NotificationTestRecord[]) => {
  if (typeof window === 'undefined') {
    return
  }
  try {
    window.localStorage.setItem(TEST_HISTORY_STORAGE_KEY, JSON.stringify(items))
  } catch (error) {
    console.warn('[NotificationCenter] 持久化测试历史失败', error)
  }
}

const extractErrorMessage = (err: unknown): string => {
  const defaultMessage = '发送测试通知失败'
  if (!err) {
    return defaultMessage
  }
  if ((err as Error).message) {
    const message = (err as Error).message
    if (message) {
      return message
    }
  }
  if ((err as AxiosError).response) {
    const response = (err as AxiosError).response!
    const detail = (response.data as any)?.detail
    if (typeof detail === 'string') {
      return detail
    }
    if (detail && typeof detail === 'object') {
      if (detail.message && typeof detail.message === 'string') {
        return detail.message
      }
      if (detail.error && typeof detail.error === 'string') {
        return detail.error
      }
    }
    if (response.status === 429) {
      return '通知额度已用尽，无法发送测试'
    }
    if (response.status === 400) {
      return '请求参数不合法，请检查标题与渠道配置'
    }
    return response.statusText || defaultMessage
  }
  return defaultMessage
}

export const useNotificationTest = (): UseNotificationTestResult => {
  const { message } = App.useApp()
  const [history, setHistory] = useState<NotificationTestRecord[]>(() => safeParseHistory())
  const [loading, setLoading] = useState(false)

  const appendRecord = useCallback((record: NotificationTestRecord) => {
    setHistory(prev => {
      const next = [record, ...prev].slice(0, TEST_HISTORY_MAX_ITEMS)
      persistHistory(next)
      return next
    })
  }, [])

  const sendTest = useCallback(async (input: NotificationTestInput) => {
    setLoading(true)
    const timestamp = Date.now()
    try {
      const payload: NotificationSendPayload = {
        title: input.title,
        content: input.content,
        channel: input.channel,
        category: input.category,
        bypass_quota: input.bypassQuota,
      }
      const result: NotificationSendResult = await sendNotification(payload)
      const record: NotificationTestRecord = {
        id: `${timestamp}`,
        title: input.title,
        content: input.content,
        channel: result.channel as NotificationChannel,
        category: result.category,
        success: true,
        statusCode: result.status_code,
        response: result.response,
        createdAt: timestamp,
      }
      appendRecord(record)
      message.success('测试通知已发送')
      return record
    } catch (error) {
      const errorMessage = extractErrorMessage(error)
      const axiosError = error as AxiosError
      const statusCode = axiosError.response?.status
      const record: NotificationTestRecord = {
        id: `${timestamp}`,
        title: input.title,
        content: input.content,
        channel: input.channel,
        category: input.category,
        success: false,
        statusCode,
        errorMessage,
        createdAt: timestamp,
      }
      appendRecord(record)
      throw error
    } finally {
      setLoading(false)
    }
  }, [appendRecord, message])

  const clearHistory = useCallback(() => {
    setHistory([])
    persistHistory([])
  }, [])

  const lastRecord = useMemo(() => history[0] || null, [history])

  return {
    loading,
    history,
    lastRecord,
    sendTest,
    clearHistory,
  }
}

export default useNotificationTest
