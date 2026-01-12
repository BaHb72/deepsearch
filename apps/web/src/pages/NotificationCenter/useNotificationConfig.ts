import { useCallback, useEffect, useRef, useState } from 'react'
import { App } from 'antd'
import {
  fetchNotificationConfig,
  updateNotificationConfig,
  type NotificationConfigResponse,
  type NotificationConfigUpdatePayload,
  type NotificationChannel,
} from '@/api/notifications'
import { DEFAULT_BODY_TEMPLATE, DEFAULT_TITLE_TEMPLATE } from './constants'

interface TokenPatch {
  wechatToken?: string | null
  barkToken?: string | null
}

interface SaveOptions {
  tokens?: TokenPatch
  successMessage?: string | false
  silent?: boolean
}

export interface UseNotificationConfigResult {
  config: NotificationConfigResponse | null
  loading: boolean
  saving: boolean
  error: string | null
  load: () => Promise<void>
  save: (
    patch: Partial<NotificationConfigResponse>,
    options?: SaveOptions,
  ) => Promise<NotificationConfigResponse | null>
  updateTokens: (
    tokens: TokenPatch,
    options?: { successMessage?: string | false; silent?: boolean },
  ) => Promise<NotificationConfigResponse | null>
  toggleEnabled: (enabled: boolean) => Promise<void>
}

const mapTokenValue = (value: string | null | undefined): string | undefined => {
  if (value === undefined) {
    return undefined
  }
  if (value === null) {
    return ''
  }
  return value
}

const normalizeChannel = (channel: NotificationChannel): NotificationChannel => {
  if (!channel) {
    return 'wechat'
  }
  return channel
}

export const useNotificationConfig = (): UseNotificationConfigResult => {
  const { message } = App.useApp()
  const [config, setConfig] = useState<NotificationConfigResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const configRef = useRef<NotificationConfigResponse | null>(null)

  useEffect(() => {
    configRef.current = config
  }, [config])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchNotificationConfig()
      const normalized: NotificationConfigResponse = {
        ...data,
        defaultChannel: normalizeChannel(data.defaultChannel),
        titleTemplate: data.titleTemplate || DEFAULT_TITLE_TEMPLATE,
        bodyTemplate: data.bodyTemplate || DEFAULT_BODY_TEMPLATE,
        categories: Array.isArray(data.categories) ? data.categories : [],
        baseUrls: {
          wechat: data.baseUrls?.wechat || '',
          bark: data.baseUrls?.bark || '',
        },
      }
      setConfig(normalized)
      configRef.current = normalized
      setError(null)
    } catch (error) {
      console.error('[NotificationCenter] 加载通知配置失败', error)
      const fallbackMessage = '加载通知配置失败，请稍后重试'
      const reason = error instanceof Error ? error.message : ''
      setError(reason ? `${fallbackMessage}：${reason}` : fallbackMessage)
      message.error(fallbackMessage)
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    if (!configRef.current) {
      void load()
    }
  }, [load])

  const save = useCallback<UseNotificationConfigResult['save']>(async (patch, options) => {
    const current = configRef.current
    if (!current) {
      await load()
    }
    const latest = configRef.current
    if (!latest) {
      message.error('通知配置尚未加载，无法保存')
      return null
    }

    const mergedBaseUrls = {
      wechat: patch.baseUrls?.wechat ?? latest.baseUrls.wechat,
      bark: patch.baseUrls?.bark ?? latest.baseUrls.bark,
    }

    const merged: NotificationConfigResponse = {
      ...latest,
      ...patch,
      baseUrls: mergedBaseUrls,
      categories: patch.categories ?? latest.categories,
      titleTemplate: patch.titleTemplate ?? latest.titleTemplate ?? DEFAULT_TITLE_TEMPLATE,
      bodyTemplate: patch.bodyTemplate ?? latest.bodyTemplate ?? DEFAULT_BODY_TEMPLATE,
    }

    const payload: NotificationConfigUpdatePayload = {
      enabled: merged.enabled,
      defaultChannel: normalizeChannel(merged.defaultChannel),
      requestTimeout: merged.requestTimeout,
      retryAttempts: merged.retryAttempts,
      retryDelay: merged.retryDelay,
      titleTemplate: merged.titleTemplate,
      bodyTemplate: merged.bodyTemplate,
      baseUrls: merged.baseUrls,
      categories: merged.categories,
    }

    const tokens = options?.tokens
    if (tokens) {
      if (Object.prototype.hasOwnProperty.call(tokens, 'wechatToken')) {
        payload.wechatToken = mapTokenValue(tokens.wechatToken)
      }
      if (Object.prototype.hasOwnProperty.call(tokens, 'barkToken')) {
        payload.barkToken = mapTokenValue(tokens.barkToken)
      }
    }

    setSaving(true)
    try {
      const updated = await updateNotificationConfig(payload)
      const normalized: NotificationConfigResponse = {
        ...updated,
        defaultChannel: normalizeChannel(updated.defaultChannel),
        titleTemplate: updated.titleTemplate || DEFAULT_TITLE_TEMPLATE,
        bodyTemplate: updated.bodyTemplate || DEFAULT_BODY_TEMPLATE,
        categories: Array.isArray(updated.categories) ? updated.categories : [],
        baseUrls: {
          wechat: updated.baseUrls?.wechat || mergedBaseUrls.wechat,
          bark: updated.baseUrls?.bark || mergedBaseUrls.bark,
        },
      }
      setConfig(normalized)
      configRef.current = normalized
      setError(null)

      const shouldNotify = !options?.silent && options?.successMessage !== false
      if (shouldNotify) {
        message.success(
          typeof options?.successMessage === 'string'
            ? options.successMessage
            : '通知配置已更新'
        )
      }
      return normalized
    } catch (error) {
      console.error('[NotificationCenter] 更新通知配置失败', error)
      const fallbackMessage = '更新通知配置失败，请稍后重试'
      const reason = error instanceof Error ? error.message : ''
      setError(reason ? `${fallbackMessage}：${reason}` : fallbackMessage)
      message.error(fallbackMessage)
      return null
    } finally {
      setSaving(false)
    }
  }, [load, message])

  const updateTokens = useCallback<UseNotificationConfigResult['updateTokens']>(
    async (tokens, options) => {
      return save(
        {},
        {
          tokens,
          successMessage: options?.successMessage ?? '通知凭证已更新',
          silent: options?.silent,
        }
      )
    },
    [save]
  )

  const toggleEnabled = useCallback(async (enabled: boolean) => {
    await save(
      { enabled },
      { successMessage: enabled ? '已开启通知渠道' : '已关闭通知渠道' }
    )
  }, [save])

  return {
    config,
    loading,
    saving,
    error,
    load,
    save,
    updateTokens,
    toggleEnabled,
  }
}

export default useNotificationConfig
