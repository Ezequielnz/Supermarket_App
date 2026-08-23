import { useState } from 'react'
import { ArrowLeft, ArrowRight, Check } from 'lucide-react'

import Button from '../components/ui/Button'
import Field from '../components/ui/Field'
import Input from '../components/ui/Input'
import { useAdminAuth } from '../hooks/useAdminAuth'
import { registerSupermarket } from '../services/supermarket.service'
import styles from './RegisterPage.module.css'

const STEPS = [
  { id: 'account', label: 'Responsable' },
  { id: 'chain', label: 'Tu cadena' },
  { id: 'store', label: 'Primera sucursal' },
  { id: 'review', label: 'Revisión' },
]

// 0 = domingo, igual que store_hours.weekday y que EXTRACT(DOW) en Postgres.
const WEEKDAYS = [
  { value: 1, label: 'Lunes' },
  { value: 2, label: 'Martes' },
  { value: 3, label: 'Miércoles' },
  { value: 4, label: 'Jueves' },
  { value: 5, label: 'Viernes' },
  { value: 6, label: 'Sábado' },
  { value: 0, label: 'Domingo' },
]

const DEFAULT_OPEN = '08:00'
const DEFAULT_CLOSE = '21:00'

const INITIAL_FORM = {
  email: '',
  password: '',
  confirmPassword: '',
  owner_full_name: '',
  owner_phone: '',
  legal_name: '',
  trade_name: '',
  tax_id: '',
  contact_email: '',
  contact_phone: '',
  storeName: '',
  street: '',
  city: '',
  province: '',
  postal_code: '',
  storePhone: '',
  accepts_terms: false,
}

// Lunes a sábado abierto por defecto: es lo más común y ahorra 6 interacciones.
const INITIAL_HOURS = WEEKDAYS.reduce((acc, day) => {
  acc[day.value] = { open: day.value !== 0, opens_at: DEFAULT_OPEN, closes_at: DEFAULT_CLOSE }
  return acc
}, {})

function digitsOnly(value) {
  return value.replace(/\D/g, '')
}

function validateStep(step, form, hours) {
  const errors = {}

  if (step === 0) {
    if (!form.owner_full_name.trim()) errors.owner_full_name = 'Ingresá tu nombre y apellido.'
    if (!form.email.trim()) errors.email = 'Ingresá tu correo.'
    if (form.password.length < 8) errors.password = 'La contraseña debe tener al menos 8 caracteres.'
    if (form.password !== form.confirmPassword) errors.confirmPassword = 'Las contraseñas no coinciden.'
  }

  if (step === 1) {
    if (!form.legal_name.trim()) errors.legal_name = 'Ingresá la razón social.'
    if (!form.trade_name.trim()) errors.trade_name = 'Ingresá el nombre comercial.'
    // El backend valida lo mismo (CHECK tax_id_format de la migración 010);
    // acá se adelanta el mensaje para no gastar un round-trip.
    if (digitsOnly(form.tax_id).length !== 11) errors.tax_id = 'El CUIT debe tener 11 dígitos.'
    if (!form.contact_email.trim()) errors.contact_email = 'Ingresá un correo de contacto.'
  }

  if (step === 2) {
    if (!form.storeName.trim()) errors.storeName = 'Ingresá el nombre de la sucursal.'
    if (!form.street.trim()) errors.street = 'Ingresá la calle y el número.'
    if (!form.city.trim()) errors.city = 'Ingresá la ciudad.'

    const invalidDay = WEEKDAYS.find(
      (d) => hours[d.value].open && hours[d.value].closes_at <= hours[d.value].opens_at,
    )
    if (invalidDay) {
      errors.hours = `El cierre debe ser posterior a la apertura (${invalidDay.label}).`
    }
  }

  if (step === 3 && !form.accepts_terms) {
    errors.accepts_terms = 'Tenés que aceptar los términos para continuar.'
  }

  return errors
}

