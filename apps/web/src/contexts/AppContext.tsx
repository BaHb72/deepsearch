import { createContext, useContext, useReducer, useCallback, useEffect, type ReactNode } from 'react'
import { message, notification } from 'antd'
import { useNavigate } from 'react-router-dom'
import request from '@/api/request'
import systemAPI from '@/api/system'
import { storage } from '@/utils/storage'

// ============= 类型定义 =============

interface User {
  name: string
  [key: string]: unknown
}

interface AppNotification {
  id: number
  timestamp: string
  type?: 'info' | 'success' | 'warning' | 'error'
  title?: string
  message?: string
  [key: string]: unknown
}

interface AppState {
  user: User | null
  token: string | null
  systemStatus: unknown
  systemInfo: unknown
  components: unknown[]
  loading: boolean
  collapsed: boolean
  settingsVisible: boolean
  notifications: AppNotification[]
  wsConnected: boolean
  wsMessage: unknown
}

interface AppAction {
  type: string
  payload?: unknown
}

interface AppProviderProps {
  children: ReactNode
}


type AppContextType = any // 简化处理，避免复杂类型定义

// Action Types
const ActionTypes = {
  // 用户相关
  SET_USER: 'SET_USER',
  SET_TOKEN: 'SET_TOKEN',
  LOGOUT: 'LOGOUT',

  // 系统相关
  SET_SYSTEM_STATUS: 'SET_SYSTEM_STATUS',
  SET_SYSTEM_INFO: 'SET_SYSTEM_INFO',
  SET_COMPONENTS: 'SET_COMPONENTS',

  // UI 相关
  SET_LOADING: 'SET_LOADING',
  SET_COLLAPSED: 'SET_COLLAPSED',
  SET_SETTINGS_VISIBLE: 'SET_SETTINGS_VISIBLE',

  // 通知相关
  ADD_NOTIFICATION: 'ADD_NOTIFICATION',
  REMOVE_NOTIFICATION: 'REMOVE_NOTIFICATION',
  CLEAR_NOTIFICATIONS: 'CLEAR_NOTIFICATIONS',

  // WebSocket
  SET_WS_CONNECTED: 'SET_WS_CONNECTED',
  SET_WS_MESSAGE: 'SET_WS_MESSAGE',
}

// 初始状态
const initialState = {
  // 用户信息
  user: storage.getItem('user') || null,
  token: storage.getItem('token') || null,

  // 系统状态
  systemStatus: null,
  systemInfo: null,
  components: [],

  // UI 状态
  loading: false,
  collapsed: false,
  settingsVisible: false,

  // 通知
  notifications: [],

  // WebSocket
  wsConnected: false,
  wsMessage: null,
}

// Reducer
const appReducer = (state: AppState, action: AppAction): AppState => {
  switch (action.type) {
    case ActionTypes.SET_USER:
      return { ...state, user: action.payload as User | null }

    case ActionTypes.SET_TOKEN:
      return { ...state, token: action.payload as string | null }

    case ActionTypes.LOGOUT:
      return {
        ...state,
        user: null,
        token: null,
        systemStatus: null,
        components: [],
      }

    case ActionTypes.SET_SYSTEM_STATUS:
      return { ...state, systemStatus: action.payload }

    case ActionTypes.SET_SYSTEM_INFO:
      return { ...state, systemInfo: action.payload }

    case ActionTypes.SET_COMPONENTS:
      return { ...state, components: action.payload as unknown[] }

    case ActionTypes.SET_LOADING:
      return { ...state, loading: action.payload as boolean }

    case ActionTypes.SET_COLLAPSED:
      return { ...state, collapsed: action.payload as boolean }

    case ActionTypes.SET_SETTINGS_VISIBLE:
      return { ...state, settingsVisible: action.payload as boolean }

    case ActionTypes.ADD_NOTIFICATION:
      return {
        ...state,
        notifications: [action.payload as AppNotification, ...state.notifications].slice(0, 10)
      }

    case ActionTypes.REMOVE_NOTIFICATION:
      return {
        ...state,
        notifications: state.notifications.filter((n: AppNotification) => n.id !== action.payload)
      }

    case ActionTypes.CLEAR_NOTIFICATIONS:
      return { ...state, notifications: [] }

    case ActionTypes.SET_WS_CONNECTED:
      return { ...state, wsConnected: action.payload as boolean }

    case ActionTypes.SET_WS_MESSAGE:
      return { ...state, wsMessage: action.payload }

    default:
      return state
  }
}

