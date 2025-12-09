import React, {createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState,} from 'react'
import {ConfigProvider, message, theme as antdTheme} from 'antd'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import 'dayjs/locale/en'

type ThemeLocale = 'zh-CN' | 'en-US'

const presetThemes = {
  default: {
      name: '默认主题',
    primaryColor: '#1890ff',
    algorithm: 'defaultAlgorithm',
  },
  dark: {
      name: '暗色主题',
    primaryColor: '#1890ff',
    algorithm: 'darkAlgorithm',
  },
  compact: {
      name: '紧凑模式',
    primaryColor: '#1890ff',
    algorithm: 'compactAlgorithm',
  },
  green: {
      name: '青草绿',
    primaryColor: '#52c41a',
    algorithm: 'defaultAlgorithm',
  },
  purple: {
      name: '魅力紫',
    primaryColor: '#722ed1',
    algorithm: 'defaultAlgorithm',
  },
  red: {
    name: '中国红',
    primaryColor: '#f5222d',
    algorithm: 'defaultAlgorithm',
  },
  orange: {
      name: '活力橙',
    primaryColor: '#fa8c16',
    algorithm: 'defaultAlgorithm',
  },
  cyan: {
      name: '清新蓝',
    primaryColor: '#13c2c2',
    algorithm: 'defaultAlgorithm',
  },
} as const

type ThemeKey = keyof typeof presetThemes
type ThemeAlgorithmName = (typeof presetThemes)[ThemeKey]['algorithm']
type AlgorithmFn = typeof antdTheme.defaultAlgorithm

interface ThemeConfigState {
    theme: ThemeKey
    primaryColor: string
    borderRadius: number
    fontSize: number
    compactMode: boolean
    locale: ThemeLocale
}

interface ThemeContextValue {
    themeConfig: ThemeConfigState
    isDark: boolean
    presetThemes: typeof presetThemes
    setTheme: (theme: ThemeKey) => void
    toggleTheme: (checked: boolean) => void
    setPrimaryColor: (color: string) => void
    setBorderRadius: (radius: number) => void
    setFontSize: (size: number) => void
    toggleCompactMode: () => void
    toggleDark: () => void
    setLocale: (locale: ThemeLocale) => void
    resetTheme: () => void
}

const THEME_STORAGE_KEY = 'theme-config'

const DEFAULT_THEME_CONFIG: ThemeConfigState = {
    theme: 'default',
    primaryColor: '#1890ff',
    borderRadius: 6,
    fontSize: 14,
    compactMode: false,
    locale: 'zh-CN',
}

