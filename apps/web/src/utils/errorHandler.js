/**
 * 统一错误处理器
 * 捕获并记录错误，但不在界面上频繁显示
 */

import logger from '@/utils/logger'

const errorHandlerLogger = logger.child('utils:error-handler')

class ErrorHandler {
  constructor() {
    this.errors = []
    this.maxErrors = 100
    this.errorListeners = []
    this.isProduction = import.meta.env.PROD
    this.setupGlobalHandlers()
  }

  // 设置全局错误处理
  setupGlobalHandlers() {
    // 捕获未处理的Promise错误
    window.addEventListener('unhandledrejection', (event) => {
      this.logError({
        type: 'unhandledRejection',
        message: event.reason?.message || event.reason,
        stack: event.reason?.stack,
        timestamp: new Date().toISOString()
      })
      // 阻止默认行为（防止控制台重复显示）
      event.preventDefault()
    })

    // 捕获全局错误
    window.addEventListener('error', (event) => {
      this.logError({
        type: 'globalError',
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        stack: event.error?.stack,
        timestamp: new Date().toISOString()
      })
      // 生产环境阻止默认行为
      if (this.isProduction) {
        event.preventDefault()
      }
    })
  }

  // 记录错误
  logError(error) {
    // 添加到错误列表
    this.errors.push(error)

    // 限制错误数量
    if (this.errors.length > this.maxErrors) {
      this.errors.shift()
    }

    // 开发环境打印到控制台
    if (!this.isProduction) {
      const errorTitle = `🔴 ${error.type || 'Error'}`
      errorHandlerLogger.error(`${errorTitle}: ${error.message}`)
      if (error.stack) {
        errorHandlerLogger.info(error.stack)
      }
    }

    // 通知监听器
    this.notifyListeners(error)

    // 发送到后端（可选）
    this.sendToBackend(error)
  }

  // 手动记录错误
  captureError(error, context = {}) {
    this.logError({
      type: 'manual',
      message: error.message || error,
      stack: error.stack,
      context,
      timestamp: new Date().toISOString()
    })
  }

  // 记录警告
  captureWarning(message, context = {}) {
    this.logError({
      type: 'warning',
      message,
      context,
      timestamp: new Date().toISOString()
    })
  }

  // 添加错误监听器
  addListener(callback) {
    this.errorListeners.push(callback)
    return () => {
      this.errorListeners = this.errorListeners.filter(cb => cb !== callback)
    }
  }

  // 通知所有监听器
  notifyListeners(error) {
    this.errorListeners.forEach(callback => {
      try {
        callback(error)
      } catch (e) {
        errorHandlerLogger.error('Error listener failed:', e)
      }
    })
  }

  // 发送错误到后端
  async sendToBackend(error) {
    if (!this.isProduction) return

    try {
      const payload = {
        ...error,
        userAgent: navigator.userAgent,
        url: window.location.href,
        timestamp: error.timestamp || new Date().toISOString()
      }

      errorHandlerLogger.debug('[SEND_PAYLOAD]', payload)
      // await fetch('/api/errors', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(payload)
      // })
    } catch (sendError) {
      errorHandlerLogger.error('Failed to send error to backend:', sendError)
    }
  }

  // 获取所有错误
  getErrors() {
    return [...this.errors]
  }

  // 清空错误
  clearErrors() {
    this.errors = []
  }

  // 获取错误统计
  getStatistics() {
    const stats = {
      total: this.errors.length,
      byType: {},
      recent: this.errors.slice(-10)
    }

    this.errors.forEach(error => {
      stats.byType[error.type] = (stats.byType[error.type] || 0) + 1
    })

    return stats
  }
}

// 创建单例
const errorHandler = new ErrorHandler()

// 导出便捷方法
export const captureError = (error, context) => errorHandler.captureError(error, context)
export const captureWarning = (message, context) => errorHandler.captureWarning(message, context)
export const addErrorListener = (callback) => errorHandler.addListener(callback)
export const getErrors = () => errorHandler.getErrors()
export const getErrorStats = () => errorHandler.getStatistics()

export default errorHandler
