// Unidades en góndola: cómo se muestran y cómo se leen de un input.
//
// El stock no es dinero y por eso no vive en money.js: viaja como número con
// hasta dos decimales (`supermarket_products.stock_quantity` es NUMERIC(10,2)),
// porque hay productos que se venden por peso — 2,5 kg de asado es un stock
// válido.
//
// Los tres estados que hay que distinguir, y que son la razón de este archivo:
//
//   null -> la sucursal no cuenta unidades de ese producto (granel). Se rige
//           solo por el switch de disponible.
//   0    -> no queda ninguno. La base lo saca de la venta sola.
//   n    -> quedan n.
//
// Confundir el primero con el segundo saca de la góndola a toda la verdulería.

const MAX_STOCK = 99999999.99

// Número → texto para mostrar. `null` no es cero: es "no se cuenta".
export function formatStock(quantity) {
  if (quantity === null || quantity === undefined) return 'Sin control'
  return new Intl.NumberFormat('es-AR', { maximumFractionDigits: 2 }).format(quantity)
}

// Número → texto para precargar un input de edición.
export function stockToInput(quantity) {
  if (quantity === null || quantity === undefined) return ''
  return String(quantity)
}

// Lo que el usuario escribió → número, `null` si dejó el campo vacío (deja de
// contar unidades), o `undefined` si lo que escribió no es una cantidad.
// Acepta la coma decimal, que es como se escribe acá.
export function inputToStock(value) {
  const normalized = String(value).trim().replace(',', '.')
  if (!normalized) return null

  const quantity = Number(normalized)
  if (!Number.isFinite(quantity) || quantity < 0 || quantity > MAX_STOCK) return undefined
  return Math.round(quantity * 100) / 100
}
