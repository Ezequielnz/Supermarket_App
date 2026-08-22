import { useCallback, useEffect, useState } from 'react'
import { Search, Plus, Check, X, Store } from 'lucide-react'

import AppNav from '../../components/AppNav'
import { useCart } from '../../hooks/useCart'
import { formatPrice } from '../../lib/money'
import { getCategories, getProductPrices, searchProducts } from '../../services/products.service'
import styles from './ExplorePage.module.css'

const SEARCH_DEBOUNCE_MS = 300
const PER_PAGE = 24
const ALL_CATEGORIES = ''

const SORTS = [
  { value: 'name', label: 'Nombre' },
  { value: 'price', label: 'Precio' },
]

export default function ExplorePage() {
  const { addProduct } = useCart()

  const [products, setProducts] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [category, setCategory] = useState(ALL_CATEGORIES)
  const [sort, setSort] = useState('name')
  const [categories, setCategories] = useState([])

  const [addedId, setAddedId] = useState(null)
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    const timeout = setTimeout(() => {
      setDebouncedQuery(query.trim())
      setPage(1)
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timeout)
  }, [query])

  useEffect(() => {
    getCategories()
      .then((result) => setCategories(result.data))
      .catch(() => setCategories([]))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await searchProducts(debouncedQuery || undefined, {
        page,
        per_page: PER_PAGE,
        category: category || undefined,
        sort,
      })
      // "Ver más" acumula; un cambio de filtro (que resetea a page 1) reemplaza.
      setProducts((prev) => (page === 1 ? result.data : [...prev, ...result.data]))
      setTotal(result.total)
      setError(null)
    } catch (err) {
      setError(err.message || 'No pudimos cargar los productos.')
    } finally {
      setLoading(false)
    }
  }, [debouncedQuery, category, sort, page])

  useEffect(() => { load() }, [load])

  function changeCategory(value) {
    setCategory(value)
    setPage(1)
  }

  function changeSort(value) {
    setSort(value)
    setPage(1)
  }

  async function handleAdd(product) {
    setError(null)
    try {
      await addProduct(product.id)
      setAddedId(product.id)
      setTimeout(() => setAddedId((current) => (current === product.id ? null : current)), 1600)
    } catch (err) {
      setError(err.message || 'No pudimos agregar el producto al carrito.')
    }
  }

  async function openDetail(product) {
    setDetail({ product, prices: null, loading: true })
    try {
      const result = await getProductPrices(product.id)
      setDetail({ product, prices: result.prices, loading: false })
    } catch {
      setDetail({ product, prices: [], loading: false })
    }
  }

  const hasMore = products.length < total

  return (
    <div className={styles.page}>
      <AppNav />

      <header className={styles.header}>
        <h1 className={styles.title}>Explorar productos</h1>
        <p className={styles.subtitle}>
          El precio que ves es el más barato de hoy. Elegís dónde comprar al comparar tu carrito.
        </p>
      </header>

      <div className={styles.filters}>
        <div className={styles.searchWrap}>
          <Search size={16} className={styles.searchIcon} aria-hidden="true" />
          <input
            className={styles.searchInput}
            value={query}
            placeholder="Buscar (ej. leche)"
            aria-label="Buscar productos"
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <label className={styles.filterField}>
          <span className={styles.filterLabel}>Categoría</span>
          <select
            className={styles.select}
            value={category}
            onChange={(e) => changeCategory(e.target.value)}
          >
            <option value={ALL_CATEGORIES}>Todas</option>
            {categories.map((cat) => (
              <option key={cat.name} value={cat.name}>{cat.name}</option>
            ))}
          </select>
        </label>

        <label className={styles.filterField}>
          <span className={styles.filterLabel}>Ordenar por</span>
          <select
            className={styles.select}
            value={sort}
            onChange={(e) => changeSort(e.target.value)}
          >
            {SORTS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>

      {error && <p className={styles.error} role="alert">{error}</p>}

      {loading && products.length === 0 ? (
        <p className={styles.muted}>Cargando productos…</p>
      ) : products.length === 0 ? (
        <p className={styles.muted}>
          {debouncedQuery
            ? `Ningún producto coincide con "${debouncedQuery}".`
            : 'Todavía no hay productos en el catálogo.'}
        </p>
      ) : (
        <>
          <div className={styles.grid}>
            {products.map((product) => (
              <article key={product.id} className={styles.card}>
                <button
                  type="button"
                  className={styles.cardBody}
                  onClick={() => openDetail(product)}
                  aria-label={`Ver todos los precios de ${product.name}`}
                >
                  <span className={styles.thumb} aria-hidden="true">
                    {product.image_url
                      ? <img src={product.image_url} alt="" className={styles.thumbImg} />
                      : <Store size={20} />}
                  </span>
                  <span className={styles.cardName}>{product.name}</span>
                  {product.brand && <span className={styles.cardBrand}>{product.brand}</span>}

                  {product.best_price === null ? (
                    <span className={styles.noPrice}>Sin precio disponible</span>
                  ) : (
                    <>
                      {/* "desde", no "$X": es el mínimo entre supermercados, y
                          prometer un precio que cambia al elegir tienda seria
                          mentir. */}
                      <span className={styles.priceLabel}>desde</span>
                      <span className={styles.price}>{formatPrice(product.best_price)}</span>
                      <span className={styles.store}>
                        {product.best_price_supermarket?.name}
                      </span>
                      <span className={styles.availability}>
                        en {product.available_in} supermercado{product.available_in === 1 ? '' : 's'}
                      </span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  className={`${styles.addBtn} ${addedId === product.id ? styles.addBtnDone : ''}`}
                  onClick={() => handleAdd(product)}
                  aria-label={`Agregar ${product.name} al carrito`}
                >
                  {addedId === product.id ? (
                    <><Check size={15} aria-hidden="true" /> Agregado</>
                  ) : (
                    <><Plus size={15} aria-hidden="true" /> Agregar</>
                  )}
                </button>
              </article>
            ))}
          </div>

          {hasMore && (
            <button
              type="button"
              className={styles.moreBtn}
              onClick={() => setPage((p) => p + 1)}
              disabled={loading}
            >
              {loading ? 'Cargando…' : `Ver más (${total - products.length} restantes)`}
            </button>
          )}
        </>
      )}

      {detail && (
        <div className={styles.overlay} role="presentation" onClick={() => setDetail(null)}>
          <div
            className={styles.detail}
            role="dialog"
            aria-modal="true"
            aria-labelledby="detail-title"
            onClick={(e) => e.stopPropagation()}
          >
            <header className={styles.detailHead}>
              <h2 className={styles.detailTitle} id="detail-title">{detail.product.name}</h2>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={() => setDetail(null)}
                aria-label="Cerrar"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </header>

            {detail.loading ? (
              <p className={styles.muted}>Cargando precios…</p>
            ) : detail.prices.length === 0 ? (
              <p className={styles.muted}>
                Ningún supermercado tiene este producto disponible ahora mismo.
              </p>
            ) : (
              <ul className={styles.priceList}>
                {detail.prices.map((entry) => (
                  <li key={entry.supermarket.id} className={styles.priceRow}>
                    <span>
                      <span className={styles.priceStore}>{entry.supermarket.name}</span>
                      {!entry.in_stock && <span className={styles.outOfStock}>Sin stock</span>}
                    </span>
                    <span className={styles.priceValue}>{formatPrice(entry.price)}</span>
                  </li>
                ))}
              </ul>
            )}

            <button
              type="button"
              className={styles.detailAddBtn}
              onClick={() => { handleAdd(detail.product); setDetail(null) }}
            >
              <Plus size={16} aria-hidden="true" /> Agregar al carrito
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
