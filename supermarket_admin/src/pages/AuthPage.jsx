import { useState } from 'react'
import { Eye, EyeOff, ArrowLeft, Building2 } from 'lucide-react'

import Button from '../components/ui/Button'
import Field from '../components/ui/Field'
import Input from '../components/ui/Input'
import { useAdminAuth } from '../hooks/useAdminAuth'
import styles from './AuthPage.module.css'

export default function AuthPage() {
  const { login } = useAdminAuth()
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    const formData = new FormData(e.target)
    try {
      const profile = await login({
        email: formData.get('email'),
        password: formData.get('password'),
      })
      // El estado de la cadena decide el destino: el panel solo se abre para
      // cadenas aprobadas (misma regla que ApprovedRoute y que el backend).
      window.location.hash = profile.chain.status === 'approved' ? '#/app/profile' : '#/pending'
    } catch (err) {
      setError(err.message || 'No pudimos iniciar sesión. Revisá tus datos.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.panel}>
        <div className={styles.panelInner}>
          <a href="#/" className={styles.panelLogo}>
            <span className={styles.panelLogoIcon}>✳</span>
            FreshMart<span className={styles.panelLogoDot}>.</span>
          </a>

          <div>
            <h2 className={styles.panelTitle}>
              Tu supermercado,<br />más cerca del cliente.
            </h2>
            <p className={styles.panelSubtitle}>
              Gestioná tus sucursales, tus precios y los pedidos que llegan desde la app,
              todo desde un mismo panel.
            </p>
          </div>

          <p className={styles.panelFooter}>© 2026 FreshMart · Panel de supermercados</p>
        </div>
      </div>

      <div className={styles.formPanel}>
        <a href="#/" className={styles.backLink}>
          <ArrowLeft size={16} aria-hidden="true" />
          Volver al inicio
        </a>

        <div className={styles.formWrap}>
          <form className={styles.form} onSubmit={handleSubmit} noValidate>
            <p className={styles.formTitle}>Acceso para supermercados</p>
            <p className={styles.formSubtitle}>
              Ingresá con la cuenta del responsable o la que te haya invitado tu cadena.
            </p>

            {error && <p className={styles.errorText} role="alert">{error}</p>}

            <Field id="admin-email" label="Correo electrónico" required>
              {({ id, describedBy }) => (
                <Input
                  id={id}
                  name="email"
                  type="email"
                  placeholder="responsable@tusupermercado.com"
                  autoComplete="email"
                  aria-describedby={describedBy}
                  required
                />
              )}
            </Field>

            <Field id="admin-password" label="Contraseña" required>
              {({ id, describedBy }) => (
                <div className={styles.inputWrap}>
                  <Input
                    id={id}
                    name="password"
                    type={showPass ? 'text' : 'password'}
                    placeholder="Tu contraseña"
                    autoComplete="current-password"
                    aria-describedby={describedBy}
                    className={styles.inputPad}
                    required
                  />
                  <button
                    type="button"
                    className={styles.eyeBtn}
                    onClick={() => setShowPass((v) => !v)}
                    aria-label={showPass ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  >
                    {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              )}
            </Field>

            <Button type="submit" disabled={loading}>
              <Building2 size={18} aria-hidden="true" />
              {loading ? 'Un momento…' : 'Iniciar sesión'}
            </Button>

            <p className={styles.switchText}>
              ¿Todavía no registraste tu supermercado?{' '}
              <a href="#/register" className={styles.switchLink}>Registralo gratis</a>
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}
