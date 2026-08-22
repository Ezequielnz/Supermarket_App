import { NavLink } from 'react-router-dom'
import { Compass, ListChecks, Package, ShoppingCart, LogOut } from 'lucide-react'

import CartDrawer from './CartDrawer'
import { useAuth } from '../hooks/useAuth'
import { useCart } from '../hooks/useCart'
import styles from './AppNav.module.css'

// Navegacion de /app. Hasta ahora cada pantalla tenia un enlace "volver" y nada
// mas: no habia forma de ir de las listas a los pedidos sin pasar por el
// panel. Navbar.jsx es solo para la landing publica.
const NAV_ITEMS = [
  { to: '/app/explore', label: 'Explorar', icon: Compass },
  { to: '/app/lists', label: 'Mis listas', icon: ListChecks },
  { to: '/app/orders', label: 'Pedidos', icon: Package },
]

export default function AppNav() {
  const { logout } = useAuth()
  const { count, open, openCart, closeCart } = useCart()

  function handleLogout() {
    logout().then(() => { window.location.hash = '#/' })
  }

  return (
    <>
      <header className={styles.bar}>
        <a href="#/app" className={styles.brand} aria-label="FreshMart, inicio">
          <span className={styles.brandMark} aria-hidden="true">✳</span>
          FreshMart
        </a>

        <nav className={styles.nav} aria-label="Navegación principal">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `${styles.link} ${isActive ? styles.linkActive : ''}`}
            >
              <Icon size={16} aria-hidden="true" />
              <span className={styles.linkLabel}>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className={styles.actions}>
          <button
            type="button"
            className={styles.cartBtn}
            onClick={openCart}
            aria-label={`Abrir carrito, ${count} producto${count === 1 ? '' : 's'}`}
          >
            <ShoppingCart size={18} aria-hidden="true" />
            {count > 0 && <span className={styles.badge}>{count}</span>}
          </button>

          <button
            type="button"
            className={styles.logoutBtn}
            onClick={handleLogout}
            aria-label="Cerrar sesión"
          >
            <LogOut size={17} aria-hidden="true" />
          </button>
        </div>
      </header>

      {open && <CartDrawer onClose={closeCart} />}
    </>
  )
}
