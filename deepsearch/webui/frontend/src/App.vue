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
                    启动系统
                  </el-button>
                  <el-button
                      v-else
                      :loading="systemLoading"
                      size="small"
                      type="danger"
                      @click="handleSystemStop"
                  >
                    停止系统
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
import {ref, computed, onMounted, onUnmounted} from 'vue'
import {useRoute} from 'vue-router'
import {ElMessage, ElMessageBox} from 'element-plus'
import {Monitor, List, Setting, Document, TrendCharts, Moon, Sunny} from '@element-plus/icons-vue'
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
        '确定要停止系统吗？这将停止所有交易活动。',
        '系统提示',
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
/* 全局样式 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
}

/* 布局容器 */
.layout-container {
  height: 100vh;
}

/* 侧边栏 */
.layout-aside {
  background-color: #304156;

  .logo {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);

    h2 {
      color: #fff;
      font-size: 20px;
      font-weight: 600;
    }
  }

  .el-menu {
    border-right: none;
    height: calc(100% - 60px);
  }
}

/* 顶部栏 */
.layout-header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;

  .header-left h3 {
    color: #303133;
    font-size: 18px;
  }

  .system-status {
    .status-indicator {
      margin-right: 4px;
      font-size: 16px;

      &.breathing {
        animation: breathing 2s ease-in-out infinite;
      }
    }
  }
}

/* 主内容区 */
.layout-main {
  background-color: #f5f7fa;
  padding: 20px;
}

/* 页面过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 呼吸动画 */
@keyframes breathing {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

/* 暗色主题 */
.dark {
  .layout-header {
    background-color: #1f1f1f;

    .header-left h3 {
      color: #fff;
    }
  }

  .layout-main {
    background-color: #141414;
  }
}
</style>