import { apiClient } from './api'

export async function searchProducts(q, { page = 1, per_page = 20, category, sort } = {}) {
  const params = new URLSearchParams({ page, per_page })
  if (q) params.set('q', q)
  if (category) params.set('category', category)
  if (sort) params.set('sort', sort)
  return apiClient.get(`/products?${params.toString()}`, { auth: true })
}

export async function getCategories() {
  return apiClient.get('/products/categories', { auth: true })
}

export async function getProductPrices(productId) {
  return apiClient.get(`/products/${productId}/prices`, { auth: true })
}
