/**
 * 消息管理器
 * 用于管理全局的 message 实例，避免直接使用 antd 的静态 message
 */

import logger from '@/utils/logger'

const messageManagerLogger = logger.child('utils:message-manager')

class MessageManager {
  constructor() {
    this.messageApi = null
  }

  /**
   * 设置 message API 实例
   * @param {MessageInstance} api - 从 App.useApp() 获取的 message 实例
   */
  setMessageApi(api) {
    this.messageApi = api
  }

  /**
   * 显示成功消息
   * @param {string} content - 消息内容
   * @param {number} duration - 持续时间（秒）
   */
  success(content, duration = 3) {
    if (this.messageApi) {
      this.messageApi.success(content, duration)
    } else {
      messageManagerLogger.info('[Success]:', content)
    }
  }

  /**
   * 显示错误消息
   * @param {string} content - 消息内容
   * @param {number} duration - 持续时间（秒）
   */
  error(content, duration = 3) {
    if (this.messageApi) {
      this.messageApi.error(content, duration)
    } else {
      messageManagerLogger.error('[Error]:', content)
    }
  }

  /**
   * 显示警告消息
   * @param {string} content - 消息内容
   * @param {number} duration - 持续时间（秒）
   */
  warning(content, duration = 3) {
    if (this.messageApi) {
      this.messageApi.warning(content, duration)
    } else {
      messageManagerLogger.warn('[Warning]:', content)
    }
  }

  /**
   * 显示信息消息
   * @param {string} content - 消息内容
   * @param {number} duration - 持续时间（秒）
   */
  info(content, duration = 3) {
    if (this.messageApi) {
      this.messageApi.info(content, duration)
    } else {
      messageManagerLogger.info('[Info]:', content)
    }
  }

  /**
   * 显示加载中消息
   * @param {string} content - 消息内容
   * @param {number} duration - 持续时间（秒），0 表示不自动关闭
   */
  loading(content, duration = 0) {
    if (this.messageApi) {
      return this.messageApi.loading(content, duration)
    } else {
      messageManagerLogger.info('[Loading]:', content)
      return () => {} // 返回空函数作为 destroy 方法
    }
  }
}

// 导出单例
const messageManager = new MessageManager()
export default messageManager