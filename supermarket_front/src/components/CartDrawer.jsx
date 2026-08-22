import { useState } from 'react'
import { X, BarChart2, Bookmark, Trash2 } from 'lucide-react'

import { useCart } from '../hooks/useCart'
import { formatPrice } from '../lib/money'
import styles from './CartDrawer.module.css'

// El boton principal es "Comparar precios", no "Pagar": el carrito NO esta
// atado a un supermercado (docs/PLAN_CATALOGO_Y_CARRITO.md §2.2). Lleva al
// comparador de su propia lista, que es el camino que ya existe hasta el
// checkout y el pedido.

export default function CartDrawer({ onClose }) {
  const { cart, items, count, loading, error, setQuantity, removeItem, saveAsList } = useCart()
  const [busyId, setBusyId] = useState(null)
  const [saving, setSaving] = useState(false)
  const [localError, setLocalError] = useState(null)

  // Suma de los mejores precios. Es un ESTIMADO: cada producto puede estar mas
  // barato en un super distinto, y el total real depende de cual se elija. Un
  // total en firme aca seria mentira.
  const estimate = items.reduce(
    (sum, item) => sum + (item.best_price ?? 0) * Number(item.quantity),
    0,
  )
  const hasUnpriced = items.some((item) => item.best_price === null)

  async function changeQuantity(item, next) {
    if (next < 1) return
    setBusyId(item.id)
    setLocalError(null)
    try {
      await setQuantity(item.id, next)
    } catch (err) {
      setLocalError(err.message || 'No pudimos actualizar la cantidad.')
    } finally {
      setBusyId(null)
    }
  }

  async function handleRemove(item) {
    setBusyId(item.id)
    setLocalError(null)
    try {
      await removeItem(item.id)
    } catch (err) {
      setLocalError(err.message || 'No pudimos quitar el producto.')
    } finally {
      setBusyId(null)
    }
  }

  async function handleSave() {
    setSaving(true)
    setLocalError(null)
    try {
      await saveAsList()
      onClose()
      window.location.hash = '#/app/lists'
    } catch (err) {
      setLocalError(err.message || 'No pudimos guardar el carrito como lista.')
    } finally {
      setSaving(false)
    }
  }

  function goCompare() {
    if (!cart) return
    onClose()
    window.location.hash = `#/app/lists/${cart.id}`
  }

  return (
    <>
      <button className={styles.overlay} onClick={onClose} aria-label="Cerrar carrito" />
      <aside className={styles.drawer} aria-label="Carrito">
        <div className={styles.drawerHead}>
          <div>
            <p className="eyebrow">Tu carrito</p>
            <h2 className={styles.drawerTitle}>
              {count === 0 ? 'Vacío por ahora.' : `${count} producto${count === 1 ? '' : 's'}`}
            </h2>
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Cerrar">
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {(error || localError) && (
          <p className={styles.error} role="alert">{localError || error}</p>
        )}

        <div className={styles.items}>
          {loading && items.length === 0 ? (
            <p className={styles.emptyText}>Cargando…</p>
          ) : count === 0 ? (
            <div className={styles.empty}>
              <span className={styles.emptyIcon} aria-hidden="true">🛒</span>
              <p className={styles.emptyTitle}>Tu carrito está vacío</p>
              <p className={styles.emptyText}>
                Buscá productos en Explorar y agregalos para comparar precios.
              </p>
            </div>
          ) : (
            items.map((item) => (
              <div key={item.id} className={styles.item}>
                <div className={styles.itemInfo}>
                  <p className={styles.itemName}>{item.product_name}</p>
                  <p className={styles.itemPrice}>
                    {item.best_price === null
                      ? 'Sin precio disponible'
                      : `desde ${formatPrice(item.best_price * Number(item.quantity))}`}
                  </p>
                </div>

                <div className={styles.qtyControl}>
                  <button
                    onClick={() => changeQuantity(item, Number(item.quantity) - 1)}
                    disabled={busyId === item.id || Number(item.quantity) <= 1}
                    aria-label={`Quitar una unidad de ${item.product_name}`}
                  >
                    −
                  </button>
                  <span>{Number(item.quantity)}</span>
                  <button
                    onClick={() => changeQuantity(item, Number(item.quantity) + 1)}
                    disabled={busyId === item.id}
                    aria-label={`Agregar una unidad de ${item.product_name}`}
                  >
                    +
                  </button>
                </div>

                <button
                  className={styles.removeBtn}
                  onClick={() => handleRemove(item)}
                  disabled={busyId === item.id}
                  aria-label={`Quitar ${item.product_name} del carrito`}
                >
                  <Trash2 size={15} aria-hidden="true" />
                </button>
              </div>
            ))
          )}
        </div>

        <div className={styles.footer}>
          <div className={styles.totalRow}>
            <span>Estimado desde</span>
            <span>{formatPrice(estimate)}</span>
          </div>
          <p className={styles.disclaimer}>
            Es la suma del precio más barato de cada producto, que puede estar en
            supermercados distintos. El total real lo ves al comparar y elegir dónde comprar.
            {hasUnpriced && ' Hay productos sin precio disponible que no están sumados.'}
          </p>

          <button
            disabled={!count}
            className={styles.checkoutBtn}
            onClick={goCompare}
          >
            <BarChart2 size={17} aria-hidden="true" /> Comparar precios
          </button>

          <button
            disabled={!count || saving}
            className={styles.saveBtn}
            onClick={handleSave}
          >
            <Bookmark size={16} aria-hidden="true" />
            {saving ? 'Guardando…' : 'Guardar como lista'}
          </button>
        </div>
      </aside>
    </>
  )
}
