import { Navigate, Outlet } from 'react-router-dom'

import { useAdminAuth } from '../../hooks/useAdminAuth'

export default function ProtectedRoute() {
  const { session, loading } = useAdminAuth()

  if (loading) return <p>Cargando…</p>
  if (!session) return <Navigate to="/auth" replace />

  return <Outlet />
}
