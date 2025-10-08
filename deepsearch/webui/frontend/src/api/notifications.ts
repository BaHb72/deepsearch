import request from './request'

export type NotificationChannel = 'wechat' | 'bark'

export interface NotificationCategoryConfigItem {
  name: string
  enabled: boolean
  maxPerWindow: number
  windowSeconds: number
  channels: NotificationChannel[]
}

export interface NotificationConfigResponse {
  enabled: boolean
  defaultChannel: NotificationChannel
  wechatToken: string
  barkToken: string
  hasWechatToken: boolean
  hasBarkToken: boolean
  requestTimeout: number
  retryAttempts: number
  retryDelay: number
  titleTemplate: string
  bodyTemplate: string
  baseUrls: {
    wechat: string
    bark: string
  }
  categories: NotificationCategoryConfigItem[]
}

export interface NotificationConfigUpdatePayload {
  enabled: boolean
  defaultChannel: NotificationChannel
  wechatToken?: string
  barkToken?: string
  requestTimeout: number
  retryAttempts: number
  retryDelay: number
  titleTemplate?: string
  bodyTemplate?: string
  baseUrls?: {
    wechat: string
    bark: string
  }
  categories: NotificationCategoryConfigItem[]
}

export interface NotificationSendPayload {
  title: string
  content?: string
  channel?: NotificationChannel
  category?: string
  bypass_quota?: boolean
}

export interface NotificationSendResult {
  success: boolean
  channel: NotificationChannel
  category: string
  status_code?: number
  quota?: {
    max_per_window?: number | null
    current_count?: number
    remaining?: number | null
    window_seconds?: number
    reset_seconds?: number
  }
  response?: unknown
}

export interface NotificationQuotasResponse {
  success: boolean
  data: Record<string, Record<string, {
    current: number
    max_per_window?: number | null
    remaining?: number | null
    window_seconds?: number
    reset_seconds?: number
    expires_at?: number
  }>>
}

export const fetchNotificationConfig = async (): Promise<NotificationConfigResponse> => {
  const response = await request.get<NotificationConfigResponse>('/notification/config')
  return response.data
}

export const updateNotificationConfig = async (payload: NotificationConfigUpdatePayload): Promise<NotificationConfigResponse> => {
  const response = await request.put<NotificationConfigResponse>('/notification/config', payload)
  return response.data
}

export const sendNotification = async (payload: NotificationSendPayload): Promise<NotificationSendResult> => {
  const response = await request.post<NotificationSendResult>('/notification/send', payload)
  return response.data
}

export const fetchNotificationQuotas = async (): Promise<NotificationQuotasResponse> => {
  const response = await request.get<NotificationQuotasResponse>('/notification/quotas')
  return response.data
}

export const resetNotificationQuotas = async (): Promise<{ success: boolean }> => {
  const response = await request.post<{ success: boolean }>('/notification/quotas/reset')
  return response.data
}
