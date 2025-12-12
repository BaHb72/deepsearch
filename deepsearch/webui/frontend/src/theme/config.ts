import {theme} from 'antd'
import type {ThemeConfig} from 'antd/es/config-provider/context'

export type ThemeMode = 'light' | 'dark'

export const DEFAULT_THEME_MODE: ThemeMode = 'light'

const baseTokens = {
    colorPrimary: '#3e79f7', // A more sophisticated Tech Blue
    colorSuccess: '#30d158', // iOS-like success green
    colorWarning: '#ff9f0a', // iOS-like warning orange
    colorError: '#ff453a',   // iOS-like error red
    colorInfo: '#3e79f7',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBgLayout: '#f4f6f9', // Very light cool gray
    colorText: '#1f1f1f',
    colorTextSecondary: 'rgba(0, 0, 0, 0.65)',
    colorTextTertiary: 'rgba(0, 0, 0, 0.45)',
    colorTextQuaternary: 'rgba(0, 0, 0, 0.25)',
    borderRadius: 8,
    borderRadiusLG: 12,
    borderRadiusSM: 4,
    fontSize: 14,
    fontSizeLG: 16,
    fontSizeSM: 12,
    fontFamily:
        'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    boxShadow:
        '0 2px 12px 0 rgba(0, 0, 0, 0.05)', // Softer, more diffuse shadow
    boxShadowSecondary:
        '0 6px 16px -8px rgba(0, 0, 0, 0.08), 0 9px 28px 0 rgba(0, 0, 0, 0.05), 0 12px 48px 16px rgba(0, 0, 0, 0.03)',
    controlHeight: 38, // Slightly taller for modern feel
    controlHeightLG: 46,
    controlHeightSM: 28,
} satisfies ThemeConfig['token']

const componentTokens = {
    Button: {
        borderRadius: 6,
        controlHeight: 38,
        colorPrimary: '#3e79f7',
    },
    Input: {
        borderRadius: 6,
        colorBgContainer: '#ffffff',
        activeBorderColor: '#3e79f7',
        hoverBorderColor: '#3e79f7',
    },
    Select: {
        borderRadius: 6,
    },
    Layout: {
        bodyBg: '#f4f6f9',
        headerBg: '#ffffff',
        headerHeight: 56, // Slightly compact header
        headerPadding: '0 24px',
        siderBg: '#ffffff',
    },
    Menu: {
        itemBorderRadius: 6,
        itemSelectedBg: 'rgba(62, 121, 247, 0.08)',
        itemSelectedColor: '#3e79f7',
        itemActiveBg: 'rgba(62, 121, 247, 0.12)',
        itemHoverBg: 'rgba(0, 0, 0, 0.03)',
    },
    Card: {
        headerBg: 'transparent',
        headerFontSize: 16,
        headerHeight: 56, // Taller header for cards
        borderRadiusLG: 12, // More rounded cards
        boxShadowTertiary: '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px 0 rgba(0, 0, 0, 0.02)', // Subtle card shadow
    },
    Table: {
        headerBg: '#fafafa',
        headerColor: 'rgba(0, 0, 0, 0.88)',
        headerSortActiveBg: '#f0f0f0',
        borderRadiusLG: 8,
        headerSplitColor: 'transparent', // Cleaner headers
    },
    Tabs: {
        itemSelectedColor: '#3e79f7',
        inkBarColor: '#3e79f7',
    },
    Tag: {
        borderRadius: 4,
    },
} satisfies NonNullable<ThemeConfig['components']>

const darkTokens: ThemeConfig['token'] = {
    ...baseTokens,
    colorBgContainer: '#141414',
    colorBgElevated: '#1f1f1f',
    colorBgLayout: '#000000',
    colorBorder: '#434343',
    colorBorderSecondary: '#303030',
    colorText: 'rgba(255, 255, 255, 0.85)',
    colorTextSecondary: 'rgba(255, 255, 255, 0.65)',
    colorTextTertiary: 'rgba(255, 255, 255, 0.45)',
    colorTextQuaternary: 'rgba(255, 255, 255, 0.25)',
}

export const lightTheme: ThemeConfig = {
    token: baseTokens,
    algorithm: theme.defaultAlgorithm,
    components: componentTokens,
}

export const darkTheme: ThemeConfig = {
    token: darkTokens,
    algorithm: theme.darkAlgorithm,
    components: componentTokens,
}

export function resolveThemeMode(storage?: Pick<Storage, 'getItem'>): ThemeMode {
    try {
        const source = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined)
        if (!source) {
            return DEFAULT_THEME_MODE
        }
        return source.getItem('theme') === 'dark' ? 'dark' : 'light'
    } catch {
        return DEFAULT_THEME_MODE
    }
}

export function getThemeConfig(mode: ThemeMode): ThemeConfig {
    return mode === 'dark' ? darkTheme : lightTheme
}
