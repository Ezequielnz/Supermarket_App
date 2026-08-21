import { Clock, XCircle, Ban, MailCheck, LogOut } from 'lucide-react'

import Button from '../components/ui/Button'
import { useAdminAuth } from '../hooks/useAdminAuth'
import styles from './PendingReviewPage.module.css'

// Un contenido por estado de la cadena. El estado lo manda el backend
// (chains.status); acá solo se traduce a algo accionable para el supermercado.
const STATE_CONTENT = {
  pending_review: {
    icon: Clock,
    tone: 'warning',
    title: 'Tu solicitud está en revisión',
    body: 'Estamos verificando los datos de tu supermercado. Normalmente lleva menos de 48 horas hábiles. Te avisamos por correo apenas esté aprobado.',
  },
  rejected: {
    icon: XCircle,
    tone: 'danger',
    title: 'No pudimos aprobar tu solicitud',
    body: 'Revisá el motivo, corregí los datos y volvé a enviarla. Si creés que es un error, escribinos.',
  },
  suspended: {
    icon: Ban,
    tone: 'danger',
    title: 'Tu cuenta está suspendida',
    body: 'Tu supermercado no aparece por ahora en la app. Contactate con soporte para regularizar la situación.',
  },
}

export default function PendingReviewPage() {
  const { chain, logout, refreshProfile } = useAdminAuth()

  // El wizard redirige acá con ?enviado=1 apenas manda la solicitud, cuando
  // todavía no hay sesión iniciada (el correo se confirma primero).
  const justSubmitted = window.location.hash.includes('enviado=1')

  if (justSubmitted && !chain) {
    return (
      <div className={styles.page}>
        <div className={styles.card}>
          <span className={`${styles.icon} ${styles.success}`} aria-hidden="true">
            <MailCheck size={26} />
          </span>
          <h1 className={styles.title}>¡Solicitud enviada!</h1>
          <p className={styles.body}>
            Te mandamos un correo para que confirmes tu dirección. Después de confirmarla vas a
            poder iniciar sesión y seguir el estado de la revisión desde acá.
          </p>
          <div className={styles.actions}>
            <Button onClick={() => { window.location.hash = '#/auth' }}>Ir a iniciar sesión</Button>
          </div>
        </div>
      </div>
    )
  }

  if (!chain) {
    return (
      <div className={styles.page}>
        <div className={styles.card}>
          <h1 className={styles.title}>No encontramos tu supermercado</h1>
          <p className={styles.body}>
            Esta cuenta no está asociada a ninguna cadena. Si te invitaron a un equipo, pedile al
            responsable que verifique el alta.
          </p>
          <div className={styles.actions}>
            <Button onClick={() => { window.location.hash = '#/auth' }}>Volver</Button>
          </div>
        </div>
      </div>
    )
  }

  const content = STATE_CONTENT[chain.status] ?? STATE_CONTENT.pending_review
  const Icon = content.icon

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <span className={`${styles.icon} ${styles[content.tone]}`} aria-hidden="true">
          <Icon size={26} />
        </span>

        <p className="eyebrow">{chain.trade_name}</p>
        <h1 className={styles.title}>{content.title}</h1>
        <p className={styles.body}>{content.body}</p>

        {chain.status === 'rejected' && chain.rejection_reason && (
          <div className={styles.reason}>
            <p className={styles.reasonLabel}>Motivo del rechazo</p>
            <p className={styles.reasonText}>{chain.rejection_reason}</p>
          </div>
        )}

        <dl className={styles.details}>
          <div><dt>Razón social</dt><dd>{chain.legal_name}</dd></div>
          <div><dt>CUIT</dt><dd>{chain.tax_id}</dd></div>
          <div><dt>Contacto</dt><dd>{chain.contact_email}</dd></div>
        </dl>

        <div className={styles.actions}>
          <Button variant="secondary" onClick={refreshProfile}>Actualizar estado</Button>
          <Button variant="ghost" onClick={logout}>
            <LogOut size={16} aria-hidden="true" />
            Cerrar sesión
          </Button>
        </div>
      </div>
    </div>
  )
}