function parseThemeConfig(raw: string | null): ThemeConfigState {
    if (!raw) {
        return DEFAULT_THEME_CONFIG
    }

    try {
        const parsed = JSON.parse(raw) as Partial<ThemeConfigState>
        return {
            theme: (parsed.theme && presetThemes[parsed.theme]) ? parsed.theme : DEFAULT_THEME_CONFIG.theme,
            primaryColor: parsed.primaryColor || DEFAULT_THEME_CONFIG.primaryColor,
            borderRadius: typeof parsed.borderRadius === 'number' ? parsed.borderRadius : DEFAULT_THEME_CONFIG.borderRadius,
            fontSize: typeof parsed.fontSize === 'number' ? parsed.fontSize : DEFAULT_THEME_CONFIG.fontSize,
            compactMode: Boolean(parsed.compactMode),
            locale: parsed.locale === 'en-US' ? 'en-US' : DEFAULT_THEME_CONFIG.locale,
        }
    } catch {
        return DEFAULT_THEME_CONFIG
    }
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export const ThemeProvider: React.FC<{ children?: ReactNode }> = ({children}) => {
    const [themeConfig, setThemeConfig] = useState<ThemeConfigState>(() =>
        parseThemeConfig(typeof window !== 'undefined' ? localStorage.getItem(THEME_STORAGE_KEY) : null)
    )
    const [isDark, setIsDark] = useState<boolean>(themeConfig.theme === 'dark')

    const mapAlgorithm = useCallback(
        (name: ThemeAlgorithmName, darkMode: boolean): AlgorithmFn[] => {
            const algorithms: AlgorithmFn[] = []

            if (name === 'darkAlgorithm' || darkMode) {
                algorithms.push(antdTheme.darkAlgorithm as AlgorithmFn)
            } else {
                algorithms.push(antdTheme.defaultAlgorithm)
            }

            if (name === 'compactAlgorithm' || themeConfig.compactMode) {
                algorithms.push(antdTheme.compactAlgorithm as AlgorithmFn)
            }

            return algorithms
        },
        [themeConfig.compactMode]
    )

    const antdConfig = useMemo(() => {
        const preset = presetThemes[themeConfig.theme]
        const algorithms = mapAlgorithm(preset.algorithm, isDark)
        const primaryColor = themeConfig.primaryColor || preset.primaryColor

    return {
      locale: themeConfig.locale === 'en-US' ? enUS : zhCN,
      theme: {
        algorithm: algorithms,
        token: {
            colorPrimary: primaryColor,
            borderRadius: themeConfig.borderRadius,
            fontSize: themeConfig.fontSize,
          colorBgContainer: isDark ? '#141414' : '#ffffff',
          colorBgElevated: isDark ? '#1f1f1f' : '#ffffff',
          colorBgLayout: isDark ? '#000000' : '#f0f2f5',
          colorBorder: isDark ? '#434343' : '#d9d9d9',
          colorText: isDark ? 'rgba(255, 255, 255, 0.85)' : 'rgba(0, 0, 0, 0.88)',
          colorTextSecondary: isDark ? 'rgba(255, 255, 255, 0.65)' : 'rgba(0, 0, 0, 0.65)',
          colorSuccess: '#52c41a',
          colorWarning: '#faad14',
          colorError: '#ff4d4f',
            colorInfo: primaryColor,
          controlHeight: themeConfig.compactMode ? 28 : 32,
          controlHeightLG: themeConfig.compactMode ? 36 : 40,
          controlHeightSM: themeConfig.compactMode ? 20 : 24,
          motionDurationFast: '0.1s',
          motionDurationMid: '0.2s',
          motionDurationSlow: '0.3s',
          motionEaseInOut: 'cubic-bezier(0.645, 0.045, 0.355, 1)',
          motionEaseOut: 'cubic-bezier(0.215, 0.61, 0.355, 1)',
          motionEaseIn: 'cubic-bezier(0.55, 0.055, 0.675, 0.19)',
        },
        components: {
          Layout: {
            headerBg: isDark ? '#141414' : '#ffffff',
            siderBg: isDark ? '#141414' : '#ffffff',
          },
          Menu: {
            itemBg: 'transparent',
              itemSelectedBg: `${primaryColor}15`,
              itemSelectedColor: primaryColor,
              itemHoverBg: `${primaryColor}0D`,
          },
        },
      },
    }
    }, [isDark, mapAlgorithm, themeConfig])

    const setTheme = useCallback((theme: ThemeKey) => {
        setThemeConfig((prev) => ({...prev, theme}))
    setIsDark(theme === 'dark')
        message.success(`已切换为${presetThemes[theme]?.name ?? presetThemes.default.name}`)
  }, [])

    const toggleTheme = useCallback(
        (checked: boolean) => {
            setIsDark(checked)
            setThemeConfig((prev) => ({...prev, theme: checked ? 'dark' : 'default'}))
            message.success(`已切换为${checked ? presetThemes.dark.name : presetThemes.default.name}`)
        },
        []
    )

    const setPrimaryColor = useCallback((color: string) => {
        setThemeConfig((prev) => ({...prev, primaryColor: color}))
  }, [])

    const setBorderRadius = useCallback((radius: number) => {
        setThemeConfig((prev) => ({...prev, borderRadius: radius}))
  }, [])

    const setFontSize = useCallback((size: number) => {
        setThemeConfig((prev) => ({...prev, fontSize: size}))
  }, [])

  const toggleCompactMode = useCallback(() => {
      setThemeConfig((prev) => ({...prev, compactMode: !prev.compactMode}))
  }, [])

  const toggleDark = useCallback(() => {
      setIsDark((prev) => !prev)
      setThemeConfig((prev) => ({
          ...prev,
          theme: prev.theme === 'dark' ? 'default' : 'dark',
      }))
  }, [])

    const setLocale = useCallback((locale: ThemeLocale) => {
        setThemeConfig((prev) => ({...prev, locale}))
    dayjs.locale(locale === 'en-US' ? 'en' : 'zh-cn')
        message.success(`语言已切换为${locale === 'en-US' ? 'English' : '简体中文'}`)
  }, [])

  const resetTheme = useCallback(() => {
      setThemeConfig(DEFAULT_THEME_CONFIG)
    setIsDark(false)
      dayjs.locale('zh-cn')
      message.success('主题配置已重置')
  }, [])

  useEffect(() => {
      if (typeof window === 'undefined') {
          return
      }
      localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify(themeConfig))
  }, [themeConfig])

    useEffect(() => {
        dayjs.locale(themeConfig.locale === 'en-US' ? 'en' : 'zh-cn')
    }, [themeConfig.locale])

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [isDark])

    const contextValue = useMemo<ThemeContextValue>(
        () => ({
            themeConfig,
            isDark,
            presetThemes,
            setTheme,
            toggleTheme,
            setPrimaryColor,
            setBorderRadius,
            setFontSize,
            toggleCompactMode,
            toggleDark,
            setLocale,
            resetTheme,
        }),
        [
            themeConfig,
            isDark,
            setTheme,
            setPrimaryColor,
            setBorderRadius,
            setFontSize,
            toggleCompactMode,
            toggleDark,
            toggleTheme,
            setLocale,
            resetTheme,
        ]
    )

  return (
    <ThemeContext.Provider value={contextValue}>
        <ConfigProvider {...antdConfig}>{children}</ConfigProvider>
    </ThemeContext.Provider>
  )
}

export const useTheme = (): ThemeContextValue => {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return context
}

export default ThemeContext
