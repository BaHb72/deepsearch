<template>
  <el-config-provider :locale="zhCn">
    <div id="app">
      <el-container class="layout-container">
        <!-- 侧边栏 -->
        <el-aside class="layout-aside" width="200px">
          <div class="logo">
            <h2>DeepSearch</h2>
          </div>
          <el-menu
              :default-active="activeMenu"
              active-text-color="#409eff"
              background-color="#304156"
              class="el-menu-vertical"
              router
              text-color="#bfcbd9"
          >
            <el-menu-item index="/">
              <el-icon>
                <Monitor/>
              </el-icon>
              <span>监控仪表板</span>
            </el-menu-item>
            <el-menu-item index="/events">
              <el-icon>
                <List/>
              </el-icon>
              <span>事件监控</span>
            </el-menu-item>
            <el-menu-item index="/config">
              <el-icon>
                <Setting/>
              </el-icon>
              <span>系统配置</span>
            </el-menu-item>
            <el-menu-item index="/logs">
              <el-icon>
                <Document/>
              </el-icon>
              <span>日志查看</span>
            </el-menu-item>
            <el-menu-item index="/trading">
              <el-icon>
                <TrendCharts/>
              </el-icon>
              <span>交易监控</span>
            </el-menu-item>
            <el-menu-item index="/data">
              <el-icon>
                <DataAnalysis/>
              </el-icon>
              <span>数据管理</span>
            </el-menu-item>
          </el-menu>
        </el-aside>

        <!-- 主内容区 -->
        <el-container>
          <!-- 顶部栏 -->
          <el-header class="layout-header">
            <div class="header-left">
              <h3>{{ pageTitle }}</h3>
            </div>
            <div class="header-right">
              <el-space>
                <!-- 系统状态指示器 -->
                <div class="system-status">
                  <el-tag :type="systemStatus.type" effect="dark">
                    <span :class="{ 'breathing': systemStatus.running }" class="status-indicator">●</span>
                    {{ systemStatus.text }}
                  </el-tag>
                </div>

                <!-- 系统控制按钮 -->
                <el-button-group>
                  <el-button
                      v-if="!systemStatus.running"
                      :loading="systemLoading"
                      size="small"
                      type="success"
                      @click="handleSystemStart"
                  >
                    启动引擎
                  </el-button>
                  <el-button
                      v-else
                      :loading="systemLoading"
                      size="small"
                      type="danger"
                      @click="handleSystemStop"
                  >
                    停止引擎
                  </el-button>
                  <el-button
                      v-if="systemStatus.running"
                      :loading="systemLoading"
                      size="small"
                      type="warning"
                      @click="handleSystemRestart"
                  >
                    重启引擎
                  </el-button>
                </el-button-group>

                <!-- 主题切换 -->
                <el-switch
                    v-model="isDark"
                    :active-icon="Moon"
                    :inactive-icon="Sunny"
                    inline-prompt
                    @change="toggleTheme"
                />
              </el-space>
            </div>
          </el-header>

          <!-- 页面内容 -->
          <el-main class="layout-main">
            <router-view v-slot="{ Component }">
              <transition mode="out-in" name="fade">
                <component :is="Component"/>
              </transition>
            </router-view>
          </el-main>
        </el-container>
      </el-container>

      <!-- 错误监控组件 -->
      <ErrorMonitor/>
    </div>
  </el-config-provider>
</template>

<script setup>
import {computed, onBeforeMount, onMounted, onUnmounted, ref} from 'vue'
import {useRoute} from 'vue-router'
import {ElLoading, ElMessage, ElMessageBox} from 'element-plus'
import {DataAnalysis, Document, List, Monitor, Moon, Setting, Sunny, TrendCharts} from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import {useSystemStore} from '@/stores/system'
import {restartSystem, startSystem, stopSystem} from '@/api/system'
import {storage, STORAGE_KEYS} from '@/utils/storage'
import ErrorMonitor from '@/components/ErrorMonitor.vue'
import backendStatus from '@/utils/backendStatus'

// 定义组件名称
defineOptions({
  name: 'App'
})

const route = useRoute()
const systemStore = useSystemStore()

// 当前激活的菜单
const activeMenu = computed(() => route.path)

// 页面标题
const pageTitle = computed(() => {
  const titles = {
    '/': '监控仪表板',
    '/events': '事件监控',
    '/config': '系统配置',
    '/logs': '日志查看',
    '/trading': '交易监控'
  }
  return titles[route.path] || 'DeepSearch'
})

