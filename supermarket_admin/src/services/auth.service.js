import { supabaseClient } from './supabaseClient'

// Login/logout/refresh van directo contra el SDK de Supabase, sin pasar por el
// backend: es la excepcion explicita de docs/NORMAS.md seccion 2.
export async function loginStaff({ email, password }) {
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
