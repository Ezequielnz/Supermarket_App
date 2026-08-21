import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'

export default function ProtectedRoute() {
  const { session, loading } = useAuth()

  if (loading) return <p>Cargando…</p>
  if (!session) return <Navigate to="/auth" replace />

  return <Outlet />
}
