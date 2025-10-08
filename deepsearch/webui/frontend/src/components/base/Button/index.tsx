import React, { forwardRef, memo } from 'react'
import PropTypes from 'prop-types'
import classNames from 'classnames'
import './index.scss'

/**
 * Unified Button Component
 * A comprehensive button component with multiple variants and states
 */
const Button = forwardRef(({
  // Appearance
  variant = 'primary',
  size = 'medium',
  block = false,
  round = false,
  circle = false,
  ghost = false,
  
  // State
  active = false,
  loading = false,
  disabled = false,
  
  // Content
  children,
  icon,
  iconPosition = 'left',
  
  // Behavior
  type = 'button',
  href,
  target,
  onClick,
  onMouseEnter,
  onMouseLeave,
  onFocus,
  onBlur,
  
  // Other
  className,
  style,
  ...restProps
}, ref) => {
  // Determine the component type
  const Component = href ? 'a' : 'button'
  
  // Build class names
  const classes = classNames(
    'ds-button',
    `ds-button--${variant}`,
    `ds-button--${size}`,
    {
      'ds-button--block': block,
      'ds-button--round': round,
      'ds-button--circle': circle,
      'ds-button--ghost': ghost,
      'ds-button--active': active,
      'ds-button--loading': loading,
      'ds-button--disabled': disabled || loading,
      'ds-button--icon-only': icon && !children,
      'ds-button--with-icon': icon && children,
      [`ds-button--icon-${iconPosition}`]: icon && children,
    },
    className
  )
  
  // Handle click events
  const handleClick = (e) => {
    if (disabled || loading) {
      e.preventDefault()
      return
    }
    onClick?.(e)
  }
  
  // Render loading spinner
  const renderLoadingIcon = () => (
    <span className="ds-button__loading">
      <svg className="ds-button__spinner" viewBox="0 0 24 24">
        <circle 
          className="ds-button__spinner-circle"
          cx="12" 
          cy="12" 
          r="10" 
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
    </span>
  )
  
  // Render icon
  const renderIcon = () => {
    if (loading && iconPosition === 'left') {
      return renderLoadingIcon()
    }
    
    if (icon) {
      return <span className="ds-button__icon">{icon}</span>
    }
    
    return null
  }
  
  // Render content
  const renderContent = () => (
    <>
      {iconPosition === 'left' && renderIcon()}
      {children && <span className="ds-button__content">{children}</span>}
      {iconPosition === 'right' && renderIcon()}
      {loading && iconPosition === 'right' && renderLoadingIcon()}
    </>
  )
  
  // Common props
  const commonProps = {
    ref,
    className: classes,
    style,
    disabled: disabled || loading,
    onMouseEnter,
    onMouseLeave,
    onFocus,
    onBlur,
    ...restProps,
  }
  
  // Render as link
  if (Component === 'a') {
    return (
      <a
        {...commonProps}
        href={disabled || loading ? undefined : href}
        target={target}
        onClick={handleClick}
        role="button"
        tabIndex={disabled || loading ? -1 : 0}
      >
        {renderContent()}
      </a>
    )
  }
  
  // Render as button
  return (
    <button
      {...commonProps}
      type={type}
      onClick={handleClick}
      aria-busy={loading}
      aria-disabled={disabled || loading}
    >
      {renderContent()}
    </button>
  )
})

Button.displayName = 'Button'

Button.propTypes = {
  // Appearance
  variant: PropTypes.oneOf([
    'primary',
    'secondary',
    'success',
    'warning',
    'danger',
    'info',
    'ghost',
    'link',
    'text',
  ]),
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  block: PropTypes.bool,
  round: PropTypes.bool,
  circle: PropTypes.bool,
  ghost: PropTypes.bool,
  
  // State
  active: PropTypes.bool,
  loading: PropTypes.bool,
  disabled: PropTypes.bool,
  
  // Content
  children: PropTypes.node,
  icon: PropTypes.node,
  iconPosition: PropTypes.oneOf(['left', 'right']),
  
  // Behavior
  type: PropTypes.oneOf(['button', 'submit', 'reset']),
  href: PropTypes.string,
  target: PropTypes.string,
  onClick: PropTypes.func,
  onMouseEnter: PropTypes.func,
  onMouseLeave: PropTypes.func,
  onFocus: PropTypes.func,
  onBlur: PropTypes.func,
  
  // Other
  className: PropTypes.string,
  style: PropTypes.object,
}

// Export memoized component for performance
export default memo(Button)