// 系统状态
const systemStatus = computed(() => {
  try {
    if (systemStore.status?.engine?.running) {
      return {type: 'success', text: '系统运行中', running: true}
    }
  } catch (e) {
    console.warn('获取系统状态失败:', e)
  }
  return {type: 'info', text: '系统已停止', running: false}
})

// 系统操作加载状态
const systemLoading = ref(false)

// 是否暂停状态轮询
const pauseStatusPolling = ref(false)

// 暗色主题 - 使用安全的 storage
const isDark = ref(storage.getItem(STORAGE_KEYS.THEME) === 'dark')

// 切换主题
const toggleTheme = (value) => {
  if (value) {
    document.documentElement.classList.add('dark')
    storage.setItem(STORAGE_KEYS.THEME, 'dark')
  } else {
    document.documentElement.classList.remove('dark')
    storage.setItem(STORAGE_KEYS.THEME, 'light')
  }
}

// 启动系统
const handleSystemStart = async () => {
  // 检查后端是否可用
  if (!backendStatus.isAvailable) {
    ElMessage.error('后端服务不可用，请先启动后端服务')
    return
  }
  
  try {
    systemLoading.value = true
    pauseStatusPolling.value = true  // 暂停轮询
    const result = await startSystem()
    ElMessage.success(result.message || '系统启动成功')
    // 延迟一下再恢复轮询
    setTimeout(() => {
      pauseStatusPolling.value = false
      systemStore.fetchStatus()
    }, 1000)
  } catch (error) {
    ElMessage.error(error.message || '系统启动失败')
    pauseStatusPolling.value = false  // 失败时恢复轮询
  } finally {
    systemLoading.value = false
  }
}

// 停止系统
const handleSystemStop = async () => {
  // 检查后端是否可用
  if (!backendStatus.isAvailable) {
    ElMessage.error('后端服务不可用')
    return
  }
  
  try {
    await ElMessageBox.confirm(
        '确定要停止交易引擎吗？这将停止所有交易活动，但WebUI仍会继续运行。',
        '停止交易引擎',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
    )

    systemLoading.value = true
    pauseStatusPolling.value = true  // 暂停轮询
    const result = await stopSystem()
    ElMessage.success(result.message || '交易引擎已停止')
    // 延迟一下再恢复轮询
    setTimeout(() => {
      pauseStatusPolling.value = false
      systemStore.fetchStatus()
    }, 1000)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '系统停止失败')
    }
    pauseStatusPolling.value = false  // 失败时恢复轮询
  } finally {
    systemLoading.value = false
  }
}

// 重启系统
const handleSystemRestart = async () => {
  // 检查后端是否可用
  if (!backendStatus.isAvailable) {
    ElMessage.error('后端服务不可用')
    return
  }
  
  try {
    await ElMessageBox.confirm(
        '确定要重启交易引擎吗？这将中断当前所有交易活动并重新启动。',
        '重启交易引擎',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        }
    )

    systemLoading.value = true
    pauseStatusPolling.value = true  // 暂停轮询
    const result = await restartSystem()
    ElMessage.success(result.message || '交易引擎重启成功')
    // 延迟一下再恢复轮询
    setTimeout(() => {
      pauseStatusPolling.value = false
      systemStore.fetchStatus()
    }, 2000)  // 重启需要更长时间
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '系统重启失败')
    }
    pauseStatusPolling.value = false  // 失败时恢复轮询
  } finally {
    systemLoading.value = false
  }
}

// 定时获取系统状态
let statusTimer = null

// 后端状态监听
const handleBackendStatusChange = (available) => {
  debugLog('BACKEND', `Backend status changed: ${available ? 'available' : 'unavailable'}`)

  if (available) {
    // 后端恢复，立即获取状态
    if (!pauseStatusPolling.value && !systemLoading.value) {
      systemStore.fetchStatus().catch(err => {
        debugLog('API', 'Status fetch failed after backend recovery', {error: err.message})
      })
    }
  }
}

// 调试日志工具
const debugLog = (stage, message, data = null) => {
  const timestamp = new Date().toISOString()
  const logEntry = `[App.vue ${timestamp}] ${stage}: ${message}`
  console.log('%c' + logEntry, 'color: #409eff; font-weight: bold;', data)
}

