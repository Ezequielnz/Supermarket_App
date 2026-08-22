import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Search, Trash2, RefreshCw, ArrowRight, Check, Pencil } from 'lucide-react'

import AppNav from '../../components/AppNav'
import { useCompare, invalidateCompare } from '../../hooks/useCompare'
import { formatPrice } from '../../lib/money'
import { getList, addItem, removeItem, renameList } from '../../services/lists.service'
import { setItemQuantity } from '../../services/cart.service'
import { searchProducts } from '../../services/products.service'
import styles from './ListDetailPage.module.css'

const SEARCH_DEBOUNCE_MS = 300

// "hace 2 min" a partir del generated_at del backend. El usuario no pidio la
// comparacion —se disparo sola al abrir la lista—, asi que tiene que poder ver
// que tan fresco es el numero que esta mirando.
function freshness(isoDate) {
  if (!isoDate) return null
  const seconds = Math.max(0, Math.round((Date.now() - new Date(isoDate).getTime()) / 1000))
  if (seconds < 60) return 'recién actualizado'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `actualizado hace ${minutes} min`
  const hours = Math.round(minutes / 60)
  return `actualizado hace ${hours} h`
}

export default function ListDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [list, setList] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])

  const [busyId, setBusyId] = useState(null)
  const [renaming, setRenaming] = useState(false)
  const [nameDraft, setNameDraft] = useState('')

  // La comparacion se dispara sola al montar. El boton queda como "Actualizar
  // precios" para conservar el control manual sin que haga falta usarlo.
  const { results, generatedAt, loading: comparing, error: compareError, refetch } = useCompare(id)

  const loadList = useCallback(() => {
    setLoading(true)
    return getList(id)
      .then(setList)
      .catch((err) => setError(err.message || 'No se pudo cargar la lista.'))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => { loadList() }, [loadList])

  useEffect(() => {
    if (!query.trim()) {
      setSearchResults([])
      return
    }
    const timeout = setTimeout(() => {
      searchProducts(query).then((res) => setSearchResults(res.data)).catch(() => setSearchResults([]))
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timeout)
  }, [query])

  // Cualquier cambio en los items invalida los totales: la cache del hook
  // guarda el resultado por lista, asi que hay que limpiarla a mano.
  const reloadAfterChange = useCallback(async () => {
    invalidateCompare(id)
    await loadList()
    refetch()
  }, [id, loadList, refetch])

  async function handleAdd(productId) {
    setError(null)
    try {
      await addItem(id, { productId, quantity: 1 })
      setQuery('')
      setSearchResults([])
      await reloadAfterChange()
    } catch (err) {
      setError(err.message || 'No se pudo agregar el producto.')
    }
  }

  async function handleRemove(itemId) {
    setBusyId(itemId)
    setError(null)
    try {
      await removeItem(id, itemId)
      await reloadAfterChange()
    } catch (err) {
      setError(err.message || 'No se pudo quitar el producto.')
    } finally {
      setBusyId(null)
    }
  }

  // Fija la cantidad, no la suma: es el control - / +. Para sacar el item esta
  // el boton de la papelera, no un quantity = 0 (el backend lo rechaza).
  async function changeQuantity(item, next) {
    if (next < 1) return
    setBusyId(item.id)
    setError(null)
    try {
      await setItemQuantity(id, item.id, next)
      await reloadAfterChange()
    } catch (err) {
      setError(err.message || 'No se pudo actualizar la cantidad.')
    } finally {
      setBusyId(null)
    }
  }

  async function handleRename(event) {
    event.preventDefault()
    const name = nameDraft.trim()
    if (!name || name === list.name) {
      setRenaming(false)
      return
    }
    try {
      await renameList(id, { name })
      setList((prev) => ({ ...prev, name }))
      setRenaming(false)
    } catch (err) {
      setError(err.message || 'No se pudo renombrar la lista.')
    }
  }

  function handleChoose(result) {
    navigate('/app/checkout', {
      state: {
        listId: id,
        supermarketId: result.supermarket.id,
        supermarketName: result.supermarket.name,
        estimatedTotal: result.total,
      },
    })
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <AppNav />
        <p className={styles.muted}>Cargando…</p>
      </div>
    )
  }

  if (!list) {
    return (
      <div className={styles.page}>
        <AppNav />
        <p className={styles.errorText} role="alert">{error || 'Lista no encontrada.'}</p>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <AppNav />
      <a href="#/app/lists" className={styles.backLink}>
        <ArrowLeft size={16} /> Volver a mis listas
      </a>

      {renaming ? (
        <form className={styles.renameForm} onSubmit={handleRename}>
          <input
            className={styles.searchInput}
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
            maxLength={120}
            aria-label="Nombre de la lista"
          />
          <button type="submit" className={styles.renameSave}>Guardar</button>
          <button type="button" className={styles.renameCancel} onClick={() => setRenaming(false)}>
            Cancelar
          </button>
        </form>
      ) : (
        <div className={styles.titleRow}>
          <h1 className={styles.title}>{list.name}</h1>
          <button
            className={styles.renameBtn}
            onClick={() => { setNameDraft(list.name); setRenaming(true) }}
            aria-label="Renombrar la lista"
          >
            <Pencil size={15} />
          </button>
        </div>
      )}

      {error && <p className={styles.errorText} role="alert">{error}</p>}

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Agregar producto</h2>
        <div className={styles.searchWrap}>
          <Search size={16} className={styles.searchIcon} />
          <input
            className={styles.searchInput}
            placeholder="Buscar producto (ej. leche)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {searchResults.length > 0 && (
          <div className={styles.searchResults}>
            {searchResults.map((p) => (
              <button key={p.id} className={styles.searchResult} onClick={() => handleAdd(p.id)}>
                {p.name}
              </button>
            ))}
          </div>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Productos de la lista</h2>
        {list.items.length === 0 ? (
          <p className={styles.muted}>Todavía no agregaste productos.</p>
        ) : (
          <div className={styles.items}>
            {list.items.map((item) => (
              <div key={item.id} className={styles.item}>
                <span>{item.product_name}</span>
                <div className={styles.itemRight}>
                  <div className={styles.qtyControl}>
                    <button
                      onClick={() => changeQuantity(item, Number(item.quantity) - 1)}
                      disabled={busyId === item.id || Number(item.quantity) <= 1}
                      aria-label={`Quitar una unidad de ${item.product_name}`}
                    >
                      −
                    </button>
                    <span>{item.quantity}</span>
                    <button
                      onClick={() => changeQuantity(item, Number(item.quantity) + 1)}
                      disabled={busyId === item.id}
                      aria-label={`Agregar una unidad de ${item.product_name}`}
                    >
                      +
                    </button>
                  </div>
                  <button
                    className={styles.removeBtn}
                    onClick={() => handleRemove(item.id)}
                    disabled={busyId === item.id}
                    aria-label={`Quitar ${item.product_name}`}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className={styles.section}>
        <div className={styles.resultsHeader}>
          <h2 className={styles.sectionTitle}>Dónde te conviene comprar</h2>
          <button
            className={styles.refreshBtn}
            onClick={refetch}
            disabled={comparing || list.items.length === 0}
          >
            <RefreshCw size={14} /> {comparing ? 'Comparando…' : 'Actualizar precios'}
          </button>
        </div>

        {generatedAt && !comparing && <p className={styles.freshness}>{freshness(generatedAt)}</p>}

        {compareError && <p className={styles.errorText} role="alert">{compareError}</p>}

        {list.items.length === 0 ? (
          <p className={styles.muted}>
            Agregá productos para ver cuánto te sale en cada supermercado.
          </p>
        ) : comparing && !results ? (
          <p className={styles.muted}>Buscando precios en los supermercados…</p>
        ) : results && results.length === 0 ? (
          <p className={styles.muted}>Ningún supermercado tiene stock de estos productos todavía.</p>
        ) : (
          <div className={styles.results}>
            {results?.map((result) => (
              <div key={result.supermarket.id} className={styles.resultCard}>
                <div className={styles.resultMain}>
                  <div className={styles.resultTop}>
                    <p className={styles.resultName}>{result.supermarket.name}</p>
                    <span
                      className={styles.coverage}
                      data-complete={result.is_complete ? 'true' : 'false'}
                    >
                      {result.is_complete && <Check size={12} aria-hidden="true" />}
                      {result.items_covered} de {result.items_total}
                    </span>
                  </div>
                  {!result.is_complete && (
                    <p className={styles.missing}>
                      Falta: {result.missing.map((m) => m.product_name).join(', ')}
                    </p>
                  )}
                </div>
                <div className={styles.resultRight}>
                  <span className={styles.resultTotal}>{formatPrice(result.total)}</span>
                  {/* Un pedido con productos faltantes lo rechaza el backend con
                      409, asi que el boton no se ofrece: llevaria a un error
                      garantizado en el checkout. */}
                  <button
                    className={styles.chooseBtn}
                    onClick={() => handleChoose(result)}
                    disabled={!result.is_complete}
                    title={
                      result.is_complete
                        ? undefined
                        : 'Este supermercado no tiene todos los productos de tu lista'
                    }
                  >
                    Elegir y continuar <ArrowRight size={15} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
