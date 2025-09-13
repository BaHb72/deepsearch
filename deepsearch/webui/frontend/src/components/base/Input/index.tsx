import React, { forwardRef, memo, useState, useCallback } from 'react'
import PropTypes from 'prop-types'
import classNames from 'classnames'
import './index.scss'

/**
 * Unified Input Component
 * A comprehensive input component with multiple types and features
 */
const Input = forwardRef(({
  // Type and variant
  type = 'text',
  variant = 'default',
  size = 'medium',
  
  // State
  value,
  defaultValue,
  disabled = false,
  readOnly = false,
  loading = false,
  error = false,
  success = false,
  
  // Appearance
  placeholder,
  prefix,
  suffix,
  allowClear = false,
  showCount = false,
  maxLength,
  
  // Behavior
  autoFocus = false,
  autoComplete = 'off',
  spellCheck = false,
  
  // Events
  onChange,
  onFocus,
  onBlur,
  onKeyDown,
  onKeyUp,
  onKeyPress,
  onPressEnter,
  onClear,
  onSearch,
  
  // Textarea specific
  rows = 3,
  autoSize = false,
  resize = 'vertical',
  
  // Number specific
  min,
  max,
  step,
  precision,
  
  // Password specific
  visibilityToggle = true,
  
  // Search specific
  enterButton = false,
  onSearchClick,
  
  // Other
  className,
  style,
  inputClassName,
  inputStyle,
  label,
  helper,
  required = false,
  id,
  name,
  ...restProps
}, ref) => {
  // State
  const [focused, setFocused] = useState(false)
  const [internalValue, setInternalValue] = useState(defaultValue || '')
  const [passwordVisible, setPasswordVisible] = useState(false)
  
  // Determine if controlled or uncontrolled
  const isControlled = value !== undefined
  const inputValue = isControlled ? value : internalValue
  
  // Build class names
  const wrapperClasses = classNames(
    'ds-input-wrapper',
    `ds-input-wrapper--${size}`,
    {
      'ds-input-wrapper--focused': focused,
      'ds-input-wrapper--disabled': disabled,
      'ds-input-wrapper--readonly': readOnly,
      'ds-input-wrapper--error': error,
      'ds-input-wrapper--success': success,
      'ds-input-wrapper--loading': loading,
      'ds-input-wrapper--with-prefix': prefix,
      'ds-input-wrapper--with-suffix': suffix || allowClear || showCount || visibilityToggle,
      'ds-input-wrapper--clearable': allowClear && inputValue,
      'ds-input-wrapper--textarea': type === 'textarea',
      'ds-input-wrapper--search': type === 'search',
    },
    className
  )
  
  const inputClasses = classNames(
    'ds-input',
    `ds-input--${variant}`,
    inputClassName
  )
  
  // Handlers
  const handleChange = useCallback((e) => {
    const newValue = e.target.value
    
    // Handle maxLength for non-textarea inputs
    if (maxLength && type !== 'textarea' && newValue.length > maxLength) {
      return
    }
    
    // Update internal state if uncontrolled
    if (!isControlled) {
      setInternalValue(newValue)
    }
    
    onChange?.(e)
  }, [isControlled, onChange, maxLength, type])
  
  const handleFocus = useCallback((e) => {
    setFocused(true)
    onFocus?.(e)
  }, [onFocus])
  
  const handleBlur = useCallback((e) => {
    setFocused(false)
    onBlur?.(e)
  }, [onBlur])
  
  const handleClear = useCallback(() => {
    const fakeEvent = {
      target: { value: '' },
      currentTarget: { value: '' },
    }
    
    if (!isControlled) {
      setInternalValue('')
    }
    
    onChange?.(fakeEvent)
    onClear?.()
  }, [isControlled, onChange, onClear])
  
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      onPressEnter?.(e)
      
      if (type === 'search') {
        onSearch?.(inputValue, e)
      }
    }
    
    onKeyDown?.(e)
  }, [onKeyDown, onPressEnter, onSearch, inputValue, type])
  
  const handleSearchClick = useCallback(() => {
    onSearchClick?.(inputValue)
    onSearch?.(inputValue)
  }, [onSearchClick, onSearch, inputValue])
  
  const togglePasswordVisibility = useCallback(() => {
    setPasswordVisible(prev => !prev)
  }, [])
  
  // Determine input type
  const getInputType = () => {
    if (type === 'password' && passwordVisible) {
      return 'text'
    }
    if (type === 'search' || type === 'textarea') {
      return 'text'
    }
    return type
  }
  
  // Render prefix
  const renderPrefix = () => {
    if (!prefix) return null
    
    return (
      <span className="ds-input-wrapper__prefix">
        {prefix}
      </span>
    )
  }
  
  // Render suffix elements
  const renderSuffix = () => {
    const elements = []
    
    // Clear button
    if (allowClear && inputValue && !disabled && !readOnly) {
      elements.push(
        <button
          key="clear"
          type="button"
          className="ds-input-wrapper__clear"
          onClick={handleClear}
          tabIndex={-1}
        >
          <svg viewBox="0 0 24 24" width="16" height="16">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
          </svg>
        </button>
      )
    }
    
    // Password visibility toggle
    if (type === 'password' && visibilityToggle && !disabled) {
      elements.push(
        <button
          key="visibility"
          type="button"
          className="ds-input-wrapper__visibility"
          onClick={togglePasswordVisibility}
          tabIndex={-1}
        >
          {passwordVisible ? (
            <svg viewBox="0 0 24 24" width="16" height="16">
              <path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" width="16" height="16">
              <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z" />
            </svg>
          )}
        </button>
      )
    }
    
    // Character count
    if (showCount && maxLength) {
      elements.push(
        <span key="count" className="ds-input-wrapper__count">
          {inputValue.length}/{maxLength}
        </span>
      )
    }
    
    // Custom suffix
    if (suffix) {
      elements.push(
        <span key="suffix" className="ds-input-wrapper__suffix">
          {suffix}
        </span>
      )
    }
    
    // Loading spinner
    if (loading) {
      elements.push(
        <span key="loading" className="ds-input-wrapper__loading">
          <svg className="ds-input-wrapper__spinner" viewBox="0 0 24 24" width="16" height="16">
            <circle 
              cx="12" 
              cy="12" 
              r="10" 
              strokeWidth="3"
              strokeLinecap="round"
              fill="none"
              stroke="currentColor"
            />
          </svg>
        </span>
      )
    }
    
    return elements.length > 0 ? (
      <span className="ds-input-wrapper__suffix-container">
        {elements}
      </span>
    ) : null
  }
  
  // Render search button
  const renderSearchButton = () => {
    if (type !== 'search' || !enterButton) return null
    
    const buttonContent = typeof enterButton === 'boolean' ? (
      <svg viewBox="0 0 24 24" width="16" height="16">
        <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
      </svg>
    ) : enterButton
    
    return (
      <button
        type="button"
        className="ds-input-wrapper__search-button"
        onClick={handleSearchClick}
        disabled={disabled || loading}
      >
        {buttonContent}
      </button>
    )
  }
  
  // Common input props
  const inputProps = {
    ref,
    id,
    name,
    className: inputClasses,
    style: inputStyle,
    value: inputValue,
    disabled,
    readOnly,
    placeholder,
    autoFocus,
    autoComplete,
    spellCheck,
    required,
    onChange: handleChange,
    onFocus: handleFocus,
    onBlur: handleBlur,
    onKeyDown: handleKeyDown,
    onKeyUp,
    onKeyPress,
    ...restProps,
  }
  
  // Render input element
  const renderInput = () => {
    if (type === 'textarea') {
      return (
        <textarea
          {...inputProps}
          rows={rows}
          maxLength={maxLength}
          style={{
            ...inputStyle,
            resize: autoSize ? 'none' : resize,
          }}
        />
      )
    }
    
    return (
      <input
        {...inputProps}
        type={getInputType()}
        min={min}
        max={max}
        step={step}
        maxLength={maxLength}
      />
    )
  }
  
  return (
    <div className="ds-input-container">
      {label && (
        <label className="ds-input-label" htmlFor={id}>
          {label}
          {required && <span className="ds-input-label__required">*</span>}
        </label>
      )}
      
      <div className={wrapperClasses} style={style}>
        {renderPrefix()}
        {renderInput()}
        {renderSuffix()}
        {renderSearchButton()}
      </div>
      
      {helper && (
        <div className={classNames('ds-input-helper', {
          'ds-input-helper--error': error,
          'ds-input-helper--success': success,
        })}>
          {helper}
        </div>
      )}
    </div>
  )
})

