/**
 * 浏览器端调试脚本
 * 在浏览器控制台中直接执行，用于调试前端启动问题
 *
 * 使用方法：
 * 1. 打开前端页面 (http://localhost:3000)
 * 2. 打开浏览器开发者工具 (F12)
 * 3. 在控制台中复制粘贴此脚本执行
 */

(async function debugFrontend() {
    console.clear();
    console.log('%c=== 前端调试工具 ===', 'color: #1890ff; font-size: 16px; font-weight: bold');
    console.log('');

    // 1. 检查 API 模块状态
    console.group('📦 [1] API 模块状态');
    try {
        // 检查全局 API 对象
        if (window.__API__) {
            console.log('✅ API 调试工具已加载');
            console.log('可用命令:');
            console.log('  - window.__API__.getLogs()      // 查看 API 日志');
            console.log('  - window.__API__.getMetrics()   // 查看 API 指标');
            console.log('  - window.__API__.exportDocs()   // 导出 API 文档');
        } else {
            console.warn('⚠️ API 调试工具未加载');
        }

        // 检查 API 初始化标记
        console.log(`API 客户端初始化: ${window.__API_INITIALIZED__ ? '✅ 已初始化' : '❌ 未初始化'}`);
    } catch (e) {
        console.error('检查失败:', e);
    }
    console.groupEnd();

    // 2. 测试后端连接
    console.group('🔌 [2] 后端连接测试');
    try {
        console.log('测试 /api/system/status ...');
        const startTime = performance.now();

        const response = await fetch('/api/system/status');
        const data = await response.json();
        const duration = performance.now() - startTime;

        if (response.ok) {
            console.log(`✅ 后端连接正常 (${duration.toFixed(2)}ms)`);
            console.log('响应数据:', data);
        } else {
            console.error('❌ 后端返回错误:', response.status, data);
        }
    } catch (error) {
        console.error('❌ 连接失败:', error.message);
        console.log('可能的原因:');
        console.log('  1. 后端未启动');
        console.log('  2. 代理配置错误');
        console.log('  3. 网络问题');
    }
    console.groupEnd();

    // 3. 检查 backendStatus
    console.group('🏥 [3] BackendStatus 状态');
    try {
        // 动态导入 backendStatus
        const { backendStatus } = await import('/src/utils/backendStatus.js');

        const stats = backendStatus.getStatistics();
        console.log('当前状态:', {
            '可用': stats.isAvailable ? '✅' : '❌',
            '连续失败': stats.consecutiveFailures,
            '成功请求': stats.successfulRequests,
            '失败请求': stats.failedRequests,
            '恢复尝试': stats.recoveryAttempts
        });

        // 手动触发检查
        console.log('手动触发健康检查...');
        await backendStatus.checkStatus();
        console.log('检查完成');

    } catch (error) {
        console.log('无法访问 backendStatus:', error.message);
    }
    console.groupEnd();

    // 4. 检查 React 组件
    console.group('⚛️ [4] React 组件状态');
    try {
        // 查找 React DevTools
        const hasReactDevTools = window.__REACT_DEVTOOLS_GLOBAL_HOOK__ !== undefined;
        console.log(`React DevTools: ${hasReactDevTools ? '✅ 已安装' : '❌ 未安装'}`);

        // 检查 StrictMode
        console.log('React.StrictMode: 已启用（开发模式下会导致组件双重渲染）');
        console.log('影响:');
        console.log('  - useEffect 执行两次');
        console.log('  - 组件挂载->卸载->再挂载');
        console.log('  - 可能发送重复请求');

    } catch (error) {
        console.error('检查失败:', error);
    }
    console.groupEnd();

    // 5. 网络请求监控
    console.group('📡 [5] 网络请求监控');

    // 拦截 fetch
    const originalFetch = window.fetch;
    let requestCount = 0;

    window.fetch = function(...args) {
        const url = args[0];
        const id = ++requestCount;

        console.log(`📤 [${id}] 发起请求:`, url);
        const startTime = performance.now();

        return originalFetch.apply(this, args)
            .then(response => {
                const duration = performance.now() - startTime;
                const status = response.ok ? '✅' : '❌';
                console.log(`📥 [${id}] ${status} 响应 (${duration.toFixed(2)}ms):`, url, `状态码: ${response.status}`);
                return response;
            })
            .catch(error => {
                const duration = performance.now() - startTime;
                console.error(`📥 [${id}] ❌ 失败 (${duration.toFixed(2)}ms):`, url, error.message);
                throw error;
            });
    };

    console.log('✅ 网络请求监控已启动');
    console.log('所有后续的 fetch 请求都会被记录');
    console.groupEnd();

    // 6. 问题诊断
    console.group('[6] 问题诊断');

    // 检查常见问题
    const diagnostics = [];

    // 检查后端状态
    try {
        const testResponse = await fetch('/api/system/status');
        if (!testResponse.ok) {
            diagnostics.push({
                issue: '后端服务异常',
                solution: '运行: python -m deepsearch run --no-frontend'
            });
        }
    } catch (e) {
        diagnostics.push({
            issue: '无法连接后端',
            solution: '检查后端是否启动，端口是否正确（8000）'
        });
    }

    // 检查 API 初始化
    if (!window.__API_INITIALIZED__) {
        diagnostics.push({
            issue: 'API 客户端未初始化',
            solution: '等待页面完全加载，或刷新页面'
        });
    }

    // 输出诊断结果
    if (diagnostics.length > 0) {
        console.warn('发现以下问题:');
        diagnostics.forEach((d, i) => {
            console.log(`  ${i + 1}. ${d.issue}`);
            console.log(`     解决方案: ${d.solution}`);
        });
    } else {
        console.log('✅ 未发现明显问题');
    }

    console.groupEnd();

    console.log('');
    console.log('%c=== 调试完成 ===', 'color: #52c41a; font-size: 16px; font-weight: bold');
    console.log('');
    console.log('💡 提示:');
    console.log('  1. 刷新页面后需要重新运行此脚本');
    console.log('  2. 网络监控会持续记录所有请求');
    console.log('  3. 使用 console.clear() 清空控制台');

})();