export default function RegisterPage() {
  const { login } = useAdminAuth()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState(INITIAL_FORM)
  const [hours, setHours] = useState(INITIAL_HOURS)
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState(null)
  const [loading, setLoading] = useState(false)

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
    setErrors((prev) => ({ ...prev, [field]: undefined }))
  }

  function updateHours(weekday, patch) {
    setHours((prev) => ({ ...prev, [weekday]: { ...prev[weekday], ...patch } }))
    setErrors((prev) => ({ ...prev, hours: undefined }))
  }

  function goNext() {
    const stepErrors = validateStep(step, form, hours)
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors)
      return
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1))
  }

  function goBack() {
    setSubmitError(null)
    setStep((s) => Math.max(s - 1, 0))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const stepErrors = validateStep(3, form, hours)
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors)
      return
    }

    setSubmitError(null)
    setLoading(true)
    try {
      // Un solo POST al final: los pasos anteriores son estado local, no
      // requests parciales, así no queda una cadena a medio crear si el
      // usuario abandona el wizard.
      await registerSupermarket({
        email: form.email,
        password: form.password,
        owner_full_name: form.owner_full_name,
        owner_phone: form.owner_phone || null,
        legal_name: form.legal_name,
        trade_name: form.trade_name,
        tax_id: digitsOnly(form.tax_id),
        contact_email: form.contact_email,
        contact_phone: form.contact_phone || null,
        store: {
          name: form.storeName,
          street: form.street,
          city: form.city,
          province: form.province || null,
          postal_code: form.postal_code || null,
          phone: form.storePhone || null,
          hours: WEEKDAYS.filter((d) => hours[d.value].open).map((d) => ({
            weekday: d.value,
            opens_at: hours[d.value].opens_at,
            closes_at: hours[d.value].closes_at,
          })),
        },
        accepts_terms: form.accepts_terms,
      })
    } catch (err) {
      setSubmitError(err.message || 'No pudimos completar el registro. Intentá nuevamente.')
      setLoading(false)
      return
    }

    // TEMPORAL: la cuenta se crea ya confirmada mientras
    // REQUIRE_EMAIL_CONFIRMATION esté en False en supermarket_auth_service.py
    // (sin SMTP propio configurado), así que se puede iniciar sesión de
    // inmediato en vez de mandar a esperar un correo. Revertir junto con esa
    // constante: volver a `window.location.hash = '#/pending?enviado=1'` sin
    // loguear.
    try {
      const profile = await login({ email: form.email, password: form.password })
      window.location.hash = profile.chain.status === 'approved' ? '#/app/profile' : '#/pending'
    } catch {
      // El registro salió bien igual: si el login automático falla, que inicie
      // sesión a mano en vez de mostrar un error que sugiera que el alta falló.
      window.location.hash = '#/auth'
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <a href="#/" className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">✳</span>
          FreshMart
        </a>
        <a href="#/auth" className={styles.headerLink}>Ya tengo cuenta</a>
      </header>

      <main className={styles.main}>
        <div className={styles.card}>
          <ol className={styles.steps}>
            {STEPS.map((s, index) => (
              <li
                key={s.id}
                className={`${styles.step} ${index === step ? styles.stepActive : ''} ${index < step ? styles.stepDone : ''}`}
                aria-current={index === step ? 'step' : undefined}
              >
                <span className={styles.stepNumber} aria-hidden="true">
                  {index < step ? <Check size={13} /> : index + 1}
                </span>
                <span className={styles.stepLabel}>{s.label}</span>
              </li>
            ))}
          </ol>

          <form className={styles.form} onSubmit={handleSubmit} noValidate>
            {submitError && <p className={styles.errorBanner} role="alert">{submitError}</p>}

            {step === 0 && (
              <section className={styles.section}>
                <h2 className={styles.sectionTitle}>Datos del responsable</h2>
                <p className={styles.sectionHint}>
                  Esta será la cuenta principal de tu supermercado. Vas a poder invitar a tu
                  equipo después.
                </p>

                <Field id="reg-owner-name" label="Nombre y apellido" error={errors.owner_full_name} required>
                  {({ id, describedBy }) => (
                    <Input
                      id={id}
                      value={form.owner_full_name}
                      onChange={(e) => update('owner_full_name', e.target.value)}
                      autoComplete="name"
                      invalid={Boolean(errors.owner_full_name)}
                      aria-describedby={describedBy}
                    />
                  )}
                </Field>

                <Field
                  id="reg-email"
                  label="Correo electrónico"
                  error={errors.email}
                  // TEMPORAL: sin confirmación de correo (ver el comentario
                  // junto a REQUIRE_EMAIL_CONFIRMATION en
                  // supermarket_auth_service.py). Revertir el hint junto con
                  // esa constante.
                  hint="Va a ser el usuario con el que inicies sesión."
                  required
                >
                  {({ id, describedBy }) => (
                    <Input
                      id={id}
                      type="email"
                      value={form.email}
                      onChange={(e) => update('email', e.target.value)}
                      autoComplete="email"
                      invalid={Boolean(errors.email)}
                      aria-describedby={describedBy}
                    />
                  )}
                </Field>

                <Field id="reg-phone" label="Teléfono">
                  {({ id, describedBy }) => (
                    <Input
                      id={id}
                      value={form.owner_phone}
                      onChange={(e) => update('owner_phone', e.target.value)}
                      autoComplete="tel"
                      aria-describedby={describedBy}
                    />
                  )}
                </Field>

                <div className={styles.row}>
                  <Field id="reg-password" label="Contraseña" error={errors.password} hint="Mínimo 8 caracteres." required>
                    {({ id, describedBy }) => (
                      <Input
                        id={id}
                        type="password"
                        value={form.password}
                        onChange={(e) => update('password', e.target.value)}
                        autoComplete="new-password"
                        invalid={Boolean(errors.password)}
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>

                  <Field id="reg-confirm" label="Repetir contraseña" error={errors.confirmPassword} required>
                    {({ id, describedBy }) => (
                      <Input
                        id={id}
                        type="password"
                        value={form.confirmPassword}
                        onChange={(e) => update('confirmPassword', e.target.value)}
                        autoComplete="new-password"
                        invalid={Boolean(errors.confirmPassword)}
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>
                </div>
              </section>
            )}

            {step === 1 && (
              <section className={styles.section}>
                <h2 className={styles.sectionTitle}>Datos de la cadena</h2>
                <p className={styles.sectionHint}>
                  Usamos estos datos para verificar tu supermercado antes de publicarlo.
                </p>

                <Field id="reg-legal" label="Razón social" error={errors.legal_name} hint="Como figura en AFIP." required>
                  {({ id, describedBy }) => (
                    <Input
                      id={id}
                      value={form.legal_name}
                      onChange={(e) => update('legal_name', e.target.value)}
                      invalid={Boolean(errors.legal_name)}
                      aria-describedby={describedBy}
                    />
                  )}
                </Field>

                <Field
                  id="reg-trade"
                  label="Nombre comercial"
                  error={errors.trade_name}
                  hint="Es el nombre que van a ver los clientes en la app."
                  required
                >
                  {({ id, describedBy }) => (
                    <Input
                      id={id}
                      value={form.trade_name}
                      onChange={(e) => update('trade_name', e.target.value)}
                      invalid={Boolean(errors.trade_name)}
                      aria-describedby={describedBy}
                    />
                  )}
                </Field>

                <Field id="reg-cuit" label="CUIT" error={errors.tax_id} hint="11 dígitos, con o sin guiones." required>
                  {({ id, describedBy }) => (
                    <Input
                      id={id}
                      value={form.tax_id}
                      onChange={(e) => update('tax_id', e.target.value)}
                      inputMode="numeric"
                      placeholder="30-71234567-8"
                      invalid={Boolean(errors.tax_id)}
                      aria-describedby={describedBy}
                    />
                  )}
                </Field>

                <div className={styles.row}>
                  <Field id="reg-contact-email" label="Correo de contacto" error={errors.contact_email} required>
                    {({ id, describedBy }) => (
                      <Input
                        id={id}
                        type="email"
                        value={form.contact_email}
                        onChange={(e) => update('contact_email', e.target.value)}
                        invalid={Boolean(errors.contact_email)}
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>

                  <Field id="reg-contact-phone" label="Teléfono de contacto">
                    {({ id, describedBy }) => (
                      <Input
                        id={id}
                        value={form.contact_phone}
                        onChange={(e) => update('contact_phone', e.target.value)}
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>
                </div>
              </section>
            )}

            {step === 2 && (
              <section className={styles.section}>
                <h2 className={styles.sectionTitle}>Primera sucursal</h2>
                <p className={styles.sectionHint}>
                  Después vas a poder agregar todas las sucursales que quieras desde el panel.
                </p>

                <Field
                  id="reg-store-name"
                  label="Nombre de la sucursal"
                  error={errors.storeName}
                  hint="Por ejemplo: SurMarket Centro."
                  required
                >
                  {({ id, describedBy }) => (
                    <Input
                      id={id}
                      value={form.storeName}
                      onChange={(e) => update('storeName', e.target.value)}
                      invalid={Boolean(errors.storeName)}
                      aria-describedby={describedBy}
                    />
                  )}
                </Field>

                <Field id="reg-street" label="Calle y número" error={errors.street} required>
                  {({ id, describedBy }) => (
                    <Input
                      id={id}
                      value={form.street}
                      onChange={(e) => update('street', e.target.value)}
                      autoComplete="street-address"
                      invalid={Boolean(errors.street)}
                      aria-describedby={describedBy}
                    />
                  )}
                </Field>

                <div className={styles.row}>
                  <Field id="reg-city" label="Ciudad" error={errors.city} required>
                    {({ id, describedBy }) => (
                      <Input
                        id={id}
                        value={form.city}
                        onChange={(e) => update('city', e.target.value)}
                        invalid={Boolean(errors.city)}
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>

                  <Field id="reg-province" label="Provincia">
                    {({ id, describedBy }) => (
                      <Input
                        id={id}
                        value={form.province}
                        onChange={(e) => update('province', e.target.value)}
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>
                </div>

                <div className={styles.row}>
                  <Field id="reg-postal" label="Código postal">
                    {({ id, describedBy }) => (
                      <Input
                        id={id}
                        value={form.postal_code}
                        onChange={(e) => update('postal_code', e.target.value)}
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>

                  <Field id="reg-store-phone" label="Teléfono de la sucursal">
                    {({ id, describedBy }) => (
                      <Input
                        id={id}
                        value={form.storePhone}
                        onChange={(e) => update('storePhone', e.target.value)}
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>
                </div>

                <fieldset className={styles.hoursFieldset}>
                  <legend className={styles.hoursLegend}>Horarios de atención</legend>
                  <p className={styles.sectionHint}>
                    Los usamos para que nadie agende un retiro con el local cerrado.
                  </p>
                  {errors.hours && <p className={styles.errorText} role="alert">{errors.hours}</p>}

                  {WEEKDAYS.map((day) => (
                    <div key={day.value} className={styles.hoursRow}>
                      <label className={styles.hoursDay} htmlFor={`open-${day.value}`}>
                        <input
                          id={`open-${day.value}`}
                          type="checkbox"
                          checked={hours[day.value].open}
                          onChange={(e) => updateHours(day.value, { open: e.target.checked })}
                        />
                        {day.label}
                      </label>

                      <div className={styles.hoursInputs}>
                        <label className={styles.srOnly} htmlFor={`opens-${day.value}`}>
                          Hora de apertura de {day.label}
                        </label>
                        <Input
                          id={`opens-${day.value}`}
                          type="time"
                          value={hours[day.value].opens_at}
                          disabled={!hours[day.value].open}
                          onChange={(e) => updateHours(day.value, { opens_at: e.target.value })}
                        />
                        <span aria-hidden="true">–</span>
                        <label className={styles.srOnly} htmlFor={`closes-${day.value}`}>
                          Hora de cierre de {day.label}
                        </label>
                        <Input
                          id={`closes-${day.value}`}
                          type="time"
                          value={hours[day.value].closes_at}
                          disabled={!hours[day.value].open}
                          onChange={(e) => updateHours(day.value, { closes_at: e.target.value })}
                        />
                      </div>
                    </div>
                  ))}
                </fieldset>
              </section>
            )}

            {step === 3 && (
              <section className={styles.section}>
                <h2 className={styles.sectionTitle}>Revisá y enviá</h2>
                <p className={styles.sectionHint}>
                  Vamos a verificar los datos antes de publicar tu supermercado en la app.
                  Normalmente lleva menos de 48 horas.
                </p>

                <dl className={styles.summary}>
                  <div><dt>Responsable</dt><dd>{form.owner_full_name}</dd></div>
                  <div><dt>Correo</dt><dd>{form.email}</dd></div>
                  <div><dt>Razón social</dt><dd>{form.legal_name}</dd></div>
                  <div><dt>Nombre comercial</dt><dd>{form.trade_name}</dd></div>
                  <div><dt>CUIT</dt><dd>{digitsOnly(form.tax_id)}</dd></div>
                  <div><dt>Sucursal</dt><dd>{form.storeName}</dd></div>
                  <div><dt>Dirección</dt><dd>{[form.street, form.city].filter(Boolean).join(', ')}</dd></div>
                  <div>
                    <dt>Días abiertos</dt>
                    <dd>
                      {WEEKDAYS.filter((d) => hours[d.value].open).map((d) => d.label).join(', ') || 'Ninguno'}
                    </dd>
                  </div>
                </dl>

                <label className={styles.terms} htmlFor="reg-terms">
                  <input
                    id="reg-terms"
                    type="checkbox"
                    checked={form.accepts_terms}
                    onChange={(e) => update('accepts_terms', e.target.checked)}
                  />
                  <span>
                    Acepto los <a href="#/" className={styles.termsLink}>Términos de uso</a> y la{' '}
                    <a href="#/" className={styles.termsLink}>Política de privacidad</a> de FreshMart.
                  </span>
                </label>
                {errors.accepts_terms && (
                  <p className={styles.errorText} role="alert">{errors.accepts_terms}</p>
                )}
              </section>
            )}

            <div className={styles.actions}>
              {step > 0 ? (
                <Button variant="secondary" onClick={goBack} disabled={loading}>
                  <ArrowLeft size={16} aria-hidden="true" />
                  Atrás
                </Button>
              ) : (
                <span />
              )}

              {step < STEPS.length - 1 ? (
                <Button onClick={goNext}>
                  Continuar
                  <ArrowRight size={16} aria-hidden="true" />
                </Button>
              ) : (
                <Button type="submit" disabled={loading}>
                  {loading ? 'Enviando…' : 'Enviar solicitud'}
                  <Check size={16} aria-hidden="true" />
                </Button>
              )}
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}
