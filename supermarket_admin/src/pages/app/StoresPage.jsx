import { useEffect, useState, useCallback } from 'react'
import { Plus, MapPin, Clock } from 'lucide-react'

import Button from '../../components/ui/Button'
import Field from '../../components/ui/Field'
import Input from '../../components/ui/Input'
import TopBar from '../../components/TopBar'
import { useAdminAuth } from '../../hooks/useAdminAuth'
import { createStore, getMyStores } from '../../services/supermarket.service'
import styles from './StoresPage.module.css'

const WEEKDAY_LABELS = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']

const EMPTY_STORE = { name: '', street: '', city: '', province: '', postal_code: '', phone: '' }

function formatHours(hours) {
  if (!hours || hours.length === 0) return 'Sin horarios cargados'
  return hours
    .slice()
    .sort((a, b) => a.weekday - b.weekday)
    .map((h) => `${WEEKDAY_LABELS[h.weekday]} ${h.opens_at.slice(0, 5)}–${h.closes_at.slice(0, 5)}`)
    .join(' · ')
}

export default function StoresPage() {
  const { role } = useAdminAuth()
  const [stores, setStores] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_STORE)
  const [saving, setSaving] = useState(false)

  const canManage = role === 'owner' || role === 'manager'

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await getMyStores()
      setStores(result.data)
      setError(null)
    } catch (err) {
      setError(err.message || 'No pudimos cargar tus sucursales.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await createStore({
        name: form.name,
        street: form.street,
        city: form.city,
        province: form.province || null,
        postal_code: form.postal_code || null,
        phone: form.phone || null,
        hours: [],
      })
      setForm(EMPTY_STORE)
      setShowForm(false)
      await load()
    } catch (err) {
      setError(err.message || 'No pudimos crear la sucursal.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <TopBar
        title="Sucursales"
        description="Cada sucursal tiene su dirección y sus horarios. El cliente elige dónde retirar."
        actions={
          canManage && (
            <Button onClick={() => setShowForm((v) => !v)}>
              <Plus size={16} aria-hidden="true" />
              {showForm ? 'Cancelar' : 'Nueva sucursal'}
            </Button>
          )
        }
      />

      {error && <p className={styles.error} role="alert">{error}</p>}

      {showForm && canManage && (
        <form className={styles.form} onSubmit={handleSubmit} noValidate>
          <h2 className={styles.formTitle}>Nueva sucursal</h2>

          <Field id="store-name" label="Nombre" required>
            {({ id, describedBy }) => (
              <Input id={id} value={form.name} onChange={(e) => update('name', e.target.value)} aria-describedby={describedBy} required />
            )}
          </Field>

          <Field id="store-street" label="Calle y número" required>
            {({ id, describedBy }) => (
              <Input id={id} value={form.street} onChange={(e) => update('street', e.target.value)} aria-describedby={describedBy} required />
            )}
          </Field>

          <div className={styles.row}>
            <Field id="store-city" label="Ciudad" required>
              {({ id, describedBy }) => (
                <Input id={id} value={form.city} onChange={(e) => update('city', e.target.value)} aria-describedby={describedBy} required />
              )}
            </Field>

            <Field id="store-province" label="Provincia">
              {({ id, describedBy }) => (
                <Input id={id} value={form.province} onChange={(e) => update('province', e.target.value)} aria-describedby={describedBy} />
              )}
            </Field>
          </div>

          <div className={styles.row}>
            <Field id="store-postal" label="Código postal">
              {({ id, describedBy }) => (
                <Input id={id} value={form.postal_code} onChange={(e) => update('postal_code', e.target.value)} aria-describedby={describedBy} />
              )}
            </Field>

            <Field id="store-phone" label="Teléfono">
              {({ id, describedBy }) => (
                <Input id={id} value={form.phone} onChange={(e) => update('phone', e.target.value)} aria-describedby={describedBy} />
              )}
            </Field>
          </div>

          <div className={styles.formActions}>
            <Button type="submit" disabled={saving}>
              {saving ? 'Guardando…' : 'Crear sucursal'}
            </Button>
          </div>
        </form>
      )}

      {loading ? (
        <p className={styles.muted}>Cargando sucursales…</p>
      ) : stores.length === 0 ? (
        <p className={styles.muted}>Todavía no cargaste ninguna sucursal.</p>
      ) : (
        <ul className={styles.list}>
          {stores.map((store) => (
            <li key={store.id} className={styles.card}>
              <div className={styles.cardHead}>
                <h2 className={styles.cardTitle}>{store.name}</h2>
                {!store.is_active && <span className={styles.inactive}>Inactiva</span>}
              </div>
              <p className={styles.cardLine}>
                <MapPin size={14} aria-hidden="true" />
                {[store.street, store.city, store.province].filter(Boolean).join(', ')}
              </p>
              <p className={styles.cardLine}>
                <Clock size={14} aria-hidden="true" />
                {formatHours(store.hours)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
