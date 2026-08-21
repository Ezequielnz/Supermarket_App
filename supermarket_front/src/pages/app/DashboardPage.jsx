import { ListChecks, LogOut } from 'lucide-react'

import { useAuth } from '../../hooks/useAuth'
import { useLists } from '../../hooks/useLists'
import styles from './DashboardPage.module.css'

export default function DashboardPage() {
  const { user, logout } = useAuth()
  const { lists, loading } = useLists()

  function handleLogout() {
    logout().then(() => {
      window.location.hash = '#/'
    })
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <p className={styles.greeting}>
          Hola, {user?.user_metadata?.full_name || user?.email}
        </p>
        <button className={styles.logoutBtn} onClick={handleLogout}>
          <LogOut size={16} /> Cerrar sesión
        </button>
      </div>

      <div className={styles.card}>
        <div className={styles.cardHead}>
          <h2 className={styles.cardTitle}>Mis listas</h2>
          <a href="#/app/lists" className={styles.cardLink}>Ver todas</a>
        </div>

        {loading ? (
          <p className={styles.muted}>Cargando…</p>
        ) : lists.length === 0 ? (
          <p className={styles.muted}>Todavía no tenés listas de compra.</p>
        ) : (
          <div className={styles.previewList}>
            {lists.slice(0, 3).map((list) => (
              <a key={list.id} href={`#/app/lists/${list.id}`} className={styles.previewItem}>
                <span>{list.name}</span>
                <span className={styles.previewMeta}>{list.items_count} producto{list.items_count === 1 ? '' : 's'}</span>
              </a>
            ))}
          </div>
        )}

        <a href="#/app/lists" className={styles.ctaBtn}>
          <ListChecks size={18} /> Ver mis listas
        </a>
      </div>
    </div>
  )
}
