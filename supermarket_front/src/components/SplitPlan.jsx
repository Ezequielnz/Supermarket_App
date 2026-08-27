import { ArrowRight, Check, PiggyBank, Store } from 'lucide-react'

import { formatPrice } from '../lib/money'
import styles from './SplitPlan.module.css'

// Cuántas paradas puede elegir el usuario. El backend tiene el mismo tope
// (comparison_service.MAX_SPLIT_SUPERMARKETS) y devuelve 422 fuera de rango.
const LIMIT_OPTIONS = [2, 3, 4]

export default function SplitPlan({
  plan,
  loading,
  error,
  maxSupermarkets,
  onMaxSupermarketsChange,
  onBuy,
}) {
  const groups = plan?.groups ?? []
  // Un plan incompleto no se puede confirmar: el backend rechaza un pedido al
  // que le faltan productos, así que ofrecerlo lleva a un error garantizado.
  // La cantidad de paradas no importa acá: si el plan usa una sola, la compra
  // sigue el camino del supermercado único (lo decide onBuy).
  const canBuy = Boolean(plan?.is_complete)

  return (
    <div className={styles.wrap}>
      <div className={styles.limits} role="group" aria-label="Cantidad máxima de supermercados">
        <span className={styles.limitsLabel}>Hasta</span>
        {LIMIT_OPTIONS.map((option) => (
          <button
            key={option}
            className={styles.limitBtn}
            data-active={option === maxSupermarkets ? 'true' : 'false'}
            aria-pressed={option === maxSupermarkets}
            onClick={() => onMaxSupermarketsChange(option)}
            disabled={loading}
          >
            {option} súper
          </button>
        ))}
      </div>

      {error && <p className={styles.errorText} role="alert">{error}</p>}

      {loading && !plan ? (
        <p className={styles.muted}>Armando el plan más barato…</p>
      ) : !plan ? null : groups.length === 0 ? (
        <p className={styles.muted}>
          Ningún supermercado tiene stock de estos productos todavía.
        </p>
      ) : (
        <>
          {/* Un plan de una sola parada no es una compra dividida: el tope es un
              techo, no una cuota. Se dice por qué, en vez de mostrar un plan de
              un supermercado sin explicación. */}
          {groups.length === 1 && (
            <p className={styles.muted}>
              No hace falta dividir: te conviene comprar todo en{' '}
              {groups[0].supermarket.name}.
            </p>
          )}

          <div className={styles.groups}>
            {groups.map((group, index) => (
              <div key={group.supermarket.id} className={styles.group}>
                <div className={styles.groupHead}>
                  <span className={styles.stop}>
                    <Store size={13} aria-hidden="true" /> Parada {index + 1}
                  </span>
                  <p className={styles.groupName}>{group.supermarket.name}</p>
                  <span className={styles.groupTotal}>{formatPrice(group.subtotal)}</span>
                </div>
                <ul className={styles.groupItems}>
                  {group.items.map((item) => (
                    <li key={item.product_id} className={styles.groupItem}>
                      <span>
                        {item.product_name}
                        {Number(item.quantity) !== 1 && ` × ${Number(item.quantity)}`}
                      </span>
                      <span className={styles.itemPrice}>{formatPrice(item.subtotal)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Un producto queda afuera por dos motivos: no lo vende nadie, o no
              entra en el tope de paradas. Se nombran los dos casos juntos
              porque la salida del usuario es la misma: subir el tope o sacarlo
              de la lista. */}
          {plan.missing.length > 0 && (
            <p className={styles.missing}>
              El plan no cubre: {plan.missing.map((m) => m.product_name).join(', ')}.
              Probá con más supermercados o sacalos de la lista.
            </p>
          )}

          <div className={styles.summary}>
            <div className={styles.totalRow}>
              <span>Total del plan</span>
              <strong className={styles.total}>{formatPrice(plan.total)}</strong>
            </div>
            {/* El ahorro es el número que justifica la segunda parada. Si es 0,
                se dice: mandar a alguien a dos supermercados para no ahorrar
                nada es peor que no ofrecer la opción. */}
            {plan.savings > 0 ? (
              <p className={styles.savings}>
                <PiggyBank size={15} aria-hidden="true" />
                Ahorrás {formatPrice(plan.savings)} contra comprar todo en un solo
                supermercado ({formatPrice(plan.best_single_total)}).
              </p>
            ) : plan.best_single_total !== null && groups.length > 1 ? (
              <p className={styles.noSavings}>
                Comprar todo en un solo supermercado sale lo mismo. Con una sola parada,
                conviene más.
              </p>
            ) : null}
          </div>

          <button
            className={styles.buyBtn}
            onClick={() => onBuy(plan)}
            disabled={!canBuy}
            title={
              canBuy
                ? undefined
                : 'El plan no cubre todos los productos de tu lista'
            }
          >
            {plan.is_complete && <Check size={15} aria-hidden="true" />}
            {groups.length === 1
              ? `Comprar en ${groups[0].supermarket.name}`
              : `Comprar en ${groups.length} supermercados`}
            <ArrowRight size={15} aria-hidden="true" />
          </button>
        </>
      )}
    </div>
  )
}
