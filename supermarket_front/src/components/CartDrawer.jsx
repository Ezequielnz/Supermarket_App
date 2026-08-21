import { X, ArrowRight } from 'lucide-react'
import styles from './CartDrawer.module.css'

const PRODUCTS = [
  { id: 1, name: 'Aguacate Hass', price: 2.9, emoji: '🥑', tone: '#eaf5df' },
  { id: 2, name: 'Fresas orgánicas', price: 4.5, emoji: '🍓', tone: '#fff0ef' },
  { id: 3, name: 'Pan de masa madre', price: 5.2, emoji: '🍞', tone: '#fff6df' },
  { id: 4, name: 'Huevos camperos', price: 3.8, emoji: '🥚', tone: '#f4f2ec' },
]

export default function CartDrawer({ cart, onClose, onAdd, onRemove }) {
  const count = Object.values(cart).reduce((s, q) => s + q, 0)
  const total = Object.entries(cart).reduce((s, [id, qty]) => {
    const p = PRODUCTS.find(p => p.id === Number(id))
    return s + (p ? p.price * qty : 0)
  }, 0)

  return (
    <>
      <button className={styles.overlay} onClick={onClose} aria-label="Cerrar carrito" />
      <aside className={styles.drawer}>
        <div className={styles.drawerHead}>
          <div>
            <p className="eyebrow">Tu cesta</p>
            <h2 className={styles.drawerTitle}>Lista para ti.</h2>
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>

        <div className={styles.items}>
          {count === 0 ? (
            <div className={styles.empty}>
              <span className={styles.emptyIcon}>🛒</span>
              <p className={styles.emptyTitle}>Tu cesta está vacía</p>
              <p className={styles.emptyText}>Añade algo rico para empezar.</p>
            </div>
          ) : (
            Object.entries(cart)
              .filter(([, qty]) => qty > 0)
              .map(([id, qty]) => {
                const product = PRODUCTS.find(p => p.id === Number(id))
                if (!product) return null
                return (
                  <div key={id} className={styles.item}>
                    <span
                      className={styles.itemEmoji}
                      style={{ background: product.tone }}
                    >
                      {product.emoji}
                    </span>
                    <div className={styles.itemInfo}>
                      <p className={styles.itemName}>{product.name}</p>
                      <p className={styles.itemPrice}>
                        ${(product.price * qty).toFixed(2)}
                      </p>
                    </div>
                    <div className={styles.qtyControl}>
                      <button onClick={() => onRemove(product.id)}>−</button>
                      <span>{qty}</span>
                      <button onClick={() => onAdd(product.id)}>+</button>
                    </div>
                  </div>
                )
              })
          )}
        </div>

        <div className={styles.footer}>
          <div className={styles.subtotal}>
            <span>Subtotal</span>
            <span>${total.toFixed(2)}</span>
          </div>
          <div className={styles.totalRow}>
            <span>Total</span>
            <span>${total.toFixed(2)}</span>
          </div>
          <button
            disabled={!count}
            className={styles.checkoutBtn}
          >
            Continuar al pago <ArrowRight size={17} />
          </button>
        </div>
      </aside>
    </>
  )
}
