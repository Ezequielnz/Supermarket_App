import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ArrowLeft, PackageCheck, X } from 'lucide-react'

import { getOrder, getOrderStatus, cancelOrder } from '../../services/orders.service'
import styles from './TrackingPage.module.css'

const STATUS_LABELS = {
  pending: 'Pendiente',
  confirmed: 'Confirmado',
  preparing: 'Preparando',
  ready: 'Listo para retirar',
  completed: 'Completado',
  cancelled: 'Cancelado',
}

const TERMINAL_STATUSES = ['completed', 'cancelled']
const POLL_INTERVAL_MS = 5000

export default function TrackingPage() {
  const { id } = useParams()
  const [order, setOrder] = useState(null)
  const [error, setError] = useState(null)
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    getOrder(id).then(setOrder).catch((err) => setError(err.message || 'No se pudo cargar el pedido.'))
  }, [id])

  useEffect(() => {
    if (!order || TERMINAL_STATUSES.includes(order.status)) return

    const interval = setInterval(() => {
      getOrderStatus(id)
        .then((status) => setOrder((prev) => (prev ? { ...prev, ...status } : prev)))
        .catch(() => {})
    }, POLL_INTERVAL_MS)

    return () => clearInterval(interval)
  }, [id, order])

  async function handleCancel() {
    if (!window.confirm('¿Cancelar este pedido?')) return
    setCancelling(true)
    try {
      const updated = await cancelOrder(id)
      setOrder((prev) => ({ ...prev, ...updated }))
    } catch (err) {
      setError(err.message || 'No se pudo cancelar el pedido.')
    } finally {
      setCancelling(false)
    }
  }

  if (error) return <p className={styles.errorText}>{error}</p>
  if (!order) return <p className={styles.muted}>Cargando…</p>

  const isTerminal = TERMINAL_STATUSES.includes(order.status)

  return (
    <div className={styles.page}>
      <a href="#/app" className={styles.backLink}>
        <ArrowLeft size={16} /> Volver al panel
      </a>
      <h1 className={styles.title}>Pedido en {order.supermarket.name}</h1>

      <div className={styles.statusBadge} data-status={order.status}>
        <PackageCheck size={18} />
        {STATUS_LABELS[order.status] || order.status}
      </div>

      <div className={styles.summary}>
        <span>Retiro programado</span>
        <strong>{new Date(order.pickup_scheduled).toLocaleString()}</strong>
        <span>Total</span>
        <strong>${order.total_price?.toFixed?.(2) ?? order.total_price}</strong>
      </div>

      <div className={styles.items}>
        {order.items.map((item) => (
          <div key={item.product_id} className={styles.item}>
            <span>{item.product_name} x{item.quantity}</span>
            <span>${item.subtotal.toFixed(2)}</span>
          </div>
        ))}
      </div>

      {!isTerminal && (
        <button className={styles.cancelBtn} onClick={handleCancel} disabled={cancelling}>
          <X size={16} /> {cancelling ? 'Cancelando…' : 'Cancelar pedido'}
        </button>
      )}
    </div>
  )
}