Input.displayName = 'Input'

Input.propTypes = {
  // Type and variant
  type: PropTypes.oneOf(['text', 'password', 'number', 'email', 'tel', 'url', 'search', 'textarea']),
  variant: PropTypes.oneOf(['default', 'filled', 'borderless']),
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  
  // State
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  defaultValue: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  disabled: PropTypes.bool,
  readOnly: PropTypes.bool,
  loading: PropTypes.bool,
  error: PropTypes.bool,
  success: PropTypes.bool,
  
  // Appearance
  placeholder: PropTypes.string,
  prefix: PropTypes.node,
  suffix: PropTypes.node,
  allowClear: PropTypes.bool,
  showCount: PropTypes.bool,
  maxLength: PropTypes.number,
  
  // Behavior
  autoFocus: PropTypes.bool,
  autoComplete: PropTypes.string,
  spellCheck: PropTypes.bool,
  
  // Events
  onChange: PropTypes.func,
  onFocus: PropTypes.func,
  onBlur: PropTypes.func,
  onKeyDown: PropTypes.func,
  onKeyUp: PropTypes.func,
  onKeyPress: PropTypes.func,
  onPressEnter: PropTypes.func,
  onClear: PropTypes.func,
  onSearch: PropTypes.func,
  
  // Textarea specific
  rows: PropTypes.number,
  autoSize: PropTypes.oneOfType([PropTypes.bool, PropTypes.object]),
  resize: PropTypes.oneOf(['none', 'both', 'horizontal', 'vertical']),
  
  // Number specific
  min: PropTypes.number,
  max: PropTypes.number,
  step: PropTypes.number,
  precision: PropTypes.number,
  
  // Password specific
  visibilityToggle: PropTypes.bool,
  
  // Search specific
  enterButton: PropTypes.oneOfType([PropTypes.bool, PropTypes.node]),
  onSearchClick: PropTypes.func,
  
  // Other
  className: PropTypes.string,
  style: PropTypes.object,
  inputClassName: PropTypes.string,
  inputStyle: PropTypes.object,
  label: PropTypes.node,
  helper: PropTypes.node,
  required: PropTypes.bool,
  id: PropTypes.string,
  name: PropTypes.string,
}

export default memo(Input)