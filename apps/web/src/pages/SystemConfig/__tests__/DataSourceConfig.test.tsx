import React from 'react'
import {act, render, screen} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DataSourceConfig from '../DataSourceConfig'
import '@testing-library/jest-dom'

const mockMessageApi = {
  open: jest.fn(),
  destroy: jest.fn(),
  success: jest.fn(),
  error: jest.fn(),
  warning: jest.fn(),
  info: jest.fn(),
  loading: jest.fn(),
}

jest.mock('antd', () => {
  const actual = jest.requireActual('antd')
  const AppComponent = actual.App
  AppComponent.useApp = () => ({ message: mockMessageApi })
  return {
    ...actual,
    App: AppComponent,
  }
})

const mockUseAsyncData = jest.fn()
const mockUseModal = jest.fn()
const mockUseDataSourceStatus = jest.fn()

jest.mock('@/hooks', () => ({
  useModal: (...args: any[]) => mockUseModal(...args),
  useAsyncData: (...args: any[]) => mockUseAsyncData(...args),
}))

jest.mock('@/stores', () => ({
  useDataSourceStatus: (...args: any[]) => mockUseDataSourceStatus(...args),
}))

jest.mock('@/api/config/dataSourceConfig', () => ({
  fetchDataSources: jest.fn(),
  fetchDataSourceHealth: jest.fn(),
  createDataSource: jest.fn(),
  updateDataSource: jest.fn(),
  deleteDataSource: jest.fn(),
  testDataSource: jest.fn(),
  toggleDataSource: jest.fn(),
}))

jest.mock('@/api/config/systemImport', () => ({
  fetchGlobalDataSourceConfig: jest.fn(async () => ({})),
  updateDataSourceConfig: jest.fn(),
}))

