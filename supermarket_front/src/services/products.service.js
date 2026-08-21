import { apiClient } from './api'

export async function searchProducts(q, { page = 1, per_page = 20 } = {}) {
  const params = new URLSearchParams({ page, per_page })
  if (q) params.set('q', q)
  return apiClient.get(`/products?${params.toString()}`, { auth: true })
}

export async function getProductPrices(productId) {
  return apiClient.get(`/products/${productId}/prices`, { auth: true })
}
