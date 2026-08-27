import { apiClient } from './api'

export async function createOrder({ listId, supermarketId, pickupScheduled, notes }) {
  return apiClient.post(
    '/orders',
    {
      list_id: listId,
      supermarket_id: supermarketId,
      pickup_scheduled: pickupScheduled,
      notes,
    },
    { auth: true },
  )
}

export async function getOrders({ page = 1, per_page = 20 } = {}) {
  const params = new URLSearchParams({ page, per_page })
  return apiClient.get(`/orders?${params.toString()}`, { auth: true })
}

export async function getOrder(id) {
  return apiClient.get(`/orders/${id}`, { auth: true })
}

export async function getOrderStatus(id) {
  return apiClient.get(`/orders/${id}/status`, { auth: true })
}

export async function cancelOrder(id, { reason } = {}) {
  return apiClient.post(`/orders/${id}/cancel`, { reason }, { auth: true })
}

// Confirma un plan de compra dividida: el backend crea un pedido por
// supermercado, todos en la misma transacción. `groups` viaja sin precios: el
// total lo recalcula el backend contra los precios de hoy.
export async function createSplitOrder({ listId, pickupScheduled, notes, groups }) {
  return apiClient.post(
    '/orders/split',
    {
      list_id: listId,
      pickup_scheduled: pickupScheduled,
      notes,
      groups: groups.map((group) => ({
        supermarket_id: group.supermarketId,
        product_ids: group.productIds,
      })),
    },
    { auth: true },
  )
}
