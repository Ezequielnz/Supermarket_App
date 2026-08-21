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
