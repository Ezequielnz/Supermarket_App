import Badge from './ui/Badge'
import { useAdminAuth } from '../hooks/useAdminAuth'
import styles from './TopBar.module.css'

const ROLE_LABELS = {
  owner: 'Responsable',
  manager: 'Encargado',
  staff: 'Empleado',
}

export default function TopBar({ title, description, actions }) {
  const { chain, role, user } = useAdminAuth()

  return (
    <header className={styles.topbar}>
      <div className={styles.headings}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>{title}</h1>
          {chain && <Badge status={chain.status} />}
        </div>
        {description && <p className={styles.description}>{description}</p>}
      </div>

      <div className={styles.meta}>
        {actions}
        <div className={styles.user}>
          <span className={styles.userEmail}>{user?.email}</span>
          <span className={styles.userRole}>{ROLE_LABELS[role] ?? role}</span>
        </div>
      </div>
    </header>
  )
}
