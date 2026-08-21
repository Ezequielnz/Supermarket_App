import { useEffect, useState, useCallback } from 'react'
import { UserPlus } from 'lucide-react'

import Button from '../../components/ui/Button'
import Field from '../../components/ui/Field'
import Input from '../../components/ui/Input'
import TopBar from '../../components/TopBar'
import { getMyStaff, inviteStaff } from '../../services/supermarket.service'
import styles from './TeamPage.module.css'

const ROLE_LABELS = {
  owner: 'Responsable',
  manager: 'Encargado',
  staff: 'Empleado',
}

const EMPTY_INVITE = { email: '', full_name: '', role: 'staff' }

export default function TeamPage() {
  const [staff, setStaff] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_INVITE)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await getMyStaff()
      setStaff(result.data)
      setError(null)
    } catch (err) {
      setError(err.message || 'No pudimos cargar tu equipo.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

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
      await inviteStaff({ email: form.email, full_name: form.full_name, role: form.role })
      setForm(EMPTY_INVITE)
      setShowForm(false)
      setMessage(`Le enviamos la invitación a ${form.email}.`)
      await load()
    } catch (err) {
      setError(err.message || 'No pudimos enviar la invitación.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <TopBar
        title="Equipo"
        description="Invitá a las personas que van a gestionar los pedidos de tu supermercado."
        actions={
          <Button onClick={() => setShowForm((v) => !v)}>
            <UserPlus size={16} aria-hidden="true" />
            {showForm ? 'Cancelar' : 'Invitar'}
          </Button>
        }
      />

      {message && <p className={styles.success} role="status">{message}</p>}
      {error && <p className={styles.error} role="alert">{error}</p>}

      {showForm && (
        <form className={styles.form} onSubmit={handleSubmit} noValidate>
          <h2 className={styles.formTitle}>Invitar a alguien</h2>
          <p className={styles.hint}>
            Le mandamos un correo para que defina su propia contraseña. Vos nunca la vas a conocer.
          </p>

          <Field id="invite-name" label="Nombre y apellido" required>
            {({ id, describedBy }) => (
              <Input id={id} value={form.full_name} onChange={(e) => update('full_name', e.target.value)} aria-describedby={describedBy} required />
            )}
          </Field>

          <Field id="invite-email" label="Correo electrónico" required>
            {({ id, describedBy }) => (
              <Input id={id} type="email" value={form.email} onChange={(e) => update('email', e.target.value)} aria-describedby={describedBy} required />
            )}
          </Field>

          <Field id="invite-role" label="Rol" hint="El encargado puede gestionar sucursales y precios; el empleado solo opera pedidos." required>
            {({ id, describedBy }) => (
              <select
                id={id}
                className={styles.select}
                value={form.role}
                onChange={(e) => update('role', e.target.value)}
                aria-describedby={describedBy}
              >
                <option value="staff">Empleado</option>
                <option value="manager">Encargado</option>
              </select>
            )}
          </Field>

          <div className={styles.formActions}>
            <Button type="submit" disabled={saving}>
              {saving ? 'Enviando…' : 'Enviar invitación'}
            </Button>
          </div>
        </form>
      )}

      {loading ? (
        <p className={styles.muted}>Cargando equipo…</p>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <caption className={styles.srOnly}>Integrantes del equipo de la cadena</caption>
            <thead>
              <tr>
                <th scope="col">Nombre</th>
                <th scope="col">Rol</th>
                <th scope="col">Estado</th>
              </tr>
            </thead>
            <tbody>
              {staff.map((person) => (
                <tr key={person.id}>
                  <td>{person.full_name}</td>
                  <td>{ROLE_LABELS[person.role] ?? person.role}</td>
                  <td>{person.is_active ? 'Activo' : 'Inactivo'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
