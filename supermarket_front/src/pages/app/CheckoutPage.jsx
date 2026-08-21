import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, ShoppingBag } from 'lucide-react'

import { createOrder } from '../../services/orders.service'
import styles from './CheckoutPage.module.css'

export default function CheckoutPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const state = location.state

  if (!state) return <Navigate to="/app/lists" replace />

  const { listId, supermarketId, supermarketName, estimatedTotal } = state

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)

    const formData = new FormData(e.target)
    const pickupLocal = formData.get('pickup_scheduled')
    const notes = formData.get('notes')

    setLoading(true)
    try {
      const order = await createOrder({
        listId,
        supermarketId,
        pickupScheduled: new Date(pickupLocal).toISOString(),
        notes: notes || null,
      })
      navigate(`/app/orders/${order.id}`, { replace: true })
    } catch (err) {
      setError(err.message || 'No se pudo crear el pedido.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <a href={`#/app/lists/${listId}`} className={styles.backLink}>
        <ArrowLeft size={16} /> Volver a la lista
      </a>
      <h1 className={styles.title}>Confirmar pedido</h1>

      <div className={styles.summary}>
        <span>Supermercado</span>
        <strong>{supermarketName}</strong>
        <span>Total estimado</span>
        <strong>${estimatedTotal?.toFixed?.(2) ?? estimatedTotal}</strong>
      </div>
      <p className={styles.note}>
        El total final se recalcula al confirmar, según el stock disponible en el momento.
      </p>

      {error && <p className={styles.errorText}>{error}</p>}

      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="pickup">Fecha y hora de retiro</label>
          <input id="pickup" name="pickup_scheduled" type="datetime-local" className={styles.input} required />
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="notes">Notas (opcional)</label>
          <textarea id="notes" name="notes" className={styles.textarea} placeholder="Ej. sin gluten, timbre 2B..." />
        </div>
        <button type="submit" className={styles.submitBtn} disabled={loading}>
          <ShoppingBag size={18} /> {loading ? 'Confirmando…' : 'Confirmar pedido'}
        </button>
      </form>
    </div>
  )
}
