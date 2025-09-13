import { useState, useEffect } from 'react'
import { Grid } from 'antd'

const { useBreakpoint } = Grid

/**
 * 响应式断点定义（基于 Ant Design 和行业最佳实践）
 * xs: < 576px  (手机)
 * sm: >= 576px (大屏手机)
 * md: >= 768px (平板)
 * lg: >= 992px (桌面)
 * xl: >= 1200px (大桌面)
 * xxl: >= 1600px (超大桌面)
 */
export interface ResponsiveInfo {
  isMobile: boolean      // < 768px
  isTablet: boolean      // 768px - 991px
  isDesktop: boolean     // >= 992px
  isLargeScreen: boolean // >= 1200px
  screenSize: 'mobile' | 'tablet' | 'desktop' | 'large'
  width: number
  height: number
  screens: Record<string, boolean>
}

/**
 * 响应式 Hook - 提供设备类型检测和响应式信息
 * @returns {ResponsiveInfo} 响应式信息对象
 */
export const useResponsive = (): ResponsiveInfo => {
  const screens = useBreakpoint()
  const [dimensions, setDimensions] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 0,
    height: typeof window !== 'undefined' ? window.innerHeight : 0
  })

  useEffect(() => {
    const handleResize = () => {
      setDimensions({
        width: window.innerWidth,
        height: window.innerHeight
      })
    }

    // 使用防抖避免频繁更新
    let timeoutId: NodeJS.Timeout
    const debouncedResize = () => {
      clearTimeout(timeoutId)
      timeoutId = setTimeout(handleResize, 150)
    }

    window.addEventListener('resize', debouncedResize)
    handleResize() // 初始化尺寸

    return () => {
      window.removeEventListener('resize', debouncedResize)
      clearTimeout(timeoutId)
    }
  }, [])

  // 设备类型判断
  const isMobile = !screens.md // < 768px
  const isTablet = !!screens.md && !screens.lg // 768px - 991px
  const isDesktop = !!screens.lg // >= 992px
  const isLargeScreen = !!screens.xl // >= 1200px

  // 获取当前屏幕尺寸类型
  const getScreenSize = (): 'mobile' | 'tablet' | 'desktop' | 'large' => {
    if (isLargeScreen) return 'large'
    if (isDesktop) return 'desktop'
    if (isTablet) return 'tablet'
    return 'mobile'
  }

  return {
    isMobile,
    isTablet,
    isDesktop,
    isLargeScreen,
    screenSize: getScreenSize(),
    width: dimensions.width,
    height: dimensions.height,
    screens
  }
}

/**
 * 获取响应式的列配置
 * @param mobile 移动端列数
 * @param tablet 平板列数
 * @param desktop 桌面端列数
 * @returns Ant Design Col 的响应式配置
 */
export const getResponsiveColumns = (
  mobile: number = 24,
  tablet: number = 12,
  desktop: number = 8
) => ({
  xs: mobile,
  sm: mobile,
  md: tablet,
  lg: desktop,
  xl: desktop,
  xxl: desktop
})

/**
 * 获取响应式的表格滚动配置
 * @param responsive 响应式信息
 * @returns Table 的 scroll 配置
 */
export const getResponsiveTableScroll = (responsive: ResponsiveInfo) => {
  if (responsive.isMobile) {
    return { x: 800 } // 移动端横向滚动
  }
  if (responsive.isTablet) {
    return { x: 1000 } // 平板横向滚动
  }
  return { x: false } // 桌面端不需要横向滚动
}

export default useResponsive