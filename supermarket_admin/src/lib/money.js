// Conversión entre lo que se muestra (pesos) y lo que viaja (centavos).
//
// `supermarket_products.price` es INTEGER en CENTAVOS (NORMAS.md §4.3): el
// dinero nunca es float, ni en la base ni en la API. Pero nadie carga un
// precio en centavos: el panel pide y muestra pesos, y la conversión vive
// SOLO acá para que no aparezcan dos criterios distintos en dos pantallas.
//
// Vive en lib/ y no en services/ porque no habla con la API: es formato, no
// transporte, y lo usan componentes que no comparten servicio.

const CENTS_PER_UNIT = 100

const formatter = new Intl.NumberFormat('es-AR', {
  style: 'currency',
  currency: 'ARS',
  minimumFractionDigits: 2,
})

// Centavos → "$1.250,00". Para mostrar.
export function formatPrice(cents) {
  if (cents === null || cents === undefined) return '—'
  return formatter.format(cents / CENTS_PER_UNIT)
}

// Centavos → "1250.00". Para precargar un input de edición.
export function centsToInput(cents) {
  if (cents === null || cents === undefined) return ''
  return (cents / CENTS_PER_UNIT).toFixed(2)
}

// Lo que el usuario escribió → centavos, o null si no es un número válido.
// Acepta la coma decimal, que es como se escribe un precio en Argentina.
// Math.round evita que 19.99 * 100 dé 1998.9999999999998.
export function inputToCents(value) {
  const normalized = String(value).trim().replace(',', '.')
  if (!normalized) return null
  const amount = Number(normalized)
  if (!Number.isFinite(amount) || amount <= 0) return null
  return Math.round(amount * CENTS_PER_UNIT)
}