// 在组件挂载前显示全屏loading
debugLog('INIT', '创建全屏Loading')
const loading = ElLoading.service({
  lock: true,
  text: '正在初始化 DeepSearch 系统...',
  background: 'rgba(0, 0, 0, 0.7)',
  customClass: 'deepsearch-loading'
})

// 添加Loading超时保护 - 增加超时时间到15秒
const loadingTimeout = setTimeout(() => {
  debugLog('ERROR', 'Loading超时，强制关闭', {timeout: '15秒'})
  if (loading) {
    loading.close()
    ElMessage.warning('系统初始化较慢，已自动关闭Loading。如有问题请检查后端服务状态。')
  }
}, 15000)

// 组件挂载前
onBeforeMount(() => {
  debugLog('LIFECYCLE', 'onBeforeMount执行')
})

onMounted(async () => {
  debugLog('LIFECYCLE', 'onMounted开始执行')
  const mountStartTime = Date.now()
  
  try {
    // 初始化主题
    debugLog('THEME', '初始化主题', {isDark: isDark.value})
    if (isDark.value) {
      document.documentElement.classList.add('dark')
    }

    // 检查后端状态
    debugLog('API', '检查后端状态')
    const isBackendAvailable = await backendStatus.checkStatus()

    if (isBackendAvailable) {
      // 获取系统状态
      debugLog('API', '开始获取系统状态')
      const fetchStartTime = Date.now()

      try {
        await systemStore.fetchStatus()
        const fetchDuration = Date.now() - fetchStartTime
        debugLog('API', '系统状态获取成功', {
          duration: `${fetchDuration}ms`,
          status: systemStore.status
        })
      } catch (fetchError) {
        const fetchDuration = Date.now() - fetchStartTime
        debugLog('API', '系统状态获取失败', {
          duration: `${fetchDuration}ms`,
          error: fetchError.message,
          stack: fetchError.stack
        })
        throw fetchError
      }
    } else {
      debugLog('API', '后端不可用，跳过状态获取')
    }

    // 延迟一点关闭loading，确保界面渲染完成
    debugLog('LOADING', '准备关闭Loading，延迟300ms')
    setTimeout(() => {
      if (loading) {
        debugLog('LOADING', 'Loading关闭成功')
        loading.close()
        clearTimeout(loadingTimeout) // 清除超时计时器
      }
    }, 300)

    const mountDuration = Date.now() - mountStartTime
    debugLog('LIFECYCLE', 'onMounted执行完成', {totalDuration: `${mountDuration}ms`})
    
  } catch (err) {
    const mountDuration = Date.now() - mountStartTime
    debugLog('ERROR', 'onMounted执行出错', {
      duration: `${mountDuration}ms`,
      error: err.message,
      stack: err.stack
    })
    console.warn('获取系统状态失败，将使用默认值:', err)

    // 确保Loading被关闭
    if (loading) {
      debugLog('LOADING', '错误状态下关闭Loading')
      loading.close()
      clearTimeout(loadingTimeout)
    }
  }

  // 监听后端状态变化
  backendStatus.addListener(handleBackendStatusChange)

  // 启动状态轮询
  debugLog('POLLING', '启动状态轮询定时器', {interval: '5000ms'})
  statusTimer = setInterval(async () => {
    // 如果正在进行系统操作，跳过轮询
    if (!pauseStatusPolling.value && !systemLoading.value) {
      // 先检查后端是否可用
      if (backendStatus.isAvailable) {
        debugLog('POLLING', '执行状态轮询')
        systemStore.fetchStatus().catch(err => {
          // 只在非系统操作期间才显示警告
          if (!systemLoading.value) {
            debugLog('POLLING', '状态轮询失败', {error: err.message})
            console.warn('更新系统状态失败:', err)
          }
        })
      } else {
        debugLog('POLLING', '后端不可用，跳过状态轮询')
      }
    } else {
      debugLog('POLLING', '跳过状态轮询', {
        pauseStatusPolling: pauseStatusPolling.value,
        systemLoading: systemLoading.value
      })
    }
  }, 5000) // 每5秒更新一次
})

// 组件更新时
onUpdated(() => {
  debugLog('LIFECYCLE', 'onUpdated执行', {route: route.path})
})

onUnmounted(() => {
  // 清除状态轮询定时器
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }

  // 移除后端状态监听器
  backendStatus.removeListener(handleBackendStatusChange)

  debugLog('LIFECYCLE', 'onUnmounted - cleaned up resources')
})
</script>

