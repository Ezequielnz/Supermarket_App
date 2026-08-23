import { supabaseClient } from './supabaseClient'

const BASE_URL = import.meta.env.VITE_API_BASE_URL

// `detail` no siempre es un string: en un 422 de FastAPI es un array de
// errores de Pydantic ({loc, msg, type}). Pasarlo tal cual a `new Error()` lo
// convierte con String() y da "[object Object]" — el mensaje real de
// validación (ej. "la contraseña debe tener al menos 8 caracteres") quedaba
// oculto.
function extractErrorMessage(payload) {
  const detail = payload?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((e) => e.msg).filter(Boolean).join(' ') || null
  }
  return null
}

async function request(path, { method = 'GET', body, auth = false } = {}) {
  const headers = { 'Content-Type': 'application/json' }

  if (auth) {
    const { data } = await supabaseClient.auth.getSession()
    if (data.session) headers.Authorization = `Bearer ${data.session.access_token}`
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  const payload = await res.json().catch(() => null)

  if (!res.ok) {
    throw new Error(extractErrorMessage(payload) || 'Error de comunicación con el servidor')
  }

  return payload
}

export const apiClient = {
  get: (path, opts) => request(path, { ...opts, method: 'GET' }),
  post: (path, body, opts) => request(path, { ...opts, method: 'POST', body }),
  put: (path, body, opts) => request(path, { ...opts, method: 'PUT', body }),
  patch: (path, body, opts) => request(path, { ...opts, method: 'PATCH', body }),
  delete: (path, opts) => request(path, { ...opts, method: 'DELETE' }),
}
