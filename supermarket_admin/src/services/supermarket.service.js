import { apiClient } from './api'

// El registro pasa por el backend: crea el usuario en Supabase Auth y la cadena
// en una sola operacion, con la service_role_key que nunca se expone al front.
export async function registerSupermarket(payload) {
  return apiClient.post('/supermarkets/register', payload)
}

export async function getMyChain() {
  return apiClient.get('/supermarkets/me', { auth: true })
}

export async function updateMyChain(payload) {
  return apiClient.patch('/supermarkets/me', payload, { auth: true })
}

export async function getMyStores() {
  return apiClient.get('/supermarkets/me/stores', { auth: true })
}

export async function createStore(payload) {
  return apiClient.post('/supermarkets/me/stores', payload, { auth: true })
}

export async function updateStore(storeId, payload) {
  return apiClient.patch(`/supermarkets/me/stores/${storeId}`, payload, { auth: true })
}

export async function getMyStaff() {
  return apiClient.get('/supermarkets/me/users', { auth: true })
}

export async function inviteStaff(payload) {
  return apiClient.post('/supermarkets/me/users', payload, { auth: true })
}