<style lang="scss">
@import '@/assets/styles/design-tokens.scss';

/* 布局容器 */
.layout-container {
  height: 100vh;
  background: var(--bg-color);
}

/* 侧边栏 */
.layout-aside {
  background: linear-gradient(180deg, $neutral-800 0%, $neutral-900 100%);
  box-shadow: $shadow-lg;
  transition: all $duration-base $ease-out;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(circle at top right, rgba($brand-primary, 0.1) 0%, transparent 50%),
    radial-gradient(circle at bottom left, rgba($brand-secondary, 0.1) 0%, transparent 50%);
    pointer-events: none;
  }

  .logo {
    height: 72px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.3);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    position: relative;
    overflow: hidden;

    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: -100%;
      width: 100%;
      height: 100%;
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
      animation: shimmer 3s infinite;
    }

    &::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 50%;
      transform: translateX(-50%);
      width: 60%;
      height: 1px;
      background: linear-gradient(90deg, transparent, $brand-primary, transparent);
    }

    h2 {
      color: white;
      font-size: $font-size-2xl;
      font-weight: $font-weight-bold;
      letter-spacing: 1px;
      text-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
      z-index: 1;
      display: flex;
      align-items: center;
      gap: $spacing-2;

      &::before {
        content: '⚇';
        font-size: 28px;
        @include gradient-text($brand-primary, $brand-secondary);
      }
    }
  }

  .el-menu {
    border-right: none;
    background: transparent;
    height: calc(100% - 72px);
    padding: $spacing-2 0;

    .el-menu-item {
      color: rgba(255, 255, 255, 0.7);
      transition: all $duration-base $ease-out;
      position: relative;
      margin: $spacing-1 $spacing-2;
      border-radius: $radius-base;
      height: 48px;
      line-height: 48px;

      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 4px;
        height: 0;
        background: $brand-primary;
        border-radius: $radius-sm;
        transition: height $duration-base $ease-out;
      }

      &::after {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(90deg, rgba($brand-primary, 0.15), transparent);
        opacity: 0;
        transition: opacity $duration-base;
        border-radius: $radius-base;
      }

      &:hover {
        color: white;

        &::after {
          opacity: 1;
        }
      }

      &.is-active {
        color: white;
        background: rgba($brand-primary, 0.15);
        font-weight: $font-weight-medium;

        &::before {
          height: 24px;
        }

        .el-icon {
          color: $brand-primary;
        }
      }

      .el-icon {
        font-size: 20px;
        margin-right: $spacing-3;
        transition: all $duration-base;
      }

      span {
        position: relative;
        z-index: 1;
      }
    }
  }
}

/* 顶部栏 */
.layout-header {
  background: var(--card-bg);
  box-shadow: $shadow-sm;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $spacing-6;
  transition: all $duration-base;
  position: relative;
  z-index: 10;

  &::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border-color), transparent);
  }

  .header-left {
    h3 {
      color: var(--text-primary);
      font-size: $font-size-xl;
      font-weight: $font-weight-semibold;
      margin: 0;
      display: flex;
      align-items: center;
      gap: $spacing-2;

      &::before {
        content: '';
        width: 4px;
        height: 24px;
        background: $brand-primary;
        border-radius: $radius-sm;
      }
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;

    .system-status {
      .el-tag {
        padding: 6px 16px;
        font-weight: 500;
        border-radius: 20px;

        &.el-tag--success {
          @include gradient-bg($color-success, darken($color-success, 10%));
          border: none;
          color: white;
          box-shadow: 0 2px 8px rgba($color-success, 0.3);
        }

        &.el-tag--danger {
          @include gradient-bg($color-danger, darken($color-danger, 10%));
          border: none;
          color: white;
          box-shadow: 0 2px 8px rgba($color-danger, 0.3);
        }

        &.el-tag--info {
          background: rgba($color-info, 0.1);
          border: 1px solid rgba($color-info, 0.3);
          color: $color-info;
        }
      }

      .status-indicator {
        margin-right: $spacing-2;
        font-size: 12px;
        vertical-align: middle;

        &.breathing {
          @include breathing-animation;
        }
      }
    }

    .el-button-group {
      .el-button {
        border-radius: 8px;
        font-weight: 500;

        &:first-child {
          border-top-right-radius: 0;
          border-bottom-right-radius: 0;
        }

        &:last-child {
          border-top-left-radius: 0;
          border-bottom-left-radius: 0;
        }
      }
    }

    .el-switch {
      --el-switch-on-color: #{$brand-primary};

      :deep(.el-switch__core) {
        border-radius: $radius-full;
        box-shadow: $shadow-inner;
      }
    }
  }
}

