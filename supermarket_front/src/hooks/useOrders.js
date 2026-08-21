import { useCallback, useEffect, useState } from 'react'

import * as ordersService from '../services/orders.service'

export function useOrders() {
  const [orders, setOrders] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refetch = useCallback(() => {
    setLoading(true)
    setError(null)
    return ordersService
      .getOrders()
      .then((res) => {
        setOrders(res.data)
        setTotal(res.total)
      })
      .catch((err) => setError(err.message || 'No se pudieron cargar los pedidos.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    refetch()
  }, [refetch])

  return { orders, total, loading, error, refetch }
}
