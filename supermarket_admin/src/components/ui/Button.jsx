import styles from './Button.module.css'

const VARIANTS = {
  primary: 'primary',
  secondary: 'secondary',
  ghost: 'ghost',
  danger: 'danger',
}

export default function Button({
  variant = 'primary',
  type = 'button',
  className = '',
  children,
  ...props
}) {
  return (
    <button
      type={type}
      className={`${styles.button} ${styles[VARIANTS[variant]]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
