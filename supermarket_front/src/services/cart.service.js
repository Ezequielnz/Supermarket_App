import { apiClient } from './api'

// El carrito ES una lista de compras con is_cart = true, no un recurso aparte.
// Por eso todo lo que sigue son atajos sobre /lists: el camino al comparador y
// al checkout es el mismo que el de una lista guardada.

// Devuelve el carrito activo con sus items. Lo crea vacío si no existe: el
// consumidor nunca tiene que crear un carrito a mano.
export async function getCart() {
  return apiClient.get('/lists/cart', { auth: true })
}

export async function addToCart({ productId, quantity = 1, note = null }) {
  return apiClient.post(
    '/lists/cart/items',
    { product_id: productId, quantity, note },
    { auth: true },
  )
}

// Convierte el carrito en lista guardada. El próximo producto abre uno nuevo.
export async function saveCartAsList({ name } = {}) {
  return apiClient.post('/lists/cart/save', { name: name ?? null }, { auth: true })
}

// Fija la cantidad (no la suma): es el control − / + del drawer.
export async function setItemQuantity(listId, itemId, quantity) {
  return apiClient.patch(
    `/lists/${listId}/items/${itemId}`,
    { quantity },
    { auth: true },
  )
}

export async function removeCartItem(listId, itemId) {
  return apiClient.delete(`/lists/${listId}/items/${itemId}`, { auth: true })
}
