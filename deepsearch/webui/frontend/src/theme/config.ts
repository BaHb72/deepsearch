import { theme } from 'antd'
import type { ThemeConfig } from 'antd/es/config-provider/context'

export type ThemeMode = 'light' | 'dark'

export const DEFAULT_THEME_MODE: ThemeMode = 'light'

const baseTokens = {
    colorPrimary: '#1677ff', // Ant Design v5 default blue, more vibrant
    colorSuccess: '#52c41a',
    colorWarning: '#faad14',
    colorError: '#ff4d4f',
    colorInfo: '#1677ff',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBgLayout: '#f5f5f5', // Slightly lighter gray for modern feel
    colorBgSpotlight: '#ffffff',
    colorBorder: '#d9d9d9',
    colorBorderSecondary: '#f0f0f0',
    colorText: 'rgba(0, 0, 0, 0.88)',
    colorTextSecondary: 'rgba(0, 0, 0, 0.65)',
    colorTextTertiary: 'rgba(0, 0, 0, 0.45)',
    colorTextQuaternary: 'rgba(0, 0, 0, 0.25)',
    borderRadius: 8, // More rounded corners for modern look
    borderRadiusLG: 12,
    borderRadiusSM: 6,
    fontSize: 14,
    fontSizeLG: 16,
    fontSizeSM: 12,
    fontFamily:
        'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif', // Added Inter
    marginXS: 8,
    marginSM: 12,
    margin: 16,
    marginMD: 20,
    marginLG: 24,
    marginXL: 32,
    boxShadow:
        '0 2px 8px rgba(0, 0, 0, 0.08)', // Softer shadow
    boxShadowSecondary:
        '0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05)',
    motionDurationFast: '0.1s',
    motionDurationMid: '0.2s',
    motionDurationSlow: '0.3s',
    controlHeight: 36, // Slightly taller controls for better touch/click targets
    controlHeightLG: 44,
    controlHeightSM: 28,
} satisfies ThemeConfig['token']

const componentTokens = {
    Button: {
        colorPrimary: '#1890ff',
        algorithm: true,
    },
    Input: {
        colorPrimary: '#1890ff',
        algorithm: true,
    },
    Select: {
        colorPrimary: '#1890ff',
        algorithm: true,
    },
    Table: {
        headerBg: '#fafafa',
        headerColor: 'rgba(0, 0, 0, 0.88)',
        headerSortActiveBg: '#f0f0f0',
        bodySortBg: '#fafafa',
    },
    Layout: {
        bodyBg: '#f0f2f5',
        headerBg: '#ffffff',
        headerHeight: 64,
        headerPadding: '0 24px',
        headerColor: 'rgba(0, 0, 0, 0.88)',
        siderBg: '#ffffff',
        triggerBg: '#002140',
        triggerColor: '#ffffff',
    },
    Menu: {
        itemBg: 'transparent',
        itemSelectedBg: 'rgba(24, 144, 255, 0.1)',
        itemSelectedColor: '#1890ff',
        itemHoverBg: 'rgba(24, 144, 255, 0.05)',
        itemHoverColor: '#1890ff',
        itemActiveBg: 'rgba(24, 144, 255, 0.15)',
    },
    Card: {
        headerBg: '#ffffff',
        headerFontSize: 16,
        headerHeight: 48,
        actionsLiMargin: '12px 0',
        tabsMarginBottom: -17,
        extraColor: 'rgba(0, 0, 0, 0.88)',
    },
    Tabs: {
        inkBarColor: '#1890ff',
        itemSelectedColor: '#1890ff',
        itemHoverColor: '#40a9ff',
        itemActiveColor: '#096dd9',
        cardBg: '#f5f5f5',
    },
    Tag: {
        defaultBg: '#fafafa',
        defaultColor: 'rgba(0, 0, 0, 0.88)',
    },
    Modal: {
        headerBg: '#ffffff',
        titleFontSize: 16,
        titleLineHeight: 1.5,
    },
    Form: {
        labelColor: 'rgba(0, 0, 0, 0.88)',
        labelFontSize: 14,
        labelHeight: 32,
        labelColonMarginInlineStart: 2,
        labelColonMarginInlineEnd: 8,
        itemMarginBottom: 24,
    },
    DatePicker: {
        cellHoverBg: '#f5f5f5',
        cellActiveWithRangeBg: '#e6f4ff',
        cellHoverWithRangeBg: '#cfe8fc',
        cellRangeBorderColor: 'transparent',
        cellBgDisabled: 'rgba(0, 0, 0, 0.04)',
        cellWidth: 36,
        cellHeight: 24,
    },
    Drawer: {
        footerPaddingBlock: 8,
        footerPaddingInline: 16,
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
