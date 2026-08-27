import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Search, Trash2, RefreshCw, ArrowRight, Check, Pencil, PiggyBank } from 'lucide-react'

import AppNav from '../../components/AppNav'
import SplitPlan from '../../components/SplitPlan'
import { useCompare, invalidateCompare } from '../../hooks/useCompare'
import { useSplitPlan, invalidateSplitPlan } from '../../hooks/useSplitPlan'
import { formatPrice } from '../../lib/money'
import { getList, addItem, removeItem, renameList } from '../../services/lists.service'
import { setItemQuantity } from '../../services/cart.service'
import { searchProducts } from '../../services/products.service'
import styles from './ListDetailPage.module.css'

const SEARCH_DEBOUNCE_MS = 300

// Las dos formas de comprar una lista. No son dos pantallas: es la misma
// pregunta ("¿donde compro esto?") con dos respuestas posibles, y el usuario
// tiene que poder ir y volver entre las dos para decidir.
const BUY_MODES = [
  { id: 'single', label: 'Un solo supermercado' },
  { id: 'split', label: 'Varios supermercados' },
]

// Con cuantas paradas arranca el plan dividido. Dos es el caso del que quiere
// ahorrar sin convertir la compra en una excursion.
const DEFAULT_SPLIT_SUPERMARKETS = 2

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

  const [buyMode, setBuyMode] = useState('single')
  const [maxSupermarkets, setMaxSupermarkets] = useState(DEFAULT_SPLIT_SUPERMARKETS)

  // La comparacion se dispara sola al montar. El boton queda como "Actualizar
  // precios" para conservar el control manual sin que haga falta usarlo.
  const { results, generatedAt, loading: comparing, error: compareError, refetch } = useCompare(id)

  // El plan dividido tambien se pide solo, con su propia cache por tope de
  // supermercados. Se pide siempre, no solo con la pestaña de dividir abierta:
  // es lo que permite anunciarle el ahorro al que esta mirando el comparador
  // comun, que es justo donde hace falta contarselo.
  const {
    plan,
    loading: planning,
    error: planError,
    refetch: refetchPlan,
  } = useSplitPlan(id, maxSupermarkets)

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
    invalidateSplitPlan(id)
    await loadList()
    refetch()
    refetchPlan()
  }, [id, loadList, refetch, refetchPlan])

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

  // Un solo boton para los dos calculos: el usuario aprieta "Actualizar
  // precios" una vez y espera que se actualice lo que esta mirando, sea la
  // comparacion o el plan dividido.
  function refreshPrices() {
    invalidateCompare(id)
    invalidateSplitPlan(id)
    refetch()
    refetchPlan()
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

  // Un plan de una sola parada no es una compra dividida: se manda por el
  // camino del supermercado unico, que es el que el backend acepta (POST
  // /orders/split exige dos grupos o mas).
  function handleBuyPlan(currentPlan) {
    const groups = currentPlan.groups
    if (groups.length === 1) {
      handleChoose({ supermarket: groups[0].supermarket, total: currentPlan.total })
      return
    }
    navigate('/app/checkout', {
      state: {
        listId: id,
        estimatedTotal: currentPlan.total,
        savings: currentPlan.savings,
        groups: groups.map((group) => ({
          supermarketId: group.supermarket.id,
          supermarketName: group.supermarket.name,
          subtotal: group.subtotal,
          productIds: group.items.map((item) => item.product_id),
        })),
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
          <h2 className={styles.sectionTitle}>Cómo querés comprar</h2>
          <button
            className={styles.refreshBtn}
            onClick={refreshPrices}
            disabled={comparing || planning || list.items.length === 0}
          >
            <RefreshCw size={14} /> {comparing || planning ? 'Comparando…' : 'Actualizar precios'}
          </button>
        </div>

        {/* Las dos formas de comprar la misma lista. La eleccion no se guarda:
            es una pregunta que el usuario se hace frente a ESTA compra, no una
            preferencia permanente. */}
        <div className={styles.modes} role="tablist" aria-label="Forma de comprar">
          {BUY_MODES.map((mode) => (
            <button
              key={mode.id}
              role="tab"
              aria-selected={buyMode === mode.id}
              className={styles.modeBtn}
              data-active={buyMode === mode.id ? 'true' : 'false'}
              onClick={() => setBuyMode(mode.id)}
            >
              {mode.label}
            </button>
          ))}
        </div>

        {generatedAt && !comparing && <p className={styles.freshness}>{freshness(generatedAt)}</p>}

        {list.items.length === 0 ? (
          <p className={styles.muted}>
            Agregá productos para ver cuánto te sale en cada supermercado.
          </p>
        ) : buyMode === 'split' ? (
          <SplitPlan
            plan={plan}
            loading={planning}
            error={planError}
            maxSupermarkets={maxSupermarkets}
            onMaxSupermarketsChange={setMaxSupermarkets}
            onBuy={handleBuyPlan}
          />
        ) : (
          <>
            {/* El que mira el comparador comun no sabe que dividir existe.
                Anunciarle el ahorro concreto —no "proba dividir"— es lo unico
                que le da un motivo para mirar la otra pestaña. */}
            {plan?.is_complete && plan.savings > 0 && plan.groups.length > 1 && (
              <button className={styles.savingsHint} onClick={() => setBuyMode('split')}>
                <PiggyBank size={15} aria-hidden="true" />
                <span>
                  Comprando en {plan.groups.length} supermercados ahorrás{' '}
                  {formatPrice(plan.savings)}. Ver cómo
                </span>
                <ArrowRight size={14} aria-hidden="true" />
              </button>
            )}

            {compareError && <p className={styles.errorText} role="alert">{compareError}</p>}

            {comparing && !results ? (
              <p className={styles.muted}>Buscando precios en los supermercados…</p>
            ) : results && results.length === 0 ? (
              <p className={styles.muted}>
                Ningún supermercado tiene stock de estos productos todavía.
              </p>
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
                      {/* Un pedido con productos faltantes lo rechaza el backend
                          con 409, asi que el boton no se ofrece: llevaria a un
                          error garantizado en el checkout. */}
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
          </>
        )}
      </section>
    </div>
  )
}
