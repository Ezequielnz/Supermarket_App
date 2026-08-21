import { apiClient } from './api'

export async function getLists({ page = 1, per_page = 20 } = {}) {
  const params = new URLSearchParams({ page, per_page })
  return apiClient.get(`/lists?${params.toString()}`, { auth: true })
}

export async function createList({ name }) {
  return apiClient.post('/lists', { name }, { auth: true })
}

export async function getList(id) {
  return apiClient.get(`/lists/${id}`, { auth: true })
}

export async function renameList(id, { name }) {
  return apiClient.put(`/lists/${id}`, { name }, { auth: true })
}

export async function deleteList(id) {
  return apiClient.delete(`/lists/${id}`, { auth: true })
}

export async function addItem(listId, { productId, quantity, note }) {
  return apiClient.post(
    `/lists/${listId}/items`,
    { product_id: productId, quantity, note },
    { auth: true },
  )
}

export async function removeItem(listId, itemId) {
  return apiClient.delete(`/lists/${listId}/items/${itemId}`, { auth: true })
}

export async function compareList(id) {
  return apiClient.get(`/lists/${id}/compare`, { auth: true })
}
