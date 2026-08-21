import { createContext, useState, useEffect, useCallback } from 'react'

import * as authService from '../services/auth.service'
import { getMyChain } from '../services/supermarket.service'

export const AdminAuthContext = createContext(null)

export function AdminAuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [profileError, setProfileError] = useState(null)

  // El estado de la cadena (pending_review / approved / rejected / suspended)
  // decide a que pantalla entra el usuario, asi que se carga apenas hay sesion
  // y se refresca despues de cada cambio de perfil.
  const loadProfile = useCallback(async () => {
    try {
      const data = await getMyChain()
      setProfile(data)
      setProfileError(null)
      return data
    } catch (err) {
      // Una cuenta de consumidor que intenta entrar al panel recibe 403 aca.
      setProfile(null)
      setProfileError(err.message)
      return null
    }
  }, [])

  useEffect(() => {
    let active = true

    authService.getSession().then(async (s) => {
      if (!active) return
      setSession(s)
      if (s) await loadProfile()
      setLoading(false)
    })

    const { data: subscription } = authService.onAuthStateChange((_event, s) => {
      setSession(s)
      if (!s) {
        setProfile(null)
        setProfileError(null)
      }
    })

    return () => {
      active = false
      subscription.subscription.unsubscribe()
    }
  }, [loadProfile])

  async function login({ email, password }) {
    const newSession = await authService.loginStaff({ email, password })
    setSession(newSession)
    const loaded = await loadProfile()
    if (!loaded) {
      // Sesion valida pero la cuenta no pertenece a ningun supermercado: se
      // cierra la sesion para no dejar al usuario en un limbo sin panel.
      await authService.logout()
      setSession(null)
      throw new Error('Esta cuenta no pertenece a ningun supermercado.')
    }
    return loaded
  }

  async function logout() {
    await authService.logout()
    setSession(null)
    setProfile(null)
  }

  const value = {
    session,
    user: session?.user ?? null,
    chain: profile?.chain ?? null,
    role: profile?.role ?? null,
    storesCount: profile?.stores_count ?? 0,
    loading,
    profileError,
    login,
    logout,
    refreshProfile: loadProfile,
  }

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>
}
