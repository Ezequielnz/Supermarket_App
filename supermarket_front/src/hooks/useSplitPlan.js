import { useCallback, useEffect, useRef, useState } from 'react'

import { compareListSplit } from '../services/lists.service'

// Mismo horizonte que useCompare: un plan es una foto de precios, y a los 5
// minutos deja de ser creíble.
const CACHE_TTL_MS = 5 * 60 * 1000

// `${listId}:${maxSupermarkets}` -> { payload, at }. Un plan depende del tope
// de supermercados, así que el tope es parte de la clave: ir y volver entre
// "hasta 2" y "hasta 3" no vuelve a pegarle a la API. Vive en el módulo y no en
// localStorage, por lo mismo que useCompare: un total viejo que sobrevive días
// es peor que un spinner.
const cache = new Map()

function cacheKey(listId, maxSupermarkets) {
  return `${listId}:${maxSupermarkets}`
}

// Se invalidan TODOS los topes de esa lista: cambió lo que hay que comprar, así
// que ningún plan de esa lista sigue siendo válido.
export function invalidateSplitPlan(listId) {
  for (const key of cache.keys()) {
    if (key.startsWith(`${listId}:`)) cache.delete(key)
  }
}

export function useSplitPlan(listId, maxSupermarkets) {
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Token del pedido en curso: si el usuario cambia el tope dos veces seguidas,
  // la respuesta que llega tarde no puede pisar a la más nueva.
  const requestRef = useRef(0)

  const run = useCallback(
    ({ force } = {}) => {
      if (!listId) return Promise.resolve(null)

      const key = cacheKey(listId, maxSupermarkets)
      const hit = cache.get(key)
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
      return compareListSplit(listId, { maxSupermarkets })
        .then((res) => {
          cache.set(key, { payload: res, at: Date.now() })
          if (requestRef.current === token) setPayload(res)
          return res
        })
        .catch((err) => {
          if (requestRef.current === token) {
            setError(err.message || 'No pudimos armar el plan de compra.')
          }
          return null
        })
        .finally(() => {
          if (requestRef.current === token) setLoading(false)
        })
    },
    [listId, maxSupermarkets],
  )

  useEffect(() => {
    setPayload(null)
    run()
  }, [run])

  const refetch = useCallback(() => run({ force: true }), [run])

  return { plan: payload, loading, error, refetch }
}
