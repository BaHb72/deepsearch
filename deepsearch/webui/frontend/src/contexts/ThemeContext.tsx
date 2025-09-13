import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react'
import { ConfigProvider, theme as antdTheme, message } from 'antd'
import { generate, presetPalettes } from '@ant-design/colors'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import 'dayjs/locale/en'

// 主题上下文
const ThemeContext = createContext(null)

// 预设主题
const presetThemes = {
  default: {
    name: '默认蓝',
    primaryColor: '#1890ff',
    algorithm: 'defaultAlgorithm',
  },
  dark: {
    name: '暗黑',
    primaryColor: '#1890ff',
    algorithm: 'darkAlgorithm',
  },
  compact: {
    name: '紧凑',
    primaryColor: '#1890ff',
    algorithm: 'compactAlgorithm',
  },
  green: {
    name: '极光绿',
    primaryColor: '#52c41a',
    algorithm: 'defaultAlgorithm',
  },
  purple: {
    name: '薰衣紫',
    primaryColor: '#722ed1',
    algorithm: 'defaultAlgorithm',
  },
  red: {
    name: '中国红',
    primaryColor: '#f5222d',
    algorithm: 'defaultAlgorithm',
  },
  orange: {
    name: '日暮橙',
    primaryColor: '#fa8c16',
    algorithm: 'defaultAlgorithm',
  },
  cyan: {
    name: '天青色',
    primaryColor: '#13c2c2',
    algorithm: 'defaultAlgorithm',
  },
}

// 获取算法
const getAlgorithm = (algorithmName) => {
  const algorithms = {
    defaultAlgorithm: antdTheme.defaultAlgorithm,
    darkAlgorithm: antdTheme.darkAlgorithm,
    compactAlgorithm: antdTheme.compactAlgorithm,
  }
  return algorithms[algorithmName] || antdTheme.defaultAlgorithm
}

