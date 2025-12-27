/**
 * 前端启动调试脚本
 * 用于测试前端启动流程和定位加载问题
 */

// 模拟前端启动流程
async function simulateStartup() {
    console.log('========================================')
    console.log('前端启动模拟测试')
    console.log('========================================')
    console.log('')

    console.log('[1] 测试动态导入 API 模块...')
    try {
        const startTime = Date.now()
        const module = await import('../deepsearch/webui/frontend/src/api/core/index.ts')
        const loadTime = Date.now() - startTime
        console.log(`✅ 模块导入成功 (耗时: ${loadTime}ms)`)
        console.log('   导出的内容:', Object.keys(module))
    } catch (error) {
        console.error('❌ 模块导入失败:', error.message)
        console.error('   错误类型:', error.constructor.name)
        console.error('   错误堆栈:', error.stack)
    }

    console.log('')
    console.log('[2] 测试 API 调用...')
    try {
        // 注意：这需要在浏览器环境中运行
        if (typeof window !== 'undefined') {
            const { api } = await import('../deepsearch/webui/frontend/src/api/core/index.ts')
            console.log('   尝试调用 api.system.getStatus()...')

            const startTime = Date.now()
            const response = await api.system.getStatus()
            const responseTime = Date.now() - startTime

            console.log(`✅ API 调用成功 (耗时: ${responseTime}ms)`)
            console.log('   响应状态:', response.status)
            console.log('   响应数据:', response.data)
        } else {
            console.log('⚠️ 需要在浏览器环境中运行此测试')
        }
    } catch (error) {
        console.error('❌ API 调用失败:', error.message)
        console.error('   错误响应:', error.response)
        console.error('   错误代码:', error.code)
    }

    console.log('')
    console.log('[3] 测试错误类型判断...')

    // 模拟不同类型的错误
    const testErrors = [
        { message: 'Cannot read property of undefined', expected: '模块加载错误' },
        { message: 'Failed to import module', expected: '模块加载错误' },
        { message: 'Request failed with status code 503', expected: '服务器错误' },
        { code: 'ECONNREFUSED', expected: '连接失败' },
        { response: { status: 500 }, expected: '服务器错误' },
        { message: 'Network Error', expected: '网络错误' }
    ]

    testErrors.forEach((testError, index) => {
        console.log(`   测试 ${index + 1}: ${testError.expected}`)

        // 判断错误类型的逻辑（与 backendStatus.js 一致）
        if (testError.message?.includes('import') || testError.message?.includes('Cannot read')) {
            console.log('     → 判定为：模块加载错误（不影响后端状态）')
        } else if (testError.response?.status >= 500 || testError.code === 'ECONNREFUSED' || testError.message?.includes('503')) {
            console.log('     → 判定为：后端服务错误（累计失败次数）')
        } else {
            console.log('     → 判定为：其他错误（不影响后端状态）')
        }
    })

    console.log('')
    console.log('[4] 测试 React StrictMode 影响...')
    console.log('   StrictMode 会导致组件双重渲染：')
    console.log('   - 组件挂载 → 卸载 → 再挂载')
    console.log('   - useEffect 可能执行两次')
    console.log('   - 可能发送重复的 API 请求')
    console.log('')
    console.log('   修复方案：')
    console.log('   - useAsyncData 使用空依赖数组')
    console.log('   - API 客户端实现请求去重')
    console.log('   - 后端状态检查避免误判')

    console.log('')
    console.log('========================================')
    console.log('测试完成')
    console.log('========================================')
}

// 如果在 Node.js 环境中运行
if (typeof window === 'undefined') {
    console.log('注意：此脚本的某些测试需要在浏览器环境中运行')
    console.log('建议在浏览器控制台中执行此脚本')
    console.log('')

    // 仍然执行基础测试
    simulateStartup().catch(console.error)
} else {
    // 在浏览器中自动执行
    simulateStartup().catch(console.error)
}

// 导出供浏览器使用
if (typeof window !== 'undefined') {
    window.testFrontendStartup = simulateStartup
}
