import { useCallback, useEffect, useRef, useState } from 'react'

import { compareList } from '../services/lists.service'

// Cuánto vale un resultado antes de volver a pedirlo. La comparación ya no la
// dispara el usuario apretando un botón: se dispara sola al abrir la lista, así
// que ir y volver entre "Mis listas" y una lista dejaría de ser gratis sin esta
// caché.
const CACHE_TTL_MS = 5 * 60 * 1000

// listId -> { payload, at }. Vive en el módulo, no en localStorage: los precios
// los mueve el supermercado del lado del servidor, y un total viejo que
// sobrevive días es peor que un spinner. Con el Map, la caché muere al recargar
// la página, que es el horizonte en el que un precio sigue siendo creíble.
const cache = new Map()

export function invalidateCompare(listId) {
  cache.delete(listId)
}

export function useCompare(listId) {
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Token de la comparación en curso. Si el usuario cambia de lista —o aprieta
  // "Actualizar precios" dos veces— la respuesta que llega tarde no tiene que
  // pisar a la más nueva. Solo se toca dentro de callbacks, nunca en el render.
  const requestRef = useRef(0)

  const run = useCallback(
    ({ force } = {}) => {
      if (!listId) return Promise.resolve(null)

      const hit = cache.get(listId)
      if (!force && hit && Date.now() - hit.at < CACHE_TTL_MS) {
        requestRef.current += 1
        setPayload(hit.payload)
        setError(null)
        return Promise.resolve(hit.payload)
      }

      requestRef.current += 1
      const token = requestRef.current

      setLoading(true)
      setError(null)
      return compareList(listId)
        .then((res) => {
          cache.set(listId, { payload: res, at: Date.now() })
          if (requestRef.current === token) setPayload(res)
          return res
        })
        .catch((err) => {
          if (requestRef.current === token) {
            setError(err.message || 'No se pudieron comparar los precios.')
          }
          return null
        })
        .finally(() => {
          if (requestRef.current === token) setLoading(false)
        })
    },
    [listId],
  )

  useEffect(() => {
    setPayload(null)
    run()
  }, [run])

  const refetch = useCallback(() => run({ force: true }), [run])

  return {
    results: payload?.results ?? null,
    generatedAt: payload?.generated_at ?? null,
    loading,
    error,
    refetch,
  }
}
