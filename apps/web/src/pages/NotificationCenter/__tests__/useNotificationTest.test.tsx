import {act, renderHook} from '@testing-library/react'
import {App as AntdApp, ConfigProvider} from 'antd'
import type {ReactNode} from 'react'
import {useNotificationTest} from '../useNotificationTest'
import {TEST_HISTORY_MAX_ITEMS} from '../constants'
import {sendNotification} from '@/api/notifications'

jest.mock('@/api/notifications', () => ({
  sendNotification: jest.fn(),
}))

const wrapper = ({ children }: { children: ReactNode }) => (
  <ConfigProvider>
    <AntdApp>{children}</AntdApp>
  </ConfigProvider>
)

describe('useNotificationTest', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    window.localStorage.clear()
  })

  it('记录成功测试结果并写入历史', async () => {
    (sendNotification as jest.Mock).mockResolvedValue({
      success: true,
      channel: 'wechat',
      category: 'alert',
      status_code: 200,
      response: { ok: true },
    })

    const { result } = renderHook(() => useNotificationTest(), { wrapper })

    await act(async () => {
      await result.current.sendTest({
        title: '测试标题',
        content: '测试正文',
        channel: 'wechat',
        category: 'alert',
        bypassQuota: false,
      })
    })

    expect(result.current.history).toHaveLength(1)
    expect(result.current.history[0].success).toBe(true)
    expect(result.current.history[0].channel).toBe('wechat')
    expect(result.current.history[0].title).toBe('测试标题')
  })

  it(`只保留最近 ${TEST_HISTORY_MAX_ITEMS} 条历史记录`, async () => {
    (sendNotification as jest.Mock).mockResolvedValue({
      success: true,
      channel: 'wechat',
      category: 'default',
      status_code: 200,
    })

    const { result } = renderHook(() => useNotificationTest(), { wrapper })

    await act(async () => {
      for (let index = 0; index < TEST_HISTORY_MAX_ITEMS + 5; index += 1) {
        await result.current.sendTest({
          title: `标题-${index}`,
          content: undefined,
          channel: 'wechat',
          category: 'default',
          bypassQuota: false,
        })
      }
    })

    expect(result.current.history).toHaveLength(TEST_HISTORY_MAX_ITEMS)
    expect(result.current.history[0].title).toBe(`标题-${TEST_HISTORY_MAX_ITEMS + 4}`)
  })

  it('在发送失败时记录错误信息', async () => {
    (sendNotification as jest.Mock).mockRejectedValue({
      response: {
        status: 429,
        data: {
          detail: {
            message: '额度不足',
          },
        },
      },
      message: '额度错误',
    })

    const { result } = renderHook(() => useNotificationTest(), { wrapper })

    let capturedError: unknown
    await act(async () => {
      try {
        await result.current.sendTest({
          title: '失败标题',
          content: '失败正文',
          channel: 'wechat',
          category: 'alert',
          bypassQuota: false,
        })
      } catch (error) {
        capturedError = error
      }
    })

    expect(capturedError).toBeDefined()
    expect(result.current.history[0].success).toBe(false)
    expect(result.current.history[0].errorMessage).toContain('额度')
  })
})
