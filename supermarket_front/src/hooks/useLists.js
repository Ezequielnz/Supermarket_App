import { useCallback, useEffect, useState } from 'react'

import * as listsService from '../services/lists.service'

export function useLists() {
  const [lists, setLists] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const refetch = useCallback(() => {
    setLoading(true)
    setError(null)
    return listsService
      .getLists()
      .then((res) => {
        setLists(res.data)
        setTotal(res.total)
      })
      .catch((err) => setError(err.message || 'No se pudieron cargar las listas.'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    refetch()
  }, [refetch])

  async function createList(name) {
    const created = await listsService.createList({ name })
    await refetch()
    return created
  }

  async function deleteList(id) {
    await listsService.deleteList(id)
    await refetch()
  }

  return { lists, total, loading, error, refetch, createList, deleteList }
}
