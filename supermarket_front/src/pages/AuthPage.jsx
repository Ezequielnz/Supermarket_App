import { useState } from 'react'
import { Eye, EyeOff, ArrowLeft, ShoppingCart } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import styles from './AuthPage.module.css'

export default function AuthPage() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [showPass, setShowPass] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const isLogin = mode === 'login'

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)

    const formData = new FormData(e.target)
    const email = formData.get('email')
    const password = formData.get('password')

    if (!isLogin && password !== formData.get('confirmPassword')) {
      setError('Las contraseñas no coinciden')
      return
    }

    setLoading(true)
    try {
      if (isLogin) {
        await login({ email, password })
      } else {
        const fullName = `${formData.get('firstName')} ${formData.get('lastName') || ''}`.trim()
        await register({ email, password, fullName, phone: null })
      }
      window.location.hash = '#/app'
    } catch (err) {
      setError(err.message || 'Ocurrió un error. Intenta nuevamente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      {/* ── Left panel (decorative) ── */}
      <div className={styles.panel}>
        <div className={styles.panelInner}>
          <a href="#/" className={styles.panelLogo}>
            <span className={styles.panelLogoIcon}>✳</span>
            FreshMart<span className={styles.panelLogoDot}>.</span>
          </a>

          <div className={styles.panelContent}>
            <h2 className={styles.panelTitle}>
              Compra inteligente,<br />ahorra de verdad.
            </h2>
            <p className={styles.panelSubtitle}>
              Compara precios entre supermercados, arma tu lista y decide dónde comprar para gastar menos cada semana.
            </p>

            <div className={styles.featureList}>
              {[
                { icon: '📋', text: 'Lista de compras inteligente' },
                { icon: '🏪', text: 'Compara entre múltiples supermercados' },
                { icon: '💰', text: 'Ve cuánto ahorras con sustitutos' },
                { icon: '📊', text: 'Historial y tendencias de precios' },
              ].map(f => (
                <div key={f.text} className={styles.featureItem}>
                  <span className={styles.featureIcon}>{f.icon}</span>
                  <span>{f.text}</span>
                </div>
              ))}
            </div>
          </div>

          <p className={styles.panelFooter}>
            © 2026 FreshMart · Tu comparador de supermercados
          </p>
        </div>

        {/* Decorative circles */}
        <div className={styles.circle1} />
        <div className={styles.circle2} />
        <div className={styles.circle3} />
      </div>

      {/* ── Right panel (form) ── */}
      <div className={styles.formPanel}>
        <a href="#/" className={styles.backLink}>
          <ArrowLeft size={16} />
          Volver al inicio
        </a>

        <div className={styles.formWrap}>
          {/* Logo mobile */}
          <a href="#/" className={styles.mobileLogo}>
            <span className={styles.mobileLogoIcon}>✳</span>
            FreshMart<span className={styles.panelLogoDot}>.</span>
          </a>

          {/* Tab toggle */}
          <div className={styles.tabs} role="tablist">
            <button
              role="tab"
              aria-selected={isLogin}
              className={`${styles.tab} ${isLogin ? styles.tabActive : ''}`}
              onClick={() => { setMode('login'); setError(null) }}
            >
              Iniciar sesión
            </button>
            <button
              role="tab"
              aria-selected={!isLogin}
              className={`${styles.tab} ${!isLogin ? styles.tabActive : ''}`}
              onClick={() => { setMode('register'); setError(null) }}
            >
              Registrarse
            </button>
          </div>

          <form className={styles.form} onSubmit={handleSubmit} noValidate>
            <p className={styles.formTitle}>
              {isLogin ? 'Accede a tu cuenta' : 'Crea tu cuenta gratis'}
            </p>
            <p className={styles.formSubtitle}>
              {isLogin
                ? 'Ingresa tus datos para ver tu lista y comparaciones guardadas.'
                : 'Empieza a comparar precios y ahorrar en tu compra semanal.'}
            </p>

            {error && <p className={styles.errorText}>{error}</p>}

            {!isLogin && (
              <div className={styles.row}>
                <div className={styles.field}>
                  <label className={styles.label} htmlFor="auth-name">Nombre</label>
                  <input
                    id="auth-name"
                    name="firstName"
                    type="text"
                    className={styles.input}
                    placeholder="Tu nombre"
                    autoComplete="given-name"
                    required
                  />
                </div>
                <div className={styles.field}>
                  <label className={styles.label} htmlFor="auth-lastname">Apellido</label>
                  <input
                    id="auth-lastname"
                    name="lastName"
                    type="text"
                    className={styles.input}
                    placeholder="Tu apellido"
                    autoComplete="family-name"
                  />
                </div>
              </div>
            )}

            <div className={styles.field}>
              <label className={styles.label} htmlFor="auth-email">Correo electrónico</label>
              <input
                id="auth-email"
                name="email"
                type="email"
                className={styles.input}
                placeholder="tu@correo.com"
                autoComplete="email"
                required
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="auth-password">Contraseña</label>
              <div className={styles.inputWrap}>
                <input
                  id="auth-password"
                  name="password"
                  type={showPass ? 'text' : 'password'}
                  className={`${styles.input} ${styles.inputPad}`}
                  placeholder={isLogin ? 'Tu contraseña' : 'Mínimo 8 caracteres'}
                  autoComplete={isLogin ? 'current-password' : 'new-password'}
                  minLength={isLogin ? undefined : 8}
                  required
                />
                <button
                  type="button"
                  className={styles.eyeBtn}
                  onClick={() => setShowPass(v => !v)}
                  aria-label={showPass ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                >
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {!isLogin && (
              <div className={styles.field}>
                <label className={styles.label} htmlFor="auth-confirm">Confirmar contraseña</label>
                <div className={styles.inputWrap}>
                  <input
                    id="auth-confirm"
                    name="confirmPassword"
                    type={showConfirm ? 'text' : 'password'}
                    className={`${styles.input} ${styles.inputPad}`}
                    placeholder="Repite tu contraseña"
                    autoComplete="new-password"
                    required
                  />
                  <button
                    type="button"
                    className={styles.eyeBtn}
                    onClick={() => setShowConfirm(v => !v)}
                    aria-label={showConfirm ? 'Ocultar' : 'Mostrar'}
                  >
                    {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
            )}

            {isLogin && (
              <div className={styles.forgotRow}>
                <a href="#/" className={styles.forgotLink}>¿Olvidaste tu contraseña?</a>
              </div>
            )}

            <button type="submit" className={styles.submitBtn} disabled={loading}>
              <ShoppingCart size={18} />
              {loading ? 'Un momento…' : isLogin ? 'Iniciar sesión' : 'Crear cuenta'}
            </button>

            <p className={styles.switchText}>
              {isLogin ? '¿No tienes cuenta?' : '¿Ya tienes cuenta?'}{' '}
              <button
                type="button"
                className={styles.switchLink}
                onClick={() => { setMode(isLogin ? 'register' : 'login'); setError(null) }}
              >
                {isLogin ? 'Regístrate gratis' : 'Inicia sesión'}
              </button>
            </p>

            {!isLogin && (
              <p className={styles.terms}>
                Al registrarte aceptas nuestros{' '}
                <a href="#/" className={styles.termsLink}>Términos de uso</a>{' '}
                y{' '}
                <a href="#/" className={styles.termsLink}>Política de privacidad</a>.
              </p>
            )}
          </form>
        </div>
      </div>
    </div>
  )
}
