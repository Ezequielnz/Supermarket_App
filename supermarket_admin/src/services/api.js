import { supabaseClient } from './supabaseClient'

const BASE_URL = import.meta.env.VITE_API_BASE_URL

// `detail` no siempre es un string: en un 422 de FastAPI es un array de
// errores de Pydantic ({loc, msg, type}). Pasarlo tal cual a `new Error()` lo
// convierte con String() y da "[object Object]" — el mensaje real de
// validación (ej. "el EAN debe tener entre 8 y 14 dígitos") quedaba oculto.
function extractErrorMessage(payload) {
  const detail = payload?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((e) => e.msg).filter(Boolean).join(' ') || null
  }
  return null
}

async function authHeaders(auth) {
  if (!auth) return {}
  const { data } = await supabaseClient.auth.getSession()
  return data.session ? { Authorization: `Bearer ${data.session.access_token}` } : {}
}

async function unwrap(res) {
  const payload = await res.json().catch(() => null)

  if (!res.ok) {
    throw new Error(extractErrorMessage(payload) || 'Error de comunicación con el servidor')
  }

  return payload
}

async function request(path, { method = 'GET', body, auth = false } = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...(await authHeaders(auth)) },
    body: body ? JSON.stringify(body) : undefined,
  })

  return unwrap(res)
}

// Subida de archivos (el importador de catálogo). Va por separado y no con un
// flag en `request` porque la diferencia no es el cuerpo sino la CABECERA: el
// Content-Type de un multipart incluye un `boundary` que genera el navegador.
// Ponerlo a mano —o dejar el 'application/json' de arriba— hace que el backend
// no encuentre las partes y responda 422 sin decir por qué.
async function upload(path, formData, { auth = false } = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: await authHeaders(auth),
    body: formData,
  })

  return unwrap(res)
}

export const apiClient = {
  get: (path, opts) => request(path, { ...opts, method: 'GET' }),
  post: (path, body, opts) => request(path, { ...opts, method: 'POST', body }),
  put: (path, body, opts) => request(path, { ...opts, method: 'PUT', body }),
  patch: (path, body, opts) => request(path, { ...opts, method: 'PATCH', body }),
  delete: (path, opts) => request(path, { ...opts, method: 'DELETE' }),
  upload: (path, formData, opts) => upload(path, formData, opts),
}
