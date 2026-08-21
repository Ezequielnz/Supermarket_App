import { apiClient } from './api'
import { supabaseClient } from './supabaseClient'

// Registro: pasa por el backend porque además de crear el usuario en Supabase
// Auth hay que crear su fila en `profiles` (requiere service_role_key, que
// nunca se expone al frontend).
export async function registerConsumer({ email, password, fullName, phone }) {
  return apiClient.post('/auth/register', {
    email,
    password,
    full_name: fullName,
    phone,
  })
}

// Login/logout/refresh: excepción explícita de docs/NORMAS.md sección 2, van
// directo contra el SDK de Supabase, sin pasar por el backend.
export async function loginConsumer({ email, password }) {
  const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password })
  if (error) throw error
  return data.session
}

export async function logout() {
  const { error } = await supabaseClient.auth.signOut()
  if (error) throw error
}

export async function getSession() {
  const { data } = await supabaseClient.auth.getSession()
  return data.session
}

export function onAuthStateChange(callback) {
  return supabaseClient.auth.onAuthStateChange(callback)
}
