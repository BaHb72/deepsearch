/**
 * 安全的 localStorage 操作封装
 * 处理隐私模式和其他可能的访问限制
 */

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
        } catch (e) {
            console.warn('localStorage 不可用，将使用内存存储', e)
            return false
        }
    }

    /**
     * 获取值
     */
    getItem(key) {
        try {
            if (this.isAvailable) {
                return localStorage.getItem(key)
            }
            return this.memoryStorage.get(key) || null
        } catch (e) {
            console.error('获取存储值失败:', e)
            return this.memoryStorage.get(key) || null
        }
    }

    /**
     * 设置值
     */
    setItem(key, value) {
        try {
            if (this.isAvailable) {
                localStorage.setItem(key, value)
            }
            this.memoryStorage.set(key, value)
        } catch (e) {
            console.error('设置存储值失败:', e)
            this.memoryStorage.set(key, value)
        }
    }

    /**
     * 移除值
     */
    removeItem(key) {
        try {
            if (this.isAvailable) {
                localStorage.removeItem(key)
            }
            this.memoryStorage.delete(key)
        } catch (e) {
            console.error('移除存储值失败:', e)
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
        } catch (e) {
            console.error('清空存储失败:', e)
            this.memoryStorage.clear()
        }
    }
}

// 导出单例
export const storage = new SafeStorage()

// 导出常用的存储键
export const STORAGE_KEYS = {
    THEME: 'theme',
    USER_PREFERENCES: 'user_preferences',
    LAST_ROUTE: 'last_route'
}