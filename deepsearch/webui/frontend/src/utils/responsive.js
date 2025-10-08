/**
 * 响应式布局工具
 * 提供断点检测、响应式配置等功能
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'

// 响应式断点定义（与 Element Plus 保持一致）
export const BREAKPOINTS = {
  xs: 768,   // <768px 手机
  sm: 992,   // >=768px 平板
  md: 1200,  // >=992px 小屏电脑
  lg: 1920,  // >=1200px 标准电脑
  xl: Infinity // >=1920px 大屏
}

// 设备类型枚举
export const DEVICE_TYPES = {
  MOBILE: 'mobile',
  TABLET: 'tablet',
  DESKTOP: 'desktop',
  WIDESCREEN: 'widescreen'
}

/**
 * 响应式管理器
 */
class ResponsiveManager {
  constructor() {
    this.listeners = new Set()
    this.currentBreakpoint = ref('lg')
    this.screenWidth = ref(window.innerWidth)
    this.screenHeight = ref(window.innerHeight)
    this.deviceType = ref(this.getDeviceType())
    this.orientation = ref(this.getOrientation())
    
    this.init()
  }

  init() {
    this.updateBreakpoint()
    window.addEventListener('resize', this.handleResize)
    window.addEventListener('orientationchange', this.handleOrientationChange)
  }

  destroy() {
    window.removeEventListener('resize', this.handleResize)
    window.removeEventListener('orientationchange', this.handleOrientationChange)
    this.listeners.clear()
  }

  handleResize = () => {
    this.screenWidth.value = window.innerWidth
    this.screenHeight.value = window.innerHeight
    this.updateBreakpoint()
    this.deviceType.value = this.getDeviceType()
    this.notifyListeners()
  }

  handleOrientationChange = () => {
    this.orientation.value = this.getOrientation()
    this.notifyListeners()
  }

  updateBreakpoint() {
    const width = window.innerWidth
    if (width < BREAKPOINTS.xs) {
      this.currentBreakpoint.value = 'xs'
    } else if (width < BREAKPOINTS.sm) {
      this.currentBreakpoint.value = 'sm'
    } else if (width < BREAKPOINTS.md) {
      this.currentBreakpoint.value = 'md'
    } else if (width < BREAKPOINTS.lg) {
      this.currentBreakpoint.value = 'lg'
    } else {
      this.currentBreakpoint.value = 'xl'
    }
  }

  getDeviceType() {
    const width = window.innerWidth
    if (width < BREAKPOINTS.xs) {
      return DEVICE_TYPES.MOBILE
    } else if (width < BREAKPOINTS.sm) {
      return DEVICE_TYPES.TABLET
    } else if (width < BREAKPOINTS.lg) {
      return DEVICE_TYPES.DESKTOP
    } else {
      return DEVICE_TYPES.WIDESCREEN
    }
  }

  getOrientation() {
    return window.innerHeight > window.innerWidth ? 'portrait' : 'landscape'
  }

  isBreakpoint(breakpoint) {
    const breakpointOrder = ['xs', 'sm', 'md', 'lg', 'xl']
    const currentIndex = breakpointOrder.indexOf(this.currentBreakpoint.value)
    const targetIndex = breakpointOrder.indexOf(breakpoint)
    return currentIndex <= targetIndex
  }

  isMobile() {
    return this.deviceType.value === DEVICE_TYPES.MOBILE
  }

  isTablet() {
    return this.deviceType.value === DEVICE_TYPES.TABLET
  }

  isDesktop() {
    return this.deviceType.value === DEVICE_TYPES.DESKTOP || 
           this.deviceType.value === DEVICE_TYPES.WIDESCREEN
  }

  isTouch() {
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0
  }

  addListener(callback) {
    this.listeners.add(callback)
  }

  removeListener(callback) {
    this.listeners.delete(callback)
  }

  notifyListeners() {
    this.listeners.forEach(callback => {
      callback({
        breakpoint: this.currentBreakpoint.value,
        deviceType: this.deviceType.value,
        screenWidth: this.screenWidth.value,
        screenHeight: this.screenHeight.value,
        orientation: this.orientation.value
      })
    })
  }

  getLayoutConfig() {
    const configs = {
      [DEVICE_TYPES.MOBILE]: {
        columns: 1,
        gutter: 10,
        margin: 10,
        cardColumns: 1,
        tablePageSize: 10,
        chartHeight: 250,
        sidebarCollapsed: true,
        showMobileMenu: true
      },
      [DEVICE_TYPES.TABLET]: {
        columns: 2,
        gutter: 16,
        margin: 16,
        cardColumns: 2,
        tablePageSize: 20,
        chartHeight: 300,
        sidebarCollapsed: false,
        showMobileMenu: false
      },
      [DEVICE_TYPES.DESKTOP]: {
        columns: 3,
        gutter: 20,
        margin: 20,
        cardColumns: 3,
        tablePageSize: 50,
        chartHeight: 400,
        sidebarCollapsed: false,
        showMobileMenu: false
      },
      [DEVICE_TYPES.WIDESCREEN]: {
        columns: 4,
        gutter: 24,
        margin: 24,
        cardColumns: 4,
        tablePageSize: 100,
        chartHeight: 500,
        sidebarCollapsed: false,
        showMobileMenu: false
      }
    }
    return configs[this.deviceType.value]
  }
}

// 创建单例
export const responsiveManager = new ResponsiveManager()

/**
 * 响应式 Hook
 */
