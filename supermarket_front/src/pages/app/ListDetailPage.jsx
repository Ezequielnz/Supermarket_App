import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Search, Trash2, BarChart2, ArrowRight } from 'lucide-react'

import { getList, addItem, removeItem, compareList } from '../../services/lists.service'
import { searchProducts } from '../../services/products.service'
import styles from './ListDetailPage.module.css'

export default function ListDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [list, setList] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])

  const [comparing, setComparing] = useState(false)
  const [compareResults, setCompareResults] = useState(null)

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
    }, 300)
    return () => clearTimeout(timeout)
  }, [query])

  async function handleAdd(productId) {
    await addItem(id, { productId, quantity: 1 })
    setQuery('')
    setSearchResults([])
    setCompareResults(null)
    loadList()
  }

  async function handleRemove(itemId) {
    await removeItem(id, itemId)
    setCompareResults(null)
    loadList()
  }

  async function handleCompare() {
    setComparing(true)
    setError(null)
    try {
      const res = await compareList(id)
      setCompareResults(res)
    } catch (err) {
      setError(err.message || 'No se pudo comparar precios.')
    } finally {
      setComparing(false)
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

  if (loading) return <p className={styles.muted}>Cargando…</p>
  if (!list) return <p className={styles.errorText}>{error || 'Lista no encontrada.'}</p>

  return (
    <div className={styles.page}>
      <a href="#/app/lists" className={styles.backLink}>
        <ArrowLeft size={16} /> Volver a mis listas
      </a>
      <h1 className={styles.title}>{list.name}</h1>

      {error && <p className={styles.errorText}>{error}</p>}

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
                  <span className={styles.itemQty}>x{item.quantity}</span>
                  <button
                    className={styles.removeBtn}
                    onClick={() => handleRemove(item.id)}
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

      <button
        className={styles.compareBtn}
        onClick={handleCompare}
        disabled={comparing || list.items.length === 0}
      >
        <BarChart2 size={18} /> {comparing ? 'Comparando…' : 'Comparar precios'}
      </button>

      {compareResults && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Resultados</h2>
          {compareResults.results.length === 0 ? (
            <p className={styles.muted}>Ningún supermercado tiene stock de estos productos todavía.</p>
          ) : (
            <div className={styles.results}>
              {compareResults.results.map((result) => (
                <div key={result.supermarket.id} className={styles.resultCard}>
                  <div>
                    <p className={styles.resultName}>{result.supermarket.name}</p>
                    <p className={styles.resultMeta}>
                      {result.is_complete ? 'Todos los productos disponibles' : 'Faltan productos en este súper'}
                    </p>
                  </div>
                  <div className={styles.resultRight}>
                    <span className={styles.resultTotal}>${result.total.toFixed(2)}</span>
                    <button className={styles.chooseBtn} onClick={() => handleChoose(result)}>
                      Elegir y continuar <ArrowRight size={15} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  )
}
