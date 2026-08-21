import { Navigate, Outlet } from 'react-router-dom'

import { useAdminAuth } from '../../hooks/useAdminAuth'

// Solo una cadena aprobada entra al panel. El resto de los estados
// (pending_review, rejected, suspended) van a /pending, que explica que pasa y
// que hacer. Espeja la validacion del backend en require_approved_chain: aca es
// navegacion, alla es autorizacion.
export default function ApprovedRoute() {
  const { chain, loading } = useAdminAuth()

  if (loading) return <p>Cargando…</p>
  if (!chain) return <Navigate to="/auth" replace />
  if (chain.status !== 'approved') return <Navigate to="/pending" replace />

  return <Outlet />
}
