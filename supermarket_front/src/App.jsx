import { useState, useEffect } from 'react'
import { HashRouter, Routes, Route } from 'react-router-dom'

import LandingPage from './pages/LandingPage'
import AuthPage from './pages/AuthPage'
import DashboardPage from './pages/app/DashboardPage'
import ListsPage from './pages/app/ListsPage'
import ListDetailPage from './pages/app/ListDetailPage'
import CheckoutPage from './pages/app/CheckoutPage'
import TrackingPage from './pages/app/TrackingPage'
import ProtectedRoute from './components/shared/ProtectedRoute'
import { AuthProvider } from './context/AuthContext'

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

  return (
    <AuthProvider>
      {isAppRoute ? (
        <HashRouter>
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route path="/app" element={<DashboardPage />} />
              <Route path="/app/lists" element={<ListsPage />} />
              <Route path="/app/lists/:id" element={<ListDetailPage />} />
              <Route path="/app/checkout" element={<CheckoutPage />} />
              <Route path="/app/orders/:id" element={<TrackingPage />} />
            </Route>
          </Routes>
        </HashRouter>
      ) : route === '#/auth' ? (
        <AuthPage />
      ) : (
        <LandingPage />
      )}
    </AuthProvider>
  )
}