describe('DataSourceConfig 状态与凭证交互', () => {
  let dataSourcesState: any[]
  let healthState: Record<string, any>
  let summaryState: Record<string, any>

  beforeEach(() => {
    Object.values(mockMessageApi).forEach(fn => fn.mockClear())
    mockUseAsyncData.mockReset()
    mockUseModal.mockReset()

    mockUseModal.mockReturnValue({
      visible: false,
      data: null,
      open: jest.fn(),
      close: jest.fn(),
      setLoading: jest.fn(),
    })

    dataSourcesState = []
    healthState = {}
    summaryState = {}

    mockUseDataSourceStatus.mockImplementation(() => {
      const counts = dataSourcesState.reduce((acc: Record<string, number>, item: Record<string, unknown>) => {
        const status = String(item.status || 'offline')
        acc[status] = (acc[status] || 0) + 1
        return acc
      }, {})

      return {
        dataSources: dataSourcesState,
        summary: {
          total: dataSourcesState.length,
          availableCount: healthState?.availableCount ?? 0,
          counts,
          ...summaryState,
        },
        health: healthState,
        loading: false,
        error: null,
        fetchStatus: jest.fn(async () => undefined),
        refreshStatus: jest.fn(async () => undefined),
      }
    })
  })

  const renderComponent = () => render(<DataSourceConfig />)

  it('展示完整生命周期状态标签', () => {
    dataSourcesState = [
      {
        id: 'ds-active',
        name: '主数据源',
        type: 'amazingdata',
        status: 'active',
        enabled: true,
        priority: 1,
        config: { host: '127.0.0.1', port: 8600 },
      },
      {
        id: 'ds-degraded',
        name: '备用数据源',
        type: 'cloudflare',
        status: 'degraded',
        enabled: true,
        priority: 2,
        config: { workerUrl: 'https://example.workers.dev' },
      },
      {
        id: 'ds-pending',
        name: '测试数据源',
        type: 'qmt',
        status: 'pending_test',
        enabled: false,
        priority: 3,
        config: { host: 'localhost', port: 6000 },
      },
      {
        id: 'ds-testing',
        name: '联调数据源',
        type: 'akshare',
        status: 'testing',
        enabled: true,
        priority: 4,
        config: { host: 'akshare', port: 9000 },
      },
      {
        id: 'ds-ready',
        name: '候选数据源',
        type: 'backup',
        status: 'ready',
        enabled: false,
        priority: 5,
        config: {},
      },
      {
        id: 'ds-error',
        name: '故障数据源',
        type: 'legacy',
        status: 'error',
        enabled: false,
        priority: 6,
        config: {},
      },
      {
        id: 'ds-offline',
        name: '停用数据源',
        type: 'deprecated',
        status: 'offline',
        enabled: false,
        priority: 7,
        config: {},
      },
    ]

    healthState = {
      sources: {
        amazingdata: { status: 'active', available: true },
        cloudflare: { status: 'degraded', available: false },
        qmt: { status: 'pending_test', available: false },
        akshare: { status: 'testing', available: true },
        backup: { status: 'ready', available: true },
        legacy: { status: 'error', available: false },
        deprecated: { status: 'offline', available: false },
      },
      availableCount: 3,
    }

    renderComponent()

    ;[
      '待测试',
      '测试中',
      '可启用',
      '已启用',
      '性能异常',
      '错误',
      '已停用',
    ].forEach(label => {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
    })
  })

  it('含已保存凭证时展示提示并支持更新流程', async () => {
    const user = userEvent.setup()

    dataSourcesState = [
      {
        id: 'secured',
        name: '受保护数据源',
        type: 'amazingdata',
        status: 'active',
        enabled: true,
        priority: 1,
        hasSavedCredential: true,
        config: { host: 'host', port: 8600 },
      },
    ]

    healthState = {
      sources: {
        amazingdata: {
          status: 'active',
          available: true,
          hasSavedCredential: true,
          lastTestTime: '2025-01-01T10:00:00Z',
          testSummary: '校验通过',
        },
      },
      availableCount: 1,
    }

    mockUseModal
      .mockReturnValueOnce({
        visible: false,
        data: null,
        open: jest.fn(),
        close: jest.fn(),
        setLoading: jest.fn(),
      })
      .mockReturnValueOnce({
        visible: true,
        data: dataSourcesState[0],
        open: jest.fn(),
        close: jest.fn(),
        setLoading: jest.fn(),
      })

    renderComponent()

    expect(screen.getByText('已保存')).toBeInTheDocument()
    const updateButton = screen.getByRole('button', { name: '更新凭证' })
    expect(updateButton).toBeEnabled()

    await act(async () => {
      await user.click(updateButton)
    })

    expect(screen.getByPlaceholderText('请输入密码')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '保留已保存的凭证' })).toBeInTheDocument()
  })

  it('状态异常时弹出告警，恢复后清除', () => {
    dataSourcesState = [
      {
        id: 'alert-source',
        name: '主数据源',
        type: 'amazingdata',
        status: 'degraded',
        enabled: true,
        priority: 1,
        config: { host: 'host', port: 8600 },
      },
    ]

    healthState = {
      sources: {
        amazingdata: { status: 'degraded', available: true },
      },
      availableCount: 1,
    }

    const { rerender } = renderComponent()

    expect(mockMessageApi.open).toHaveBeenCalledWith(
      expect.objectContaining({
        content: expect.stringContaining('请重新测试查看诊断'),
        type: 'warning',
      })
    )

    mockMessageApi.open.mockClear()
    mockMessageApi.destroy.mockClear()

    dataSourcesState = [
      {
        id: 'alert-source',
        name: '主数据源',
        type: 'amazingdata',
        status: 'active',
        enabled: true,
        priority: 1,
        config: { host: 'host', port: 8600 },
      },
    ]

    healthState = {
      sources: {
        amazingdata: { status: 'active', available: true },
      },
      availableCount: 1,
    }

    rerender(<DataSourceConfig />)

    expect(mockMessageApi.destroy).toHaveBeenCalled()
    expect(mockMessageApi.open).not.toHaveBeenCalled()
  })
})