export function useResponsive() {
  const breakpoint = computed(() => responsiveManager.currentBreakpoint.value)
  const deviceType = computed(() => responsiveManager.deviceType.value)
  const screenWidth = computed(() => responsiveManager.screenWidth.value)
  const screenHeight = computed(() => responsiveManager.screenHeight.value)
  const orientation = computed(() => responsiveManager.orientation.value)
  const layoutConfig = computed(() => responsiveManager.getLayoutConfig())

  const isMobile = computed(() => responsiveManager.isMobile())
  const isTablet = computed(() => responsiveManager.isTablet())
  const isDesktop = computed(() => responsiveManager.isDesktop())
  const isTouch = computed(() => responsiveManager.isTouch())

  const isBreakpoint = (bp) => responsiveManager.isBreakpoint(bp)

  // 响应式样式
  const responsiveStyle = computed(() => {
    const config = layoutConfig.value
    return {
      padding: `${config.margin}px`,
      gap: `${config.gutter}px`
    }
  })

  // 响应式类名
  const responsiveClass = computed(() => {
    return [
      `device-${deviceType.value}`,
      `breakpoint-${breakpoint.value}`,
      `orientation-${orientation.value}`,
      isTouch.value ? 'touch-device' : 'non-touch-device'
    ]
  })

  return {
    breakpoint,
    deviceType,
    screenWidth,
    screenHeight,
    orientation,
    layoutConfig,
    isMobile,
    isTablet,
    isDesktop,
    isTouch,
    isBreakpoint,
    responsiveStyle,
    responsiveClass
  }
}

/**
 * 响应式容器 Hook
 */
export function useResponsiveContainer(containerRef) {
  const containerWidth = ref(0)
  const containerHeight = ref(0)
  const containerColumns = ref(1)

  const updateContainerSize = () => {
    if (containerRef.value) {
      const rect = containerRef.value.getBoundingClientRect()
      containerWidth.value = rect.width
      containerHeight.value = rect.height
      
      // 根据容器宽度计算列数
      if (containerWidth.value < 600) {
        containerColumns.value = 1
      } else if (containerWidth.value < 900) {
        containerColumns.value = 2
      } else if (containerWidth.value < 1200) {
        containerColumns.value = 3
      } else {
        containerColumns.value = 4
      }
    }
  }

  let resizeObserver = null

  onMounted(() => {
    updateContainerSize()
    
    if (containerRef.value && window.ResizeObserver) {
      resizeObserver = new ResizeObserver(updateContainerSize)
      resizeObserver.observe(containerRef.value)
    }
  })

  onUnmounted(() => {
    if (resizeObserver) {
      resizeObserver.disconnect()
    }
  })

  return {
    containerWidth,
    containerHeight,
    containerColumns
  }
}

/**
 * 响应式网格布局 Hook
 */
export function useResponsiveGrid(options = {}) {
  const {
    minItemWidth = 200,
    maxColumns = 6,
    gutter = 16
  } = options

  const { screenWidth, deviceType } = useResponsive()

  const gridConfig = computed(() => {
    const width = screenWidth.value
    const availableWidth = width - (gutter * 2)
    
    // 计算列数
    let columns = Math.floor(availableWidth / minItemWidth)
    columns = Math.max(1, Math.min(columns, maxColumns))
    
    // 根据设备类型调整
    if (deviceType.value === DEVICE_TYPES.MOBILE) {
      columns = Math.min(columns, 2)
    } else if (deviceType.value === DEVICE_TYPES.TABLET) {
      columns = Math.min(columns, 3)
    }

    return {
      columns,
      gutter,
      itemWidth: (availableWidth - (gutter * (columns - 1))) / columns
    }
  })

  const gridStyle = computed(() => ({
    display: 'grid',
    gridTemplateColumns: `repeat(${gridConfig.value.columns}, 1fr)`,
    gap: `${gridConfig.value.gutter}px`,
    width: '100%'
  }))

  return {
    gridConfig,
    gridStyle
  }
}

/**
 * 响应式表格 Hook
 */
export function useResponsiveTable() {
  const { isMobile, isTablet, layoutConfig } = useResponsive()

  const tableConfig = computed(() => {
    const config = layoutConfig.value
    
    return {
      pageSize: config.tablePageSize,
      showPagination: !isMobile.value,
      showSelection: !isMobile.value,
      showIndex: !isMobile.value,
      scrollX: isMobile.value || isTablet.value,
      fixedColumns: isMobile.value ? [] : ['action'],
      hiddenColumns: isMobile.value ? ['create_time', 'update_time'] : [],
      rowHeight: isMobile.value ? 60 : 48
    }
  })

  return {
    tableConfig
  }
}

/**
 * 响应式图表 Hook
 */
export function useResponsiveChart() {
  const { layoutConfig, deviceType } = useResponsive()

  const chartConfig = computed(() => {
    const config = layoutConfig.value
    const baseConfig = {
      height: config.chartHeight,
      animationDuration: deviceType.value === DEVICE_TYPES.MOBILE ? 300 : 500,
      dataZoom: deviceType.value !== DEVICE_TYPES.MOBILE,
      toolbox: deviceType.value === DEVICE_TYPES.DESKTOP || 
               deviceType.value === DEVICE_TYPES.WIDESCREEN
    }

    // 移动端特殊配置
    if (deviceType.value === DEVICE_TYPES.MOBILE) {
      return {
        ...baseConfig,
        legend: { show: false },
        grid: {
          top: 20,
          right: 10,
          bottom: 30,
          left: 40
        },
        xAxis: {
          axisLabel: {
            rotate: 45,
            interval: 'auto'
          }
        }
      }
    }

    // 桌面端配置
    return {
      ...baseConfig,
      legend: { show: true },
      grid: {
        top: 60,
        right: 40,
        bottom: 60,
        left: 60
      },
      xAxis: {
        axisLabel: {
          rotate: 0,
          interval: 'auto'
        }
      }
    }
  })

  return {
    chartConfig
  }
}

export default responsiveManager