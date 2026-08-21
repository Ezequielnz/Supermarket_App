import { createContext, useState, useEffect } from 'react'

import * as authService from '../services/auth.service'

export const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    authService.getSession().then((s) => {
      setSession(s)
      setLoading(false)
    })

    const { data: subscription } = authService.onAuthStateChange((_event, s) => {
      setSession(s)
    })

    return () => subscription.subscription.unsubscribe()
  }, [])

  async function login({ email, password }) {
    const newSession = await authService.loginConsumer({ email, password })
    setSession(newSession)
  }

  async function register({ email, password, fullName, phone }) {
    await authService.registerConsumer({ email, password, fullName, phone })
    // Auto-login: el backend nunca emite tokens de sesión, así que tras crear
    // la cuenta se inicia sesión con las mismas credenciales.
    await login({ email, password })
  }

  async function logout() {
    await authService.logout()
    setSession(null)
  }

  const value = { user: session?.user ?? null, session, loading, login, register, logout }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