// 主题提供者组件
export const ThemeProvider = ({ children }) => {
  const [themeConfig, setThemeConfig] = useState(() => {
    const stored = localStorage.getItem('theme-config')
    if (stored) {
      try {
        return JSON.parse(stored)
      } catch {
        // 忽略解析错误
      }
    }
    return {
      theme: 'default',
      primaryColor: '#1890ff',
      borderRadius: 6,
      fontSize: 14,
      compactMode: false,
      locale: 'zh-CN',
    }
  })

  const [isDark, setIsDark] = useState(themeConfig.theme === 'dark')

  // 生成主题配置
  const antdConfig = useMemo(() => {
    const preset = presetThemes[themeConfig.theme] || presetThemes.default
    const colors = generate(themeConfig.primaryColor || preset.primaryColor)
    
    // 组合算法
    const algorithms = []
    if (preset.algorithm === 'darkAlgorithm' || isDark) {
      algorithms.push(antdTheme.darkAlgorithm)
    } else {
      algorithms.push(antdTheme.defaultAlgorithm)
    }
    if (themeConfig.compactMode) {
      algorithms.push(antdTheme.compactAlgorithm)
    }

    return {
      locale: themeConfig.locale === 'en-US' ? enUS : zhCN,
      theme: {
        algorithm: algorithms,
        token: {
          colorPrimary: themeConfig.primaryColor || preset.primaryColor,
          borderRadius: themeConfig.borderRadius || 6,
          fontSize: themeConfig.fontSize || 14,
          
          // 生成的颜色
          colorBgContainer: isDark ? '#141414' : '#ffffff',
          colorBgElevated: isDark ? '#1f1f1f' : '#ffffff',
          colorBgLayout: isDark ? '#000000' : '#f0f2f5',
          colorBorder: isDark ? '#434343' : '#d9d9d9',
          colorText: isDark ? 'rgba(255, 255, 255, 0.85)' : 'rgba(0, 0, 0, 0.88)',
          colorTextSecondary: isDark ? 'rgba(255, 255, 255, 0.65)' : 'rgba(0, 0, 0, 0.65)',
          
          // 其他 token
          colorSuccess: '#52c41a',
          colorWarning: '#faad14',
          colorError: '#ff4d4f',
          colorInfo: themeConfig.primaryColor || preset.primaryColor,
          
          // 尺寸
          controlHeight: themeConfig.compactMode ? 28 : 32,
          controlHeightLG: themeConfig.compactMode ? 36 : 40,
          controlHeightSM: themeConfig.compactMode ? 20 : 24,
          
          // 动画
          motionDurationFast: '0.1s',
          motionDurationMid: '0.2s',
          motionDurationSlow: '0.3s',
          motionEaseInOut: 'cubic-bezier(0.645, 0.045, 0.355, 1)',
          motionEaseOut: 'cubic-bezier(0.215, 0.61, 0.355, 1)',
          motionEaseIn: 'cubic-bezier(0.55, 0.055, 0.675, 0.19)',
          
          // 阴影
          boxShadow: isDark
            ? '0 1px 2px 0 rgba(0, 0, 0, 0.45), 0 1px 6px -1px rgba(0, 0, 0, 0.35), 0 2px 4px 0 rgba(0, 0, 0, 0.35)'
            : '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02)',
          boxShadowSecondary: isDark
            ? '0 6px 16px 0 rgba(0, 0, 0, 0.48), 0 3px 6px -4px rgba(0, 0, 0, 0.65), 0 9px 28px 8px rgba(0, 0, 0, 0.35)'
            : '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
        },
        components: {
          // 组件级别的主题定制
          Button: {
            colorPrimary: themeConfig.primaryColor,
            borderRadius: themeConfig.borderRadius,
          },
          Input: {
            colorPrimary: themeConfig.primaryColor,
            borderRadius: themeConfig.borderRadius,
          },
          Select: {
            colorPrimary: themeConfig.primaryColor,
            borderRadius: themeConfig.borderRadius,
          },
          Card: {
            borderRadius: themeConfig.borderRadius * 1.5,
          },
          Modal: {
            borderRadius: themeConfig.borderRadius * 1.5,
          },
          Table: {
            borderRadius: themeConfig.borderRadius,
            headerBg: isDark ? '#1f1f1f' : '#fafafa',
          },
          Tabs: {
            inkBarColor: themeConfig.primaryColor,
          },
          Layout: {
            bodyBg: isDark ? '#000000' : '#f0f2f5',
            headerBg: isDark ? '#141414' : '#ffffff',
            siderBg: isDark ? '#141414' : '#ffffff',
          },
          Menu: {
            itemBg: 'transparent',
            itemSelectedBg: `${themeConfig.primaryColor}15`,
            itemSelectedColor: themeConfig.primaryColor,
            itemHoverBg: `${themeConfig.primaryColor}08`,
          },
        },
      },
    }
  }, [themeConfig, isDark])

  // 切换主题
  const setTheme = useCallback((theme) => {
    setThemeConfig(prev => ({ ...prev, theme }))
    setIsDark(theme === 'dark')
    message.success(`已切换到${presetThemes[theme]?.name || '默认'}主题`)
  }, [])

  // 设置主色
  const setPrimaryColor = useCallback((color) => {
    setThemeConfig(prev => ({ ...prev, primaryColor: color }))
  }, [])

  // 设置圆角
  const setBorderRadius = useCallback((radius) => {
    setThemeConfig(prev => ({ ...prev, borderRadius: radius }))
  }, [])

  // 设置字号
  const setFontSize = useCallback((size) => {
    setThemeConfig(prev => ({ ...prev, fontSize: size }))
  }, [])

  // 切换紧凑模式
  const toggleCompactMode = useCallback(() => {
    setThemeConfig(prev => ({ ...prev, compactMode: !prev.compactMode }))
  }, [])

  // 切换暗黑模式
  const toggleDark = useCallback(() => {
    setIsDark(prev => !prev)
    setThemeConfig(prev => ({ ...prev, theme: !isDark ? 'dark' : 'default' }))
  }, [isDark])

  // 设置语言
  const setLocale = useCallback((locale) => {
    setThemeConfig(prev => ({ ...prev, locale }))
    dayjs.locale(locale === 'en-US' ? 'en' : 'zh-cn')
    message.success(`已切换到${locale === 'en-US' ? 'English' : '中文'}`)
  }, [])

  // 重置主题
  const resetTheme = useCallback(() => {
    const defaultConfig = {
      theme: 'default',
      primaryColor: '#1890ff',
      borderRadius: 6,
      fontSize: 14,
      compactMode: false,
      locale: 'zh-CN',
    }
    setThemeConfig(defaultConfig)
    setIsDark(false)
    message.success('主题已重置')
  }, [])

  // 保存配置到本地
  useEffect(() => {
    localStorage.setItem('theme-config', JSON.stringify(themeConfig))
  }, [themeConfig])

  // 设置 HTML 类名
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [isDark])

  // Context 值
  const contextValue = useMemo(() => ({
    themeConfig,
    isDark,
    presetThemes,
    setTheme,
    setPrimaryColor,
    setBorderRadius,
    setFontSize,
    toggleCompactMode,
    toggleDark,
    setLocale,
    resetTheme,
  }), [
    themeConfig,
    isDark,
    setTheme,
    setPrimaryColor,
    setBorderRadius,
    setFontSize,
    toggleCompactMode,
    toggleDark,
    setLocale,
    resetTheme,
  ])

  return (
    <ThemeContext.Provider value={contextValue}>
      <ConfigProvider {...antdConfig}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  )
}

// 使用主题 Hook
export const useTheme = () => {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return context
}

export default ThemeContext