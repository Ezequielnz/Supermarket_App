import { useState, useEffect } from 'react'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'

import LandingPage from './pages/LandingPage'
import AuthPage from './pages/AuthPage'
import RegisterPage from './pages/RegisterPage'
import PendingReviewPage from './pages/PendingReviewPage'
import AppLayout from './pages/app/AppLayout'
import ProfilePage from './pages/app/ProfilePage'
import StoresPage from './pages/app/StoresPage'
import TeamPage from './pages/app/TeamPage'
import ProtectedRoute from './components/shared/ProtectedRoute'
import ApprovedRoute from './components/shared/ApprovedRoute'
import { AdminAuthProvider } from './context/AdminAuthContext'

// Mismo patrón que supermarket_front: hash-routing simple para las páginas
// públicas y react-router para las rutas de /app (docs/NORMAS.md §3.7).
function getRoute() {
  return window.location.hash || '#/'
}

export default function App() {
  const [route, setRoute] = useState(getRoute)

  useEffect(() => {
    const handler = () => setRoute(getRoute())
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])

  const isAppRoute = route.startsWith('#/app')
  const isPending = route.startsWith('#/pending')

  return (
    <AdminAuthProvider>
      {isAppRoute ? (
        <HashRouter>
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route element={<ApprovedRoute />}>
                <Route element={<AppLayout />}>
                  <Route path="/app" element={<Navigate to="/app/profile" replace />} />
                  <Route path="/app/profile" element={<ProfilePage />} />
                  <Route path="/app/stores" element={<StoresPage />} />
                  <Route path="/app/team" element={<TeamPage />} />
                </Route>
              </Route>
            </Route>
          </Routes>
        </HashRouter>
      ) : isPending ? (
        <PendingReviewPage />
      ) : route.startsWith('#/register') ? (
        <RegisterPage />
      ) : route.startsWith('#/auth') ? (
        <AuthPage />
      ) : (
        <LandingPage />
      )}
    </AdminAuthProvider>
  )
}
