import styles from './Badge.module.css'

// Estados de la cadena, con el mismo vocabulario que chain_status en la base.
const TONES = {
  pending_review: 'warning',
  approved: 'success',
  rejected: 'danger',
  suspended: 'danger',
}

const CHAIN_STATUS_LABELS = {
  pending_review: 'En revisión',
  approved: 'Aprobado',
  rejected: 'Rechazado',
  suspended: 'Suspendido',
}

export default function Badge({ status, children }) {
  const tone = TONES[status] ?? 'neutral'
  return (
    <span className={`${styles.badge} ${styles[tone]}`}>
      {children ?? CHAIN_STATUS_LABELS[status] ?? status}
    </span>
  )
}