// Context
const AppContext = createContext<AppContextType | null>(null)

// Provider Component
export const AppProvider = ({ children }: AppProviderProps) => {
  const [state, dispatch] = useReducer(appReducer, initialState)
  const navigate = useNavigate()

  // Actions
  const actions = {
    // 用户相关
    setUser: useCallback((user: User | null) => {
      dispatch({ type: ActionTypes.SET_USER, payload: user })
      storage.setItem('user', user)
    }, []),

    setToken: useCallback((token: string | null) => {
      dispatch({ type: ActionTypes.SET_TOKEN, payload: token })
      storage.setItem('token', token)
    }, []),

    login: useCallback(async (credentials: unknown) => {
      try {
        dispatch({ type: ActionTypes.SET_LOADING, payload: true })
        const raw = await request.post('/auth/login', credentials as Record<string, unknown>)
        const rawRecord = raw && typeof raw === 'object'
          ? raw as unknown as Record<string, unknown>
          : null
        const payload = rawRecord && 'data' in rawRecord
          ? (raw as { data: unknown }).data
          : raw
        const response = payload as { token?: string; user?: User } | null
        const token = response?.token
        const user = response?.user

        if (!token || !user) {
          throw new Error('登录接口返回缺少 token 或 user 字段')
        }

        actions.setToken(token)
        actions.setUser(user)

        message.success('登录成功')
        navigate('/')

        return response
      } catch (error) {
        message.error('登录失败：' + (error as Error).message)
        throw error
      } finally {
        dispatch({ type: ActionTypes.SET_LOADING, payload: false })
      }
    }, [navigate]),

    logout: useCallback(() => {
      dispatch({ type: ActionTypes.LOGOUT })
      storage.removeItem('user')
      storage.removeItem('token')
      message.success('已退出登录')
      navigate('/login')
    }, [navigate]),

    // 系统相关
    fetchSystemStatus: useCallback(async () => {
      try {
        const status = await systemAPI.getStatus()
        dispatch({ type: ActionTypes.SET_SYSTEM_STATUS, payload: status })
        return status
      } catch (error) {
        console.error('获取系统状态失败:', error)
        throw error
      }
    }, []),

    fetchSystemInfo: useCallback(async () => {
      try {
        const info = await systemAPI.getInfo()
        dispatch({ type: ActionTypes.SET_SYSTEM_INFO, payload: info })
        return info
      } catch (error) {
        console.error('获取系统信息失败:', error)
        throw error
      }
    }, []),

    startSystem: useCallback(async () => {
      try {
        dispatch({ type: ActionTypes.SET_LOADING, payload: true })
        await systemAPI.start()
        await actions.fetchSystemStatus()
        message.success('系统启动成功')
      } catch (error) {
        message.error('系统启动失败：' + (error as Error).message)
        throw error
      } finally {
        dispatch({ type: ActionTypes.SET_LOADING, payload: false })
      }
    }, []),

    stopSystem: useCallback(async () => {
      try {
        dispatch({ type: ActionTypes.SET_LOADING, payload: true })
        await systemAPI.stop()
        await actions.fetchSystemStatus()
        message.success('系统已停止')
      } catch (error) {
        message.error('系统停止失败：' + (error as Error).message)
        throw error
      } finally {
        dispatch({ type: ActionTypes.SET_LOADING, payload: false })
      }
    }, []),

    restartSystem: useCallback(async () => {
      try {
        dispatch({ type: ActionTypes.SET_LOADING, payload: true })
        await systemAPI.restart()
        await actions.fetchSystemStatus()
        message.success('系统重启成功')
      } catch (error) {
        message.error('系统重启失败：' + (error as Error).message)
        throw error
      } finally {
        dispatch({ type: ActionTypes.SET_LOADING, payload: false })
      }
    }, []),

    // UI 相关
    setLoading: useCallback((loading: boolean) => {
      dispatch({ type: ActionTypes.SET_LOADING, payload: loading })
    }, []),

    setCollapsed: useCallback((collapsed: boolean) => {
      dispatch({ type: ActionTypes.SET_COLLAPSED, payload: collapsed })
    }, []),

    toggleSettings: useCallback(() => {
      dispatch({
        type: ActionTypes.SET_SETTINGS_VISIBLE,
        payload: !state.settingsVisible
      })
    }, [state.settingsVisible]),

    // 通知相关
    addNotification: useCallback((notificationData: Partial<AppNotification>) => {
      const id = Date.now()
      const notif = { id, timestamp: new Date().toISOString(), ...notificationData }

      dispatch({ type: ActionTypes.ADD_NOTIFICATION, payload: notif })

      // 显示系统通知
      if (notificationData.type === 'error') {
        notification.error({
          message: notificationData.title,
          description: notificationData.message,
          duration: 5,
        })
      } else if (notificationData.type === 'warning') {
        notification.warning({
          message: notificationData.title,
          description: notificationData.message,
          duration: 4,
        })
      } else if (notificationData.type === 'success') {
        notification.success({
          message: notificationData.title,
          description: notificationData.message,
          duration: 3,
        })
      } else {
        notification.info({
          message: notificationData.title,
          description: notificationData.message,
          duration: 4,
        })
      }

      return id
    }, []),

    removeNotification: useCallback((id: number) => {
      dispatch({ type: ActionTypes.REMOVE_NOTIFICATION, payload: id })
    }, []),

    clearNotifications: useCallback(() => {
      dispatch({ type: ActionTypes.CLEAR_NOTIFICATIONS })
    }, []),

    // WebSocket
    setWsConnected: useCallback((connected: boolean) => {
      dispatch({ type: ActionTypes.SET_WS_CONNECTED, payload: connected })
    }, []),

    handleWsMessage: useCallback((wsMsg: { type?: string; data?: unknown }) => {
      dispatch({ type: ActionTypes.SET_WS_MESSAGE, payload: wsMsg })

      // 根据消息类型处理
      switch (wsMsg.type) {
        case 'system_status':
          dispatch({ type: ActionTypes.SET_SYSTEM_STATUS, payload: wsMsg.data })
          break

        case 'component_update':
          dispatch({ type: ActionTypes.SET_COMPONENTS, payload: wsMsg.data })
          break

        case 'notification':
          actions.addNotification(wsMsg.data as Partial<AppNotification>)
          break

        default:
          console.log('未知消息类型:', wsMsg.type)
      }
    }, []),
  }

  // 自动获取系统状态
  useEffect(() => {
    if (state.token) {
      actions.fetchSystemStatus().catch(console.error)
      actions.fetchSystemInfo().catch(console.error)

      // 定时刷新
      const timer = setInterval(() => {
        actions.fetchSystemStatus().catch(console.error)
      }, 30000) // 30秒刷新一次

      return () => clearInterval(timer)
    }
  }, [state.token])

  // WebSocket 连接管理
  useEffect(() => {
    if (state.token) {
      // 这里应该建立 WebSocket 连接
      // const ws = new WebSocket(...)
      // ws.onmessage = (e) => actions.handleWsMessage(JSON.parse(e.data))
    }
  }, [state.token])

  const value = {
    state,
    dispatch,
    actions,
    ...actions, // 展开所有 actions 方便使用
  }

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  )
}

// Hook
export const useApp = () => {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useApp must be used within AppProvider')
  }
  return context
}

// 导出常量
export { ActionTypes }
export default AppContext
