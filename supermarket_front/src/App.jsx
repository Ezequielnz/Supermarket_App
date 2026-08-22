import { useState, useEffect } from 'react'
import { HashRouter, Routes, Route } from 'react-router-dom'

import LandingPage from './pages/LandingPage'
import AuthPage from './pages/AuthPage'
import DashboardPage from './pages/app/DashboardPage'
import ListsPage from './pages/app/ListsPage'
import ExplorePage from './pages/app/ExplorePage'
import OrdersPage from './pages/app/OrdersPage'
import ListDetailPage from './pages/app/ListDetailPage'
import CheckoutPage from './pages/app/CheckoutPage'
import TrackingPage from './pages/app/TrackingPage'
import ProtectedRoute from './components/shared/ProtectedRoute'
import { AuthProvider } from './context/AuthContext'
import { CartProvider } from './context/CartContext'

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
        <CartProvider>
          <HashRouter>
            <Routes>
              <Route element={<ProtectedRoute />}>
                <Route path="/app" element={<DashboardPage />} />
                <Route path="/app/explore" element={<ExplorePage />} />
                <Route path="/app/lists" element={<ListsPage />} />
                <Route path="/app/lists/:id" element={<ListDetailPage />} />
                <Route path="/app/checkout" element={<CheckoutPage />} />
                <Route path="/app/orders" element={<OrdersPage />} />
                <Route path="/app/orders/:id" element={<TrackingPage />} />
              </Route>
            </Routes>
          </HashRouter>
        </CartProvider>
      ) : route === '#/auth' ? (
        <AuthPage />
      ) : (
        <LandingPage />
      )}
    </AuthProvider>
  )
}
