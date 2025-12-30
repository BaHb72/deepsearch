import request from './request'

export type NotificationChannel = 'wechat' | 'bark'

export interface NotificationCategoryConfigItem {
  name: string
  enabled: boolean
  maxPerWindow: number
  windowSeconds: number
  channels: NotificationChannel[]
}

export interface BarkServer {
  name: string
  baseUrl: string
  token: string
  enabled: boolean
  group?: string
  icon?: string
  sound?: string
  level?: 'active' | 'timeSensitive' | 'passive' | 'critical'
}

// ==================== 消息模板类型 ====================

export interface WechatMessageTemplate {
  name: string
  titleTemplate: string
  bodyTemplate: string
}

export interface BarkMessageTemplate {
  name: string
  titleTemplate: string
  bodyTemplate: string
  subtitleTemplate?: string
  useMarkdown?: boolean
  level?: 'active' | 'timeSensitive' | 'passive' | 'critical'
  sound?: string
  icon?: string
  image?: string
  group?: string
  url?: string
  copyContent?: string
  autoCopy?: boolean
  isArchive?: boolean
  call?: boolean
  badge?: number
}

export interface MessageTemplates {
  wechat: WechatMessageTemplate[]
  bark: BarkMessageTemplate[]
  defaultWechat?: string
  defaultBark?: string
}

export interface NotificationConfigResponse {
  enabled: boolean
  defaultChannel: NotificationChannel[] | NotificationChannel
  wechatToken: string
  barkToken: string
  hasWechatToken: boolean
  hasBarkToken: boolean
  barkServers: BarkServer[]
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
  templates: MessageTemplates
}

export interface NotificationConfigUpdatePayload {
  enabled: boolean
  defaultChannel: NotificationChannel[] | NotificationChannel
  wechatToken?: string
  barkToken?: string
  barkServers?: BarkServer[]
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
  templates?: MessageTemplates
}

export interface NotificationSendPayload {
  title: string
  content?: string
  channel?: NotificationChannel
  category?: string
  bypass_quota?: boolean
  barkServerNames?: string[]  // 指定推送的 Bark 服务器名称列表
  barkTemplateName?: string   // 指定使用的 Bark 模板名称
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
  // 响应拦截器已经返回 response.data，所以这里直接返回
  const data = await request.get<NotificationConfigResponse>('/notification/config')
  return data as unknown as NotificationConfigResponse
}

export const updateNotificationConfig = async (payload: NotificationConfigUpdatePayload): Promise<NotificationConfigResponse> => {
  // 响应拦截器已经返回 response.data，所以这里直接返回
  const data = await request.put<NotificationConfigResponse>('/notification/config', payload)
  return data as unknown as NotificationConfigResponse
}


export const sendNotification = async (payload: NotificationSendPayload): Promise<NotificationSendResult> => {
  const data = await request.post<NotificationSendResult>('/notification/send', payload)
  return data as unknown as NotificationSendResult
}

export const fetchNotificationQuotas = async (): Promise<NotificationQuotasResponse> => {
  const data = await request.get<NotificationQuotasResponse>('/notification/quotas')
  return data as unknown as NotificationQuotasResponse
}

export const resetNotificationQuotas = async (): Promise<{ success: boolean }> => {
  const data = await request.post<{ success: boolean }>('/notification/quotas/reset')
  return data as unknown as { success: boolean }
}
