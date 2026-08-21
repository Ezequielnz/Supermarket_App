import { useState } from 'react'
import { Save } from 'lucide-react'

import Button from '../../components/ui/Button'
import Field from '../../components/ui/Field'
import Input from '../../components/ui/Input'
import TopBar from '../../components/TopBar'
import { useAdminAuth } from '../../hooks/useAdminAuth'
import { updateMyChain } from '../../services/supermarket.service'
import styles from './ProfilePage.module.css'

export default function ProfilePage() {
  const { chain, role, storesCount, refreshProfile } = useAdminAuth()
  const [form, setForm] = useState({
    legal_name: chain?.legal_name ?? '',
    trade_name: chain?.trade_name ?? '',
    contact_email: chain?.contact_email ?? '',
    contact_phone: chain?.contact_phone ?? '',
    logo_url: chain?.logo_url ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  const isOwner = role === 'owner'

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
    setMessage(null)
    setError(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await updateMyChain({
        legal_name: form.legal_name,
        trade_name: form.trade_name,
        contact_email: form.contact_email,
        contact_phone: form.contact_phone || null,
        logo_url: form.logo_url || null,
      })
      await refreshProfile()
      setMessage('Cambios guardados.')
    } catch (err) {
      setError(err.message || 'No pudimos guardar los cambios.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <TopBar
        title="Mi cadena"
        description={`${storesCount} ${storesCount === 1 ? 'sucursal registrada' : 'sucursales registradas'}.`}
      />

      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        {message && <p className={styles.success} role="status">{message}</p>}
        {error && <p className={styles.error} role="alert">{error}</p>}

        {!isOwner && (
          <p className={styles.readonly}>
            Solo el responsable de la cadena puede modificar estos datos.
          </p>
        )}

        <Field id="profile-legal" label="Razón social" required>
          {({ id, describedBy }) => (
            <Input
              id={id}
              value={form.legal_name}
              onChange={(e) => update('legal_name', e.target.value)}
              disabled={!isOwner}
              aria-describedby={describedBy}
            />
          )}
        </Field>

        <Field id="profile-trade" label="Nombre comercial" hint="Es el nombre que ven los clientes en la app." required>
          {({ id, describedBy }) => (
            <Input
              id={id}
              value={form.trade_name}
              onChange={(e) => update('trade_name', e.target.value)}
              disabled={!isOwner}
              aria-describedby={describedBy}
            />
          )}
        </Field>

        <Field
          id="profile-cuit"
          label="CUIT"
          hint="El CUIT no se puede modificar: es la identidad fiscal con la que aprobamos tu cadena. Escribinos si necesitás cambiarlo."
        >
          {({ id, describedBy }) => (
            <Input id={id} value={chain?.tax_id ?? ''} disabled readOnly aria-describedby={describedBy} />
          )}
        </Field>

        <div className={styles.row}>
          <Field id="profile-email" label="Correo de contacto" required>
            {({ id, describedBy }) => (
              <Input
                id={id}
                type="email"
                value={form.contact_email}
                onChange={(e) => update('contact_email', e.target.value)}
                disabled={!isOwner}
                aria-describedby={describedBy}
              />
            )}
          </Field>

          <Field id="profile-phone" label="Teléfono de contacto">
            {({ id, describedBy }) => (
              <Input
                id={id}
                value={form.contact_phone}
                onChange={(e) => update('contact_phone', e.target.value)}
                disabled={!isOwner}
                aria-describedby={describedBy}
              />
            )}
          </Field>
        </div>

        <Field id="profile-logo" label="URL del logo">
          {({ id, describedBy }) => (
            <Input
              id={id}
              value={form.logo_url}
              onChange={(e) => update('logo_url', e.target.value)}
              placeholder="https://..."
              disabled={!isOwner}
              aria-describedby={describedBy}
            />
          )}
        </Field>

        {isOwner && (
          <div className={styles.actions}>
            <Button type="submit" disabled={saving}>
              <Save size={16} aria-hidden="true" />
              {saving ? 'Guardando…' : 'Guardar cambios'}
            </Button>
          </div>
        )}
      </form>
    </>
  )
}
