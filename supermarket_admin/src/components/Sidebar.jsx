import { NavLink } from 'react-router-dom'
import { Store, Building2, Users, Package, LogOut } from 'lucide-react'

import { useAdminAuth } from '../hooks/useAdminAuth'
import styles from './Sidebar.module.css'

const NAV_ITEMS = [
  { to: '/app/profile', label: 'Mi cadena', icon: Building2 },
  { to: '/app/stores', label: 'Sucursales', icon: Store },
  // Sin ownerOnly: el rol 'staff' ve los precios de su cadena, solo que no los
  // edita (matriz de docs/SEGURIDAD.md §4.2). El filtro de escritura esta
  // dentro de la pagina, no en la navegacion.
  { to: '/app/products', label: 'Productos', icon: Package },
  { to: '/app/team', label: 'Equipo', icon: Users, ownerOnly: true },
]

export default function Sidebar() {
  const { chain, role, logout } = useAdminAuth()

  const items = NAV_ITEMS.filter((item) => !item.ownerOnly || role === 'owner')

  return (
    <nav className={styles.sidebar} aria-label="Navegación principal">
      <div className={styles.brand}>
        <span className={styles.brandMark} aria-hidden="true">✳</span>
        <span className={styles.brandText}>
          FreshMart
          <span className={styles.brandSub}>Panel de supermercados</span>
        </span>
      </div>

      <p className={styles.chainName}>{chain?.trade_name}</p>

      <ul className={styles.list}>
        {items.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              className={({ isActive }) => `${styles.link} ${isActive ? styles.linkActive : ''}`}
            >
              <Icon size={17} aria-hidden="true" />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>

      <button type="button" className={styles.logout} onClick={logout}>
        <LogOut size={17} aria-hidden="true" />
        Cerrar sesión
      </button>
    </nav>
  )
}
