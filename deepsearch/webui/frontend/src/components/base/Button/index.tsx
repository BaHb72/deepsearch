import type {AnchorHTMLAttributes, ButtonHTMLAttributes, MouseEvent, ReactNode,} from 'react'
import {forwardRef, memo} from 'react'
import classNames from 'classnames'

import './index.scss'

type ButtonVariant =
    | 'primary'
    | 'secondary'
    | 'success'
    | 'warning'
    | 'danger'
    | 'info'
    | 'ghost'
    | 'link'
    | 'text'

type ButtonSize = 'small' | 'medium' | 'large'
type IconPosition = 'left' | 'right'

export interface ButtonProps
    extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'type' | 'onClick'> {
    variant?: ButtonVariant
    size?: ButtonSize
    block?: boolean
    round?: boolean
    circle?: boolean
    ghost?: boolean
    active?: boolean
    loading?: boolean
    icon?: ReactNode
    iconPosition?: IconPosition
    href?: string
    target?: AnchorHTMLAttributes<HTMLAnchorElement>['target']
    type?: ButtonHTMLAttributes<HTMLButtonElement>['type']
    onClick?: (event: MouseEvent<HTMLButtonElement | HTMLAnchorElement>) => void
}

const Button = memo(
    forwardRef<HTMLButtonElement | HTMLAnchorElement, ButtonProps>(
        (
            {
                variant = 'primary',
                size = 'medium',
                block = false,
                round = false,
                circle = false,
                ghost = false,
                active = false,
                loading = false,
                disabled = false,
                icon,
                iconPosition = 'left',
                children,
                className,
                style,
                href,
                target,
                type = 'button',
                onClick,
                onMouseEnter,
                onMouseLeave,
                onFocus,
                onBlur,
                ...restProps
            }: ButtonProps,
            ref
        ) => {
            const isLink = typeof href === 'string' && href.length > 0
            const isInteractive = !(disabled || loading)

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
                    'ds-button--disabled': !isInteractive,
                    'ds-button--icon-only': icon && !children,
                    'ds-button--with-icon': icon && children,
                    [`ds-button--icon-${iconPosition}`]: icon && children,
                },
                className
            )

            const handleClick = (
                event: MouseEvent<HTMLButtonElement | HTMLAnchorElement>
            ) => {
                if (!isInteractive) {
                    event.preventDefault()
                    return
                }
                onClick?.(event)
            }

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

            const renderIcon = () => {
                if (loading && iconPosition === 'left') {
                    return renderLoadingIcon()
                }

                if (icon) {
                    return <span className="ds-button__icon">{icon}</span>
                }

                return null
            }

            const renderContent = () => (
                <>
                    {iconPosition === 'left' && renderIcon()}
                    {children && <span className="ds-button__content">{children}</span>}
                    {iconPosition === 'right' && renderIcon()}
                    {loading && iconPosition === 'right' && renderLoadingIcon()}
                </>
            )

            const commonProps = {
                ref,
                className: classes,
                style,
                onMouseEnter,
                onMouseLeave,
                onFocus,
                onBlur,
                ...restProps,
            }

            if (isLink) {
                const anchorSpecific: AnchorHTMLAttributes<HTMLAnchorElement> = {
                    ...commonProps,
                    href: isInteractive ? href : undefined,
                    target,
                    onClick: handleClick as (event: MouseEvent<HTMLAnchorElement>) => void,
                    role: 'button',
                    tabIndex: isInteractive ? 0 : -1,
                    'aria-disabled': !isInteractive,
                }

                return <a {...anchorSpecific}>{renderContent()}</a>
            }

            const buttonSpecific: ButtonHTMLAttributes<HTMLButtonElement> = {
                ...commonProps,
                type,
                disabled: !isInteractive,
                onClick: handleClick as (event: MouseEvent<HTMLButtonElement>) => void,
                'aria-busy': loading,
                'aria-disabled': !isInteractive,
            }

            return <button {...buttonSpecific}>{renderContent()}</button>
        }
  )
)

Button.displayName = 'Button'

export default Button
