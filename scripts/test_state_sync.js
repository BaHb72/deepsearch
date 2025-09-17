/**
 * 测试组件状态同步功能
 * 验证后端恢复后组件是否自动刷新
 *
 * 使用方法：
 * 1. 在浏览器控制台中执行此脚本
 * 2. 观察组件行为
 */

(async function testStateSync() {
    console.clear();
    console.log('%c=== 组件状态同步测试 ===', 'color: #1890ff; font-size: 16px; font-weight: bold');
    console.log('');

    // 1. 模拟后端不可用
    console.group('📉 [1] 模拟后端不可用');
    try {
        // 获取 backendStatus
        const { default: backendStatus } = await import('/src/utils/backendStatus.js');

        console.log('当前后端状态:', backendStatus.isAvailable ? '✅ 可用' : '❌ 不可用');
        console.log('手动设置后端为不可用...');

        // 设置为不可用
        backendStatus.setAvailable(false);

        console.log('后端状态已设置为: ❌ 不可用');
        console.log('');
        console.log('预期行为:');
        console.log('  - 新请求被拒绝');
        console.log('  - 组件显示"正在等待后端服务恢复..."');
        console.log('  - 显示加载动画');

    } catch (error) {
        console.error('设置失败:', error);
    }
    console.groupEnd();

    // 2. 等待几秒，观察组件状态
    console.group('⏱️ [2] 等待观察');
    console.log('等待 3 秒，观察组件状态...');
    await new Promise(resolve => setTimeout(resolve, 3000));
    console.log('✅ 观察完成');
    console.groupEnd();

    // 3. 模拟后端恢复
    console.group('📈 [3] 模拟后端恢复');
    try {
        const { default: backendStatus } = await import('/src/utils/backendStatus.js');

        console.log('手动设置后端为可用...');

        // 设置为可用
        backendStatus.setAvailable(true);

        console.log('后端状态已设置为: ✅ 可用');
        console.log('');
        console.log('预期行为:');
        console.log('  - 触发所有监听器');
        console.log('  - useAsyncData 自动重试');
        console.log('  - 组件自动刷新');
        console.log('  - 显示正常内容');

    } catch (error) {
        console.error('设置失败:', error);
    }
    console.groupEnd();

    // 4. 检查监听器
    console.group('👂 [4] 检查监听器');
    try {
        const { default: backendStatus } = await import('/src/utils/backendStatus.js');

        console.log('当前监听器数量:', backendStatus.listeners.size);

        if (backendStatus.listeners.size > 0) {
            console.log('✅ 有组件正在监听后端状态变化');
        } else {
            console.warn('⚠️ 没有组件监听后端状态变化');
            console.log('可能原因:');
            console.log('  1. 组件未挂载');
            console.log('  2. useAsyncData 未正确添加监听器');
        }

    } catch (error) {
        console.error('检查失败:', error);
    }
    console.groupEnd();

    // 5. 手动触发刷新测试
    console.group('🔄 [5] 手动刷新测试');
    console.log('尝试手动触发监听器...');

    try {
        const { default: backendStatus } = await import('/src/utils/backendStatus.js');

        // 手动通知所有监听器
        backendStatus.notifyListeners(true);

        console.log('✅ 已通知所有监听器');
        console.log('如果组件实现了监听，应该会自动刷新');

    } catch (error) {
        console.error('触发失败:', error);
    }
    console.groupEnd();

    // 6. 查看控制台日志
    console.group('📝 [6] 相关日志');
    console.log('请查看控制台中的相关日志:');
    console.log('  - [useAsyncData] 后端已恢复，自动重试...');
    console.log('  - [BackendStatus] ✅ 后端服务正常');
    console.log('  - [DatabaseConfig] 开始获取数据库连接列表...');
    console.groupEnd();

    console.log('');
    console.log('%c=== 测试完成 ===', 'color: #52c41a; font-size: 16px; font-weight: bold');
    console.log('');
    console.log('💡 提示:');
    console.log('  1. 观察 DatabaseConfig 组件是否自动刷新');
    console.log('  2. 检查网络请求是否自动重发');
    console.log('  3. 查看是否有"自动重试"的日志');

    // 导出测试函数
    window.testStateSync = {
        setBackendUnavailable: () => {
            import('/src/utils/backendStatus.js').then(m => {
                m.default.setAvailable(false);
                console.log('✅ 后端已设置为不可用');
            });
        },
        setBackendAvailable: () => {
            import('/src/utils/backendStatus.js').then(m => {
                m.default.setAvailable(true);
                console.log('✅ 后端已设置为可用');
            });
        },
        checkListeners: () => {
            import('/src/utils/backendStatus.js').then(m => {
                console.log('监听器数量:', m.default.listeners.size);
                console.log('后端状态:', m.default.isAvailable ? '✅ 可用' : '❌ 不可用');
            });
        }
    };

    console.log('');
    console.log('可用的测试命令:');
    console.log('  - testStateSync.setBackendUnavailable()  // 设置后端不可用');
    console.log('  - testStateSync.setBackendAvailable()    // 设置后端可用');
    console.log('  - testStateSync.checkListeners()         // 检查监听器');

})();