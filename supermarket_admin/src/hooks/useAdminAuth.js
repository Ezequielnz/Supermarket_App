import { useContext } from 'react'

import { AdminAuthContext } from '../context/AdminAuthContext'

export function useAdminAuth() {
  const context = useContext(AdminAuthContext)
  if (!context) {
    throw new Error('useAdminAuth debe usarse dentro de un AdminAuthProvider')
  }
  return context
}
