import { useState } from 'react'
import { Menu, X } from 'lucide-react'
import styles from './Navbar.module.css'

// Solo para la landing publica. El carrito vive en /app, detras del login, y
// tiene su propia barra (AppNav): esta recibia cartCount y onCartOpen y no
// usaba ninguno de los dos.
export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false)

  function goAuth(e) {
    e.preventDefault()
    window.location.hash = '#/auth'
    setMenuOpen(false)
  }

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <a href="#inicio" className={styles.logo} aria-label="FreshMart, inicio">
          <span className={styles.logoIcon}>✳</span>
          FreshMart<span className={styles.logoDot}>.</span>
        </a>

        <nav className={styles.desktopNav}>
          <a href="#como-funciona" className={styles.navLink}>Cómo funciona</a>
          <a href="#comparador" className={styles.navLink}>Comparador</a>
          <a href="#sustitutos" className={styles.navLink}>Sustitutos</a>
        </nav>

        <div className={styles.actions}>
          <a href="#/auth" onClick={goAuth} className={styles.loginBtn}>
            Iniciar sesión
          </a>
          <a href="#/auth" onClick={goAuth} className={styles.registerBtn}>
            Registrarse gratis
          </a>
          <button
            className={styles.menuBtn}
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Abrir menú"
          >
            {menuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {menuOpen && (
        <nav className={styles.mobileNav}>
          <a href="#como-funciona" onClick={() => setMenuOpen(false)}>Cómo funciona</a>
          <a href="#comparador" onClick={() => setMenuOpen(false)}>Comparador</a>
          <a href="#sustitutos" onClick={() => setMenuOpen(false)}>Sustitutos</a>
          <a href="#/auth" onClick={goAuth} className={styles.mobileAuthLink}>Iniciar sesión</a>
          <a href="#/auth" onClick={goAuth} className={styles.mobileRegisterLink}>Registrarse gratis →</a>
        </nav>
      )}
    </header>
  )
}
