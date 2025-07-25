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
    </div>
  </el-config-provider>
</template>

<script setup>
import {computed, onMounted, onUnmounted, ref} from 'vue'
import {useRoute} from 'vue-router'
import {ElMessage, ElMessageBox} from 'element-plus'
import {Document, List, Monitor, Moon, Setting, Sunny, TrendCharts} from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import {useSystemStore} from '@/stores/system'
import {startSystem, stopSystem} from '@/api/system'
import {storage, STORAGE_KEYS} from '@/utils/storage'

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
  try {
    systemLoading.value = true
    const result = await startSystem()
    ElMessage.success(result.message || '系统启动成功')
    systemStore.fetchStatus()
  } catch (error) {
    ElMessage.error(error.message || '系统启动失败')
  } finally {
    systemLoading.value = false
  }
}

// 停止系统
const handleSystemStop = async () => {
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
    const result = await stopSystem()
    ElMessage.success(result.message || '系统停止成功')
    systemStore.fetchStatus()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '系统停止失败')
    }
  } finally {
    systemLoading.value = false
  }
}

// 定时获取系统状态
let statusTimer = null

onMounted(() => {
  // 初始化主题
  if (isDark.value) {
    document.documentElement.classList.add('dark')
  }

  // 获取系统状态
  systemStore.fetchStatus().catch(err => {
    console.warn('获取系统状态失败，将使用默认值:', err)
  })

  statusTimer = setInterval(() => {
    systemStore.fetchStatus().catch(err => {
      console.warn('更新系统状态失败:', err)
    })
  }, 5000) // 每5秒更新一次
})

onUnmounted(() => {
  if (statusTimer) {
    clearInterval(statusTimer)
  }
})
</script>

<style lang="scss">
/* 布局容器 */
.layout-container {
  height: 100vh;
  background: var(--bg-color);
}

/* 侧边栏 */
.layout-aside {
  background: linear-gradient(180deg, #2b3144 0%, #1f2332 100%);
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
  transition: all 0.3s;

  .logo {
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.2);
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

    h2 {
      color: #fff;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: 1px;
      text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
      z-index: 1;
    }
  }

  .el-menu {
    border-right: none;
    background: transparent;
    height: calc(100% - 64px);

    .el-menu-item {
      color: rgba(255, 255, 255, 0.8);
      transition: all 0.3s;
      position: relative;

      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 3px;
        background: var(--primary-color);
        transform: scaleY(0);
        transition: transform 0.3s;
      }

      &:hover {
        color: #fff;
        background: rgba(255, 255, 255, 0.1);
      }

      &.is-active {
        color: #fff;
        background: rgba(64, 158, 255, 0.2);

        &::before {
          transform: scaleY(1);
        }
      }

      .el-icon {
        font-size: 18px;
        margin-right: 10px;
      }
    }
  }
}

/* 顶部栏 */
.layout-header {
  background: var(--card-bg);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  transition: all 0.3s;

  .header-left {
    h3 {
      color: var(--text-primary);
      font-size: 20px;
      font-weight: 600;
      margin: 0;
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
          background: linear-gradient(135deg, #84cc16 0%, #22c55e 100%);
          border: none;
          color: #fff;
        }

        &.el-tag--danger {
          background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
          border: none;
          color: #fff;
        }
      }

      .status-indicator {
        margin-right: 6px;
        font-size: 12px;
        vertical-align: middle;

        &.breathing {
          animation: breathing 2s ease-in-out infinite;
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
      --el-switch-on-color: var(--primary-color);
    }
  }
}

/* 主内容区 */
.layout-main {
  background: var(--bg-color);
  padding: 0;
  overflow: auto;
  height: calc(100vh - 60px);
}

/* 页面过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: all 0.3s ease;
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
@keyframes breathing {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.6;
    transform: scale(1.1);
  }
}

@keyframes shimmer {
  to {
    left: 100%;
  }
}

/* 暗色主题 */
.dark {
  .layout-aside {
    background: linear-gradient(180deg, #1a1a1a 0%, #0f0f0f 100%);

    .logo {
      background: rgba(0, 0, 0, 0.5);
    }

    .el-menu-item {
      &.is-active {
        background: rgba(64, 158, 255, 0.3);
      }
    }
  }

  .layout-header {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .layout-aside {
    width: 180px !important;
  }
  
  .layout-header {
    padding: 0 16px;
    
    .header-left h3 {
      font-size: 16px;
    }

    .header-right {
      gap: 8px;

      .el-button {
        padding: 8px 12px;
        font-size: 12px;
      }
    }
  }
}
</style>