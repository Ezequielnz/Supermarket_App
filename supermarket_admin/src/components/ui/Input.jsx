import styles from './Input.module.css'

export default function Input({ invalid = false, className = '', ...props }) {
  return (
    <input
      className={`${styles.input} ${invalid ? styles.invalid : ''} ${className}`}
      aria-invalid={invalid || undefined}
      {...props}
    />
  )
}
