import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeft, PiggyBank, ShoppingBag, Store } from 'lucide-react'

import { formatPrice } from '../../lib/money'
import { createOrder, createSplitOrder } from '../../services/orders.service'
import styles from './CheckoutPage.module.css'

// La pantalla confirma dos compras distintas con el mismo formulario: todo en
// un supermercado, o el plan repartido entre varios. Lo unico que cambia es el
// resumen de arriba y a que endpoint se manda: la fecha de retiro y las notas
// son las mismas preguntas. Que llega en location.state lo decide
// ListDetailPage: `groups` para el plan dividido, `supermarketId` para el unico.

export default function CheckoutPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const state = location.state

  if (!state) return <Navigate to="/app/lists" replace />

  const { listId, supermarketName, estimatedTotal, groups, savings } = state
  const isSplit = Array.isArray(groups) && groups.length > 1

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)

    const formData = new FormData(e.target)
    const pickupLocal = formData.get('pickup_scheduled')
    const notes = formData.get('notes')

    setLoading(true)
    try {
      if (isSplit) {
        // Un pedido por supermercado, en una sola transaccion del lado del
        // backend. No hay un pedido para "ver": se cae en la lista, que es
        // donde estan los N que se acaban de crear.
        await createSplitOrder({
          listId,
          pickupScheduled: new Date(pickupLocal).toISOString(),
          notes: notes || null,
          groups,
        })
        navigate('/app/orders', { replace: true })
        return
      }

      const order = await createOrder({
        listId,
        supermarketId: state.supermarketId,
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
      <h1 className={styles.title}>
        {isSplit ? `Confirmar compra en ${groups.length} supermercados` : 'Confirmar pedido'}
      </h1>

      {isSplit ? (
        <>
          <div className={styles.stops}>
            {groups.map((group, index) => (
              <div key={group.supermarketId} className={styles.stop}>
                <span className={styles.stopBadge}>
                  <Store size={13} aria-hidden="true" /> Parada {index + 1}
                </span>
                <span className={styles.stopName}>{group.supermarketName}</span>
                <span className={styles.stopMeta}>
                  {group.productIds.length} producto{group.productIds.length === 1 ? '' : 's'}
                </span>
                <strong className={styles.stopTotal}>{formatPrice(group.subtotal)}</strong>
              </div>
            ))}
          </div>

          <div className={styles.summary}>
            <span>Total estimado</span>
            <strong>{formatPrice(estimatedTotal)}</strong>
          </div>

          {savings > 0 && (
            <p className={styles.savings}>
              <PiggyBank size={15} aria-hidden="true" /> Ahorrás {formatPrice(savings)} contra
              comprar todo en un solo supermercado.
            </p>
          )}

          <p className={styles.note}>
            Se crea un pedido por supermercado, todos para la misma fecha de retiro. Cada uno
            se sigue por separado desde Mis pedidos. El total final se recalcula al confirmar,
            según el stock disponible en el momento.
          </p>
        </>
      ) : (
        <>
          <div className={styles.summary}>
            <span>Supermercado</span>
            <strong>{supermarketName}</strong>
            <span>Total estimado</span>
            <strong>{formatPrice(estimatedTotal)}</strong>
          </div>
          <p className={styles.note}>
            El total final se recalcula al confirmar, según el stock disponible en el momento.
          </p>
        </>
      )}

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
          <ShoppingBag size={18} />
          {loading
            ? 'Confirmando…'
            : isSplit
              ? `Confirmar ${groups.length} pedidos`
              : 'Confirmar pedido'}
        </button>
      </form>
    </div>
  )
}
