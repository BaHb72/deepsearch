# DeepSearch React Component Library

## Overview

This is the unified React component library for the DeepSearch quantitative trading platform. It provides a consistent, professional, and reusable UI system.

## Component Structure

```
/components
├── /base              # Fundamental UI components
│   ├── Button        # Button with multiple variants
│   ├── Input         # Input with various types
│   └── Card          # Container component
├── /business         # Domain-specific components
├── /layout           # Layout components
└── README.md         # This file
```

## Design System

### Design Tokens
- **Location**: `/styles/tokens.js`
- **CSS Variables**: `/styles/variables.css`
- **Purpose**: Single source of truth for design values

### Color System
- **Brand Colors**: Primary (#4A69FF), Secondary (#00D4AA), Accent (#FF6B6B)
- **Market Colors**: Bullish (Red #F5222D), Bearish (Green #52C41A) - Chinese convention
- **Semantic Colors**: Success, Warning, Error, Info

### Typography
- **Font Family**: System fonts with Chinese support
- **Size Scale**: 12px to 46px (8 levels)
- **Weight Scale**: 300 to 700

## Usage Examples

### Button Component

```jsx
import Button from '@/components/base/Button'

// Basic usage
<Button variant="primary">Click Me</Button>

// With icon
<Button icon={<SearchOutlined />}>Search</Button>

// Loading state
<Button loading>Processing...</Button>

// Different sizes
<Button size="small">Small</Button>
<Button size="large">Large</Button>
```

### Input Component

```jsx
import Input from '@/components/base/Input'

// Basic text input
<Input 
  placeholder="Enter text..."
  value={value}
  onChange={(e) => setValue(e.target.value)}
/>

// Password with visibility toggle
<Input 
  type="password"
  visibilityToggle
  label="Password"
/>

// Search input
<Input 
  type="search"
  enterButton="Search"
  onSearch={(value) => handleSearch(value)}
/>

// Textarea with character count
<Input 
  type="textarea"
  showCount
  maxLength={200}
  rows={4}
/>
```

### Card Component

```jsx
import Card, { CardGrid, CardMeta } from '@/components/base/Card'

// Basic card
<Card title="Card Title">
  <p>Card content</p>
</Card>

// Card with actions
<Card 
  title="Interactive Card"
  actions={[
    <Button variant="text">Action 1</Button>,
    <Button variant="text">Action 2</Button>
  ]}
>
  Content
</Card>

// Card grid layout
<CardGrid cols={3} gap="medium">
  <Card>Card 1</Card>
  <Card>Card 2</Card>
  <Card>Card 3</Card>
</CardGrid>

// Card with metadata
<Card>
  <CardMeta
    avatar={<Avatar />}
    title="Title"
    description="Description"
  />
</Card>
```

## Theme Support

The component library supports light and dark themes:

```jsx
// Toggle theme
document.documentElement.setAttribute('data-theme', 'dark')

// Or use with ThemeContext
import { useTheme } from '@/contexts/ThemeContext'

const { toggleDark } = useTheme()
```

## Component Showcase

To view all components and their variants, navigate to:
```
/showcase
```

Or import the showcase page:
```jsx
import ComponentShowcase from '@/pages/ComponentShowcase'
```

## Best Practices

1. **Always use design tokens** instead of hardcoded values
2. **Prefer composition** over complex props
3. **Use semantic variants** (primary, success, danger) appropriately
4. **Implement proper loading states** for async operations
5. **Include accessibility attributes** (ARIA labels, roles)
6. **Test across themes** (light/dark) and screen sizes

## Performance Optimization

All components are:
- Wrapped with `React.memo()` for render optimization
- Use `forwardRef` for ref forwarding
- Implement proper event handler memoization
- Support lazy loading where appropriate

## Contributing

When creating new components:

1. Follow the established structure
2. Use the design token system
3. Include PropTypes validation
4. Write comprehensive documentation
5. Add to the component showcase
6. Test in both light and dark themes

## Financial UI Components (Coming Soon)

- **StockTicker**: Real-time price display
- **OrderBook**: Depth visualization
- **KLineChart**: Candlestick charts with indicators
- **PortfolioCard**: Position summary
- **TradePanel**: Buy/sell interface

## Integration with Ant Design

These components can work alongside Ant Design components. For consistency, use the custom theme configuration in `ThemeContext.jsx`.

## Support

For questions or issues, please refer to the main project documentation or contact the development team.