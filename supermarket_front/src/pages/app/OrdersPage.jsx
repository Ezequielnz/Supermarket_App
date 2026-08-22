import { ChevronRight } from 'lucide-react'

import AppNav from '../../components/AppNav'
import { useOrders } from '../../hooks/useOrders'
import { formatPrice } from '../../lib/money'
import styles from './OrdersPage.module.css'

// Mismo vocabulario que el enum order_status de la migracion 008 y que
// TrackingPage: un pedido no puede llamarse distinto en dos pantallas.
const STATUS_LABELS = {
  pending: 'Pendiente',
  confirmed: 'Confirmado',
  preparing: 'Preparando',
  ready: 'Listo para retirar',
  completed: 'Completado',
  cancelled: 'Cancelado',
}

const dateFormatter = new Intl.DateTimeFormat('es-AR', {
  day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
})

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : dateFormatter.format(date)
}

export default function OrdersPage() {
  const { orders, loading, error } = useOrders()

  return (
    <div className={styles.page}>
      <AppNav />

      <header className={styles.header}>
        <h1 className={styles.title}>Mis pedidos</h1>
        <p className={styles.subtitle}>
          Los pedidos que hiciste, del más reciente al más viejo.
        </p>
      </header>

      {error && <p className={styles.error} role="alert">{error}</p>}

      {loading ? (
        <p className={styles.muted}>Cargando pedidos…</p>
      ) : orders.length === 0 ? (
        <p className={styles.muted}>
          Todavía no hiciste ningún pedido. Armá tu carrito en{' '}
          <a href="#/app/explore" className={styles.inlineLink}>Explorar</a>, compará precios y
          elegí dónde comprar.
        </p>
      ) : (
        <ul className={styles.list}>
          {orders.map((order) => (
            <li key={order.id}>
              <a href={`#/app/orders/${order.id}`} className={styles.card}>
                <span className={styles.cardMain}>
                  <span className={styles.status} data-status={order.status}>
                    {STATUS_LABELS[order.status] ?? order.status}
                  </span>
                  <span className={styles.pickup}>
                    Retiro: {formatDate(order.pickup_scheduled)}
                  </span>
                </span>

                <span className={styles.cardRight}>
                  <span className={styles.total}>
                    {order.total_price === null ? 'A confirmar' : formatPrice(order.total_price)}
                  </span>
                  <ChevronRight size={18} aria-hidden="true" />
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