/* 主内容区 */
.layout-main {
  background: var(--bg-color);
  padding: 0;
  overflow: auto;
  height: calc(100vh - 60px);
  position: relative;

  @include custom-scrollbar(12px, var(--bg-color), var(--border-color));
}

/* 页面过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: all $duration-base $ease-out;
}

.fade-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* 动画效果 */
@keyframes shimmer {
  to {
    left: 100%;
  }
}

/* 状态按钮组 */
.el-button-group {
  .el-button {
    &--success {
      &:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: $shadow-success;
      }
    }

    &--danger {
      &:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: $shadow-danger;
      }
    }

    &--warning {
      &:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba($color-warning, 0.4);
      }
    }
  }
}

/* 暗色主题 */
.dark {
  .layout-aside {
    background: linear-gradient(180deg, $dark-bg-tertiary 0%, $dark-bg-secondary 100%);

    &::before {
      background: radial-gradient(circle at top right, rgba($brand-primary, 0.15) 0%, transparent 50%),
      radial-gradient(circle at bottom left, rgba($brand-secondary, 0.15) 0%, transparent 50%);
    }

    .logo {
      background: rgba(0, 0, 0, 0.5);
      border-bottom-color: rgba(255, 255, 255, 0.05);
    }

    .el-menu-item {
      &.is-active {
        background: rgba($brand-primary, 0.2);
      }
    }
  }

  .layout-header {
    box-shadow: 0 2px 16px rgba(0, 0, 0, 0.5);
    background: $dark-bg-elevated;

    &::after {
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.05), transparent);
    }
  }

  .layout-main {
    background: $dark-bg-primary;
  }
}

/* 响应式 */
@media (max-width: $breakpoint-md) {
  .layout-aside {
    width: 180px !important;

    .logo h2 {
      font-size: $font-size-lg;
    }

    .el-menu-item {
      height: 44px;
      line-height: 44px;
      margin: $spacing-1;

      .el-icon {
        font-size: 18px;
      }
    }
  }
  
  .layout-header {
    padding: 0 $spacing-4;
    
    .header-left h3 {
      font-size: $font-size-base;

      &::before {
        height: 20px;
      }
    }

    .header-right {
      gap: $spacing-2;

      .system-status {
        .el-tag {
          padding: $spacing-1 $spacing-2;
          font-size: $font-size-xs;
        }
      }
      
      .el-button {
        padding: $spacing-2 $spacing-3;
        font-size: $font-size-xs;
        height: 32px;
      }
    }
  }
}

/* 快捷键提示 */
.el-menu-item {
  position: relative;

  &[data-shortcut]::after {
    content: attr(data-shortcut);
    position: absolute;
    right: $spacing-4;
    top: 50%;
    transform: translateY(-50%);
    font-size: $font-size-xs;
    color: rgba(255, 255, 255, 0.4);
    background: rgba(0, 0, 0, 0.2);
    padding: 2px 6px;
    border-radius: $radius-sm;
    font-family: $font-mono;
  }
}
</style>

<style>
/* 自定义 ElLoading 样式 */
.deepsearch-loading {
  .el-loading-spinner {
    margin-top: -40px;
  }

  .el-loading-spinner .circular {
    width: 50px;
    height: 50px;
    animation: loading-rotate 2s linear infinite;
  }

  .el-loading-spinner .path {
    stroke: #409eff;
    stroke-width: 3;
    animation: loading-dash 1.5s ease-in-out infinite;
  }

  .el-loading-text {
    margin-top: 20px;
    font-size: 16px;
    color: #409eff;
    font-weight: 500;
    letter-spacing: 1px;
  }
}

@keyframes loading-rotate {
  100% {
    transform: rotate(360deg);
  }
}

@keyframes loading-dash {
  0% {
    stroke-dasharray: 1, 200;
    stroke-dashoffset: 0;
  }
  50% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -40px;
  }
  100% {
    stroke-dasharray: 90, 150;
    stroke-dashoffset: -120px;
  }
}
</style>