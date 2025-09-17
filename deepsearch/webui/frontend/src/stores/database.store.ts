/**
 * 数据库状态管理 Store
 */

import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import { devtools } from 'zustand/middleware'
import { message } from 'antd'

import {
  DatabaseConnection,
  CreateConnectionDTO,
  UpdateConnectionDTO,
  TestResult,
  StoreError
} from './types'

import {
  fetchDatabaseConnections,
  createDatabaseConnection,
  updateDatabaseConnection,
  deleteDatabaseConnection,
  testDatabaseConnection
} from '@/api/systemConfig'

import { cacheService } from '@/dataCenter/cache.service'
import { requestManager, generateCacheKey } from '@/dataCenter/utils'

// Store 状态接口
interface DatabaseState {
  // 状态数据
  connections: DatabaseConnection[]
  loading: boolean
  error: StoreError | null
  selectedId: number | null

  // 缓存控制
  lastFetch: number
  cacheTime: number // 缓存时间（毫秒）

  // Actions
  fetchConnections: (force?: boolean) => Promise<void>
  createConnection: (data: CreateConnectionDTO) => Promise<void>
  updateConnection: (id: number, data: UpdateConnectionDTO) => Promise<void>
  deleteConnection: (id: number) => Promise<void>
  testConnection: (id: number) => Promise<TestResult>
  selectConnection: (id: number | null) => void
  clearError: () => void
  reset: () => void
}

// 初始状态
const initialState = {
  connections: [],
  loading: false,
  error: null,
  selectedId: null,
  lastFetch: 0,
  cacheTime: 30000 // 默认缓存30秒
}

