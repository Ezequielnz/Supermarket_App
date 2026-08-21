import styles from './Field.module.css'

// Un input con su label asociado por htmlFor/id y su mensaje de error.
// Centraliza el requisito de accesibilidad de NORMAS.md §8: todo campo tiene
// label, y el error se anuncia con aria-describedby.
export default function Field({ id, label, error, hint, children, required = false }) {
  const errorId = error ? `${id}-error` : undefined
  const hintId = hint ? `${id}-hint` : undefined

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={id}>
        {label}
        {required && <span className={styles.required} aria-hidden="true"> *</span>}
      </label>
      {children({ id, describedBy: [hintId, errorId].filter(Boolean).join(' ') || undefined })}
      {hint && <p className={styles.hint} id={hintId}>{hint}</p>}
      {error && <p className={styles.error} id={errorId} role="alert">{error}</p>}
    </div>
  )
}
