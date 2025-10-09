// DeepSearch Design Tokens v2.0
// Unified design system for React components
// Based on first principles and user research

// Color System
export const colors = {
  // Brand Colors
  brand: {
    primary: '#4A69FF',        // Trust, Professional
    primaryLight: '#7089FF',   
    primaryDark: '#2449DF',    
    secondary: '#00D4AA',      // Growth, Positive
    secondaryLight: '#33DDBB',
    secondaryDark: '#00A583',
    accent: '#FF6B6B',         // Emphasis, Warning
    accentLight: '#FF8787',
    accentDark: '#E55555',
  },

  // Financial Market Colors (Chinese Convention)
  market: {
    bullish: '#F5222D',        // 上涨 - Red
    bearish: '#52C41A',        // 下跌 - Green
    flat: '#8C8C8C',           // 平盘 - Gray
  },

  // Semantic Colors
  semantic: {
    success: '#52C41A',
    warning: '#FAAD14',
    error: '#F5222D',
    info: '#1890FF',
  },

  // Neutral Colors (11-level grayscale)
  neutral: {
    0: '#FFFFFF',
    50: '#FAFBFC',
    100: '#F4F6F8',
    200: '#E9ECEF',
    300: '#DEE2E6',
    400: '#CED4DA',
    500: '#ADB5BD',
    600: '#6C757D',
    700: '#495057',
    800: '#343A40',
    900: '#212529',
    1000: '#000000',
  },
}

// Typography System
export const typography = {
  fontFamily: {
    base: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif',
    mono: '"SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace',
  },
  
  fontSize: {
    xs: '12px',    // Auxiliary info
    sm: '14px',    // Secondary content
    base: '16px',  // Body text
    lg: '18px',    // Emphasis content
    xl: '22px',    // Secondary heading
    '2xl': '28px', // Primary heading
    '3xl': '36px', // Page title
    '4xl': '46px', // Display title
  },
  
  fontWeight: {
    light: 300,
    regular: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
  
  lineHeight: {
    tight: 1.25,    // Headings
    base: 1.5,      // Body text
    relaxed: 1.75,  // Long text
  },
}

// Spacing System (8px grid)
export const spacing = {
  0: '0',
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  5: '24px',
  6: '32px',
  7: '40px',
  8: '48px',
  9: '64px',
  10: '80px',
}

// Border Radius
export const radius = {
  none: '0',
  sm: '2px',     // Small components
  base: '4px',   // Buttons, inputs
  md: '6px',     // Cards
  lg: '8px',     // Modals
  xl: '12px',    // Large cards
  '2xl': '16px', // Extra large cards
  full: '9999px', // Circular
}

// Shadows
export const shadows = {
  none: 'none',
  xs: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  sm: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
  base: '0 2px 8px 0 rgba(0, 0, 0, 0.1)',
  md: '0 4px 12px 0 rgba(0, 0, 0, 0.1)',
  lg: '0 8px 24px 0 rgba(0, 0, 0, 0.1)',
  xl: '0 12px 48px 0 rgba(0, 0, 0, 0.12)',
  inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
  innerLg: 'inset 0 4px 8px 0 rgba(0, 0, 0, 0.12)',
}

// Animation
export const animation = {
  duration: {
    instant: '100ms',  // Instant feedback
    fast: '200ms',     // Fast transition
    base: '300ms',     // Standard animation
    slow: '500ms',     // Complex animation
    slower: '700ms',   // Page transition
  },
  
  easing: {
    linear: 'linear',
    in: 'cubic-bezier(0.4, 0, 1, 1)',
    out: 'cubic-bezier(0, 0, 0.2, 1)',
    inOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
    spring: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
  },
}

// Borders
export const borders = {
  width: {
    base: '1px',
    thick: '2px',
    heavy: '4px',
  },
  
  color: {
    base: colors.neutral[300],
    light: colors.neutral[200],
    dark: colors.neutral[400],
  },
}

// Z-index layers
export const zIndex = {
  base: 0,
  dropdown: 1000,
  sticky: 1020,
  fixed: 1030,
  modalBackdrop: 1040,
  modal: 1050,
  popover: 1060,
  tooltip: 1070,
  notification: 1080,
}

// Breakpoints (responsive design)
export const breakpoints = {
  xs: '0px',       // Mobile portrait
  sm: '576px',     // Mobile landscape
  md: '768px',     // Tablet portrait
  lg: '992px',     // Tablet landscape
  xl: '1200px',    // Laptop
  '2xl': '1400px', // Desktop
}

// Grid System
export const grid = {
  columns: 12,
  gutter: '24px',
  margin: '24px',
}

// Component-specific tokens
export const components = {
  button: {
    height: {
      sm: '24px',
      base: '32px',
      lg: '40px',
    },
    padding: {
      sm: '0 8px',
      base: '0 16px',
      lg: '0 24px',
    },
  },
  
  input: {
    height: {
      sm: '24px',
      base: '32px',
      lg: '40px',
    },
    padding: '0 12px',
  },
  
  card: {
    padding: {
      sm: '12px',
      base: '16px',
      lg: '24px',
    },
  },
  
  modal: {
    width: {
      sm: '360px',
      base: '520px',
      lg: '720px',
      xl: '960px',
    },
  },
}

// Theme configurations
export const themes = {
  light: {
    background: {
      primary: colors.neutral[0],
      secondary: colors.neutral[50],
      tertiary: colors.neutral[100],
    },
    text: {
      primary: colors.neutral[900],
      secondary: colors.neutral[600],
      placeholder: colors.neutral[500],
      disabled: colors.neutral[400],
    },
    border: {
      color: colors.neutral[300],
      light: colors.neutral[200],
      dark: colors.neutral[400],
    },
  },
  
  dark: {
    background: {
      primary: colors.neutral[900],
      secondary: colors.neutral[800],
      tertiary: colors.neutral[700],
    },
    text: {
      primary: colors.neutral[100],
      secondary: colors.neutral[400],
      placeholder: colors.neutral[500],
      disabled: colors.neutral[600],
    },
    border: {
      color: colors.neutral[700],
      light: colors.neutral[600],
      dark: colors.neutral[800],
    },
  },
}

// Export all tokens as a single object for convenience
const tokens = {
  colors,
  typography,
  spacing,
  radius,
  shadows,
  animation,
  borders,
  zIndex,
  breakpoints,
  grid,
  components,
  themes,
}

export default tokens