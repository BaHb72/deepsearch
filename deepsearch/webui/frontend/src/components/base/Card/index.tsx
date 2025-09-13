import React, { forwardRef, memo } from 'react'
import PropTypes from 'prop-types'
import classNames from 'classnames'
import './index.scss'

/**
 * Unified Card Component
 * A versatile container component for grouping related content
 */
const Card = forwardRef(({
  // Content
  children,
  title,
  subtitle,
  header,
  footer,
  cover,
  extra,
  
  // Appearance
  variant = 'default',
  size = 'medium',
  bordered = true,
  shadow = 'base',
  hoverable = false,
  selected = false,
  
  // State
  loading = false,
  disabled = false,
  
  // Layout
  padding = true,
  bodyStyle,
  headerStyle,
  footerStyle,
  
  // Actions
  actions,
  onClick,
  onMouseEnter,
  onMouseLeave,
  
  // Other
  className,
  style,
  ...restProps
}, ref) => {
  // Build class names
  const cardClasses = classNames(
    'ds-card',
    `ds-card--${variant}`,
    `ds-card--${size}`,
    `ds-card--shadow-${shadow}`,
    {
      'ds-card--bordered': bordered,
      'ds-card--borderless': !bordered,
      'ds-card--hoverable': hoverable,
      'ds-card--selected': selected,
      'ds-card--loading': loading,
      'ds-card--disabled': disabled,
      'ds-card--clickable': onClick,
      'ds-card--no-padding': !padding,
    },
    className
  )
  
  // Handle click
  const handleClick = (e) => {
    if (disabled || loading) {
      e.preventDefault()
      return
    }
    onClick?.(e)
  }
  
  // Render loading overlay
  const renderLoading = () => {
    if (!loading) return null
    
    return (
      <div className="ds-card__loading">
        <div className="ds-card__loading-spinner">
          <svg viewBox="0 0 50 50">
            <circle
              cx="25"
              cy="25"
              r="20"
              fill="none"
              strokeWidth="4"
            />
          </svg>
        </div>
      </div>
    )
  }
  
  // Render cover image
  const renderCover = () => {
    if (!cover) return null
    
    return (
      <div className="ds-card__cover">
        {typeof cover === 'string' ? (
          <img src={cover} alt="Card cover" />
        ) : (
          cover
        )}
      </div>
    )
  }
  
  // Render header
  const renderHeader = () => {
    if (!header && !title && !subtitle && !extra) return null
    
    if (header) {
      return (
        <div className="ds-card__header" style={headerStyle}>
          {header}
        </div>
      )
    }
    
    return (
      <div className="ds-card__header" style={headerStyle}>
        <div className="ds-card__header-content">
          {title && (
            <div className="ds-card__title">{title}</div>
          )}
          {subtitle && (
            <div className="ds-card__subtitle">{subtitle}</div>
          )}
        </div>
        {extra && (
          <div className="ds-card__extra">{extra}</div>
        )}
      </div>
    )
  }
  
  // Render body
  const renderBody = () => {
    if (!children) return null
    
    return (
      <div className="ds-card__body" style={bodyStyle}>
        {children}
      </div>
    )
  }
  
  // Render actions
  const renderActions = () => {
    if (!actions || actions.length === 0) return null
    
    return (
      <div className="ds-card__actions">
        {actions.map((action, index) => (
          <div key={index} className="ds-card__action">
            {action}
          </div>
        ))}
      </div>
    )
  }
  
  // Render footer
  const renderFooter = () => {
    if (!footer && (!actions || actions.length === 0)) return null
    
    if (footer) {
      return (
        <div className="ds-card__footer" style={footerStyle}>
          {footer}
        </div>
      )
    }
    
    return renderActions()
  }
  
  return (
    <div
      ref={ref}
      className={cardClasses}
      style={style}
      onClick={handleClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick && !disabled ? 0 : undefined}
      {...restProps}
    >
      {renderLoading()}
      {renderCover()}
      {renderHeader()}
      {renderBody()}
      {renderFooter()}
    </div>
  )
})

Card.displayName = 'Card'

Card.propTypes = {
  // Content
  children: PropTypes.node,
  title: PropTypes.node,
  subtitle: PropTypes.node,
  header: PropTypes.node,
  footer: PropTypes.node,
  cover: PropTypes.oneOfType([PropTypes.string, PropTypes.node]),
  extra: PropTypes.node,
  
  // Appearance
  variant: PropTypes.oneOf(['default', 'outlined', 'elevated', 'filled']),
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  bordered: PropTypes.bool,
  shadow: PropTypes.oneOf(['none', 'xs', 'sm', 'base', 'md', 'lg', 'xl']),
  hoverable: PropTypes.bool,
  selected: PropTypes.bool,
  
  // State
  loading: PropTypes.bool,
  disabled: PropTypes.bool,
  
  // Layout
  padding: PropTypes.bool,
  bodyStyle: PropTypes.object,
  headerStyle: PropTypes.object,
  footerStyle: PropTypes.object,
  
  // Actions
  actions: PropTypes.arrayOf(PropTypes.node),
  onClick: PropTypes.func,
  onMouseEnter: PropTypes.func,
  onMouseLeave: PropTypes.func,
  
  // Other
  className: PropTypes.string,
  style: PropTypes.object,
}

// Grid component for card layouts
export const CardGrid = memo(({ children, className, cols = 3, gap = 'medium', ...props }) => {
  const gridClasses = classNames(
    'ds-card-grid',
    `ds-card-grid--cols-${cols}`,
    `ds-card-grid--gap-${gap}`,
    className
  )
  
  return (
    <div className={gridClasses} {...props}>
      {children}
    </div>
  )
})

CardGrid.displayName = 'CardGrid'

CardGrid.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  cols: PropTypes.oneOf([1, 2, 3, 4, 5, 6]),
  gap: PropTypes.oneOf(['small', 'medium', 'large']),
}

// Meta component for card metadata
export const CardMeta = memo(({ avatar, title, description, className, ...props }) => {
  const metaClasses = classNames('ds-card-meta', className)
  
  return (
    <div className={metaClasses} {...props}>
      {avatar && (
        <div className="ds-card-meta__avatar">
          {avatar}
        </div>
      )}
      <div className="ds-card-meta__content">
        {title && (
          <div className="ds-card-meta__title">{title}</div>
        )}
        {description && (
          <div className="ds-card-meta__description">{description}</div>
        )}
      </div>
    </div>
  )
})

CardMeta.displayName = 'CardMeta'

CardMeta.propTypes = {
  avatar: PropTypes.node,
  title: PropTypes.node,
  description: PropTypes.node,
  className: PropTypes.string,
}

export default memo(Card)