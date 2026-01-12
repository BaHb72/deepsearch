/**
 * 安全的 localStorage 封装
 * 在隐私模式或受限环境中自动回退到内存存储
 */

import logger from '@/utils/logger'

const storageLogger = logger.child('utils:storage')

class SafeStorage {
    constructor() {
        this.isAvailable = this.checkAvailability()
        this.memoryStorage = new Map()
    }

    /**
     * 检查 localStorage 是否可用
     */
    checkAvailability() {
        try {
            const testKey = '__localStorage_test__'
            localStorage.setItem(testKey, 'test')
            localStorage.removeItem(testKey)
            return true
        } catch (error) {
            // 在隐私模式或无存储权限时降级到内存
            storageLogger.debug('[CHECK_UNAVAILABLE] localStorage not accessible, fallback to memory')
            return false
        }
    }

    /**
     * 读取值
     */
    getItem(key) {
        try {
            if (this.isAvailable) {
                return localStorage.getItem(key)
            }
            return this.memoryStorage.get(key) ?? null
        } catch (error) {
            storageLogger.error('[GET_FAILED]', { key, error })
            return this.memoryStorage.get(key) ?? null
        }
    }

    /**
     * 写入值
     */
    setItem(key, value) {
        try {
            if (this.isAvailable) {
                localStorage.setItem(key, value)
            }
            this.memoryStorage.set(key, value)
        } catch (error) {
            storageLogger.error('[SET_FAILED]', { key, value, error })
            this.memoryStorage.set(key, value)
        }
    }

    /**
     * 删除值
     */
    removeItem(key) {
        try {
            if (this.isAvailable) {
                localStorage.removeItem(key)
            }
            this.memoryStorage.delete(key)
        } catch (error) {
            storageLogger.error('[REMOVE_FAILED]', { key, error })
            this.memoryStorage.delete(key)
        }
    }

    /**
     * 清空存储
     */
    clear() {
        try {
            if (this.isAvailable) {
                localStorage.clear()
            }
            this.memoryStorage.clear()
        } catch (error) {
            storageLogger.error('[CLEAR_FAILED]', error)
            this.memoryStorage.clear()
        }
    }
}

export const storage = new SafeStorage()

export const STORAGE_KEYS = {
    THEME: 'theme',
    USER_PREFERENCES: 'user_preferences',
    LAST_ROUTE: 'last_route'
}