// 创建 Store
export const useDatabaseStore = create<DatabaseState>()(
  devtools(
    immer((set, get) => ({
      ...initialState,

      /**
       * 获取数据库连接列表
       */
      fetchConnections: async (force = false) => {
        const state = get()
        const now = Date.now()

        // 检查缓存
        if (!force) {
          // 如果正在加载，直接返回
          if (state.loading) {
            console.log('[DatabaseStore] 正在加载中，跳过重复请求')
            return
          }

          // 如果缓存未过期，直接返回
          if (now - state.lastFetch < state.cacheTime && state.connections.length > 0) {
            console.log('[DatabaseStore] 使用缓存数据')
            return
          }

          // 检查缓存服务
          const cacheKey = generateCacheKey('database:connections')
          const cached = cacheService.getWithStats<DatabaseConnection[]>(cacheKey)
          if (cached) {
            console.log('[DatabaseStore] 从缓存服务获取数据')
            set(draft => {
              draft.connections = cached
              draft.lastFetch = now
            })
            return
          }
        }

        // 设置加载状态
        set(draft => {
          draft.loading = true
          draft.error = null
        })

        try {
          // 使用请求管理器去重
          const connections = await requestManager.execute(
            'database:fetchConnections',
            () => fetchDatabaseConnections()
          )

          // 更新状态
          set(draft => {
            draft.connections = connections || []
            draft.loading = false
            draft.lastFetch = now
          })

          // 更新缓存
          const cacheKey = generateCacheKey('database:connections')
          cacheService.set(cacheKey, connections, state.cacheTime)

          console.log('[DatabaseStore] 获取连接成功:', connections)
        } catch (error) {
          const errorObj: StoreError = {
            code: 'FETCH_ERROR',
            message: error instanceof Error ? error.message : '获取数据库连接失败',
            details: error,
            timestamp: now
          }

          set(draft => {
            draft.loading = false
            draft.error = errorObj
          })

          // 不显示错误消息，让组件处理
          console.error('[DatabaseStore] 获取连接失败:', error)
        }
      },

      /**
       * 创建数据库连接
       */
      createConnection: async (data: CreateConnectionDTO) => {
        set(draft => {
          draft.loading = true
          draft.error = null
        })

        try {
          const newConnection = await createDatabaseConnection(data)

          set(draft => {
            draft.connections.push(newConnection)
            draft.loading = false
          })

          // 清除缓存
          cacheService.invalidate('database:')

          message.success('创建连接成功')
        } catch (error) {
          const errorObj: StoreError = {
            code: 'CREATE_ERROR',
            message: error instanceof Error ? error.message : '创建连接失败',
            details: error,
            timestamp: Date.now()
          }

          set(draft => {
            draft.loading = false
            draft.error = errorObj
          })

          message.error(errorObj.message)
          throw error
        }
      },

      /**
       * 更新数据库连接
       */
      updateConnection: async (id: number, data: UpdateConnectionDTO) => {
        set(draft => {
          draft.loading = true
          draft.error = null
        })

        try {
          const updatedConnection = await updateDatabaseConnection(id, data)

          set(draft => {
            const index = draft.connections.findIndex(c => c.id === id)
            if (index !== -1) {
              draft.connections[index] = updatedConnection
            }
            draft.loading = false
          })

          // 清除缓存
          cacheService.invalidate('database:')

          message.success('更新连接成功')
        } catch (error) {
          const errorObj: StoreError = {
            code: 'UPDATE_ERROR',
            message: error instanceof Error ? error.message : '更新连接失败',
            details: error,
            timestamp: Date.now()
          }

          set(draft => {
            draft.loading = false
            draft.error = errorObj
          })

          message.error(errorObj.message)
          throw error
        }
      },

      /**
       * 删除数据库连接
       */
      deleteConnection: async (id: number) => {
        set(draft => {
          draft.loading = true
          draft.error = null
        })

        try {
          await deleteDatabaseConnection(id)

          set(draft => {
            draft.connections = draft.connections.filter(c => c.id !== id)
            if (draft.selectedId === id) {
              draft.selectedId = null
            }
            draft.loading = false
          })

          // 清除缓存
          cacheService.invalidate('database:')

          message.success('删除连接成功')
        } catch (error) {
          const errorObj: StoreError = {
            code: 'DELETE_ERROR',
            message: error instanceof Error ? error.message : '删除连接失败',
            details: error,
            timestamp: Date.now()
          }

          set(draft => {
            draft.loading = false
            draft.error = errorObj
          })

          message.error(errorObj.message)
          throw error
        }
      },

      /**
       * 测试数据库连接
       */
      testConnection: async (id: number) => {
        try {
          const result = await testDatabaseConnection(id)

          if (result.success) {
            message.success(result.message || '连接测试成功')

            // 更新连接状态
            set(draft => {
              const connection = draft.connections.find(c => c.id === id)
              if (connection) {
                connection.connected = true
                connection.status = 'connected'
                connection.lastHealthCheck = new Date().toISOString()
              }
            })
          } else {
            message.error(result.message || '连接测试失败')

            // 更新连接状态
            set(draft => {
              const connection = draft.connections.find(c => c.id === id)
              if (connection) {
                connection.connected = false
                connection.status = 'error'
                connection.error = result.error
              }
            })
          }

          return result
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : '测试连接失败'
          message.error(errorMessage)
          throw error
        }
      },

      /**
       * 选择连接
       */
      selectConnection: (id: number | null) => {
        set(draft => {
          draft.selectedId = id
        })
      },

      /**
       * 清除错误
       */
      clearError: () => {
        set(draft => {
          draft.error = null
        })
      },

      /**
       * 重置状态
       */
      reset: () => {
        set(draft => {
          Object.assign(draft, initialState)
        })
        cacheService.invalidate('database:')
      }
    })),
    {
      name: 'database-store' // DevTools 中显示的名称
    }
  )
)

// 导出 hooks
export const useDatabaseConnections = () => {
  const connections = useDatabaseStore(state => state.connections)
  const loading = useDatabaseStore(state => state.loading)
  const fetchConnections = useDatabaseStore(state => state.fetchConnections)

  return { connections, loading, fetchConnections }
}

export const useSelectedConnection = () => {
  const selectedId = useDatabaseStore(state => state.selectedId)
  const connections = useDatabaseStore(state => state.connections)
  const selectConnection = useDatabaseStore(state => state.selectConnection)

  const selectedConnection = connections.find(c => c.id === selectedId)

  return { selectedConnection, selectConnection }
}