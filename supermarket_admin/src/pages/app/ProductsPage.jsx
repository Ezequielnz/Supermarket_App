import { useCallback, useEffect, useState } from 'react'
import { Plus, Search, Trash2, Check, X } from 'lucide-react'

import Button from '../../components/ui/Button'
import ProductFormModal from '../../components/ProductFormModal'
import TopBar from '../../components/TopBar'
import { useAdminAuth } from '../../hooks/useAdminAuth'
import { centsToInput, formatPrice, inputToCents } from '../../lib/money'
import {
  deleteMyProduct,
  getMyProducts,
  updateMyProduct,
} from '../../services/products.service'
import { getMyStores } from '../../services/supermarket.service'
import styles from './ProductsPage.module.css'

const SEARCH_DEBOUNCE_MS = 300
const ALL_STORES = ''

export default function ProductsPage() {
  const { role } = useAdminAuth()

  const [stores, setStores] = useState([])
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [storeId, setStoreId] = useState(ALL_STORES)
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [priceDraft, setPriceDraft] = useState('')
  const [savingId, setSavingId] = useState(null)

  // El rol 'staff' ve los precios pero no los toca: es lo que dice la matriz de
  // permisos de docs/SEGURIDAD.md §4.2. El backend igual lo rechaza con 403
  // (require_approved_manager); acá se esconden los controles para no ofrecer
  // algo que va a fallar.
  const canManage = role === 'owner' || role === 'manager'

  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedQuery(query.trim()), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timeout)
  }, [query])

  useEffect(() => {
    getMyStores()
      .then((result) => setStores(result.data))
      .catch(() => setStores([]))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await getMyProducts({
        supermarketId: storeId || undefined,
        q: debouncedQuery || undefined,
        per_page: 100,
      })
      setRows(result.data)
      setTotal(result.total)
      setError(null)
    } catch (err) {
      setError(err.message || 'No pudimos cargar tu catálogo.')
    } finally {
      setLoading(false)
    }
  }, [storeId, debouncedQuery])

  useEffect(() => { load() }, [load])

  function startEditing(row) {
    setEditingId(row.id)
    setPriceDraft(centsToInput(row.price))
    setError(null)
  }

  function cancelEditing() {
    setEditingId(null)
    setPriceDraft('')
  }

  async function savePrice(row) {
    const cents = inputToCents(priceDraft)
    if (cents === null) {
      setError('Ingresá un precio mayor a cero.')
      return
    }
    if (cents === row.price) {
      cancelEditing()
      return
    }

    setSavingId(row.id)
    setError(null)
    try {
      const updated = await updateMyProduct(row.id, { price: cents })
      setRows((prev) => prev.map((r) => (r.id === row.id ? updated : r)))
      cancelEditing()
    } catch (err) {
      setError(err.message || 'No pudimos actualizar el precio.')
    } finally {
      setSavingId(null)
    }
  }

  async function toggleStock(row) {
    setSavingId(row.id)
    setError(null)
    try {
      const updated = await updateMyProduct(row.id, { inStock: !row.in_stock })
      setRows((prev) => prev.map((r) => (r.id === row.id ? updated : r)))
    } catch (err) {
      setError(err.message || 'No pudimos actualizar el stock.')
    } finally {
      setSavingId(null)
    }
  }

  async function handleDelete(row) {
    const label = `${row.product.name} en ${row.supermarket.name}`
    if (!window.confirm(`¿Dejar de vender ${label}?`)) return

    setSavingId(row.id)
    setError(null)
    try {
      await deleteMyProduct(row.id)
      setRows((prev) => prev.filter((r) => r.id !== row.id))
      setTotal((prev) => Math.max(0, prev - 1))
    } catch (err) {
      setError(err.message || 'No pudimos quitar el producto.')
    } finally {
      setSavingId(null)
    }
  }

  async function handleCreated() {
    setShowModal(false)
    await load()
  }

  return (
    <>
      <TopBar
        title="Productos"
        description="Lo que vendés y a qué precio. El precio se edita en línea; el producto es del catálogo compartido."
        actions={
          canManage && stores.length > 0 && (
            <Button onClick={() => setShowModal(true)}>
              <Plus size={16} aria-hidden="true" />
              Agregar producto
            </Button>
          )
        }
      />

      {error && <p className={styles.error} role="alert">{error}</p>}

      {stores.length === 0 && !loading && (
        <p className={styles.notice}>
          Todavía no tenés sucursales. Creá una en <a href="#/app/stores">Sucursales</a> antes
          de cargar precios: un precio siempre es el precio de una sucursal.
        </p>
      )}

      <div className={styles.filters}>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>Sucursal</span>
          <select
            className={styles.select}
            value={storeId}
            onChange={(e) => setStoreId(e.target.value)}
          >
            <option value={ALL_STORES}>Todas</option>
            {stores.map((store) => (
              <option key={store.id} value={store.id}>{store.name}</option>
            ))}
          </select>
        </label>

        <label className={styles.filterField}>
          <span className={styles.filterLabel}>Buscar</span>
          <span className={styles.searchWrap}>
            <Search size={15} className={styles.searchIcon} aria-hidden="true" />
            <input
              className={styles.searchInput}
              value={query}
              placeholder="Nombre del producto"
              onChange={(e) => setQuery(e.target.value)}
            />
          </span>
        </label>
      </div>

      {loading ? (
        <p className={styles.muted}>Cargando catálogo…</p>
      ) : rows.length === 0 ? (
        <p className={styles.muted}>
          {debouncedQuery
            ? `Ningún producto coincide con "${debouncedQuery}".`
            : 'Todavía no cargaste productos.'}
        </p>
      ) : (
        <>
          <p className={styles.count}>
            {total} producto{total === 1 ? '' : 's'} cargado{total === 1 ? '' : 's'}
          </p>

          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">Producto</th>
                  <th scope="col">Sucursal</th>
                  <th scope="col">Precio</th>
                  <th scope="col">Stock</th>
                  {canManage && <th scope="col"><span className={styles.srOnly}>Acciones</span></th>}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <span className={styles.productName}>{row.product.name}</span>
                      <span className={styles.productMeta}>
                        {[row.product.brand, row.product.ean].filter(Boolean).join(' · ') || '—'}
                      </span>
                    </td>
                    <td className={styles.storeCell}>{row.supermarket.name}</td>
                    <td>
                      {editingId === row.id ? (
                        <span className={styles.priceEdit}>
                          <input
                            className={styles.priceInput}
                            value={priceDraft}
                            inputMode="decimal"
                            autoFocus
                            aria-label={`Precio de ${row.product.name}`}
                            onChange={(e) => setPriceDraft(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') savePrice(row)
                              if (e.key === 'Escape') cancelEditing()
                            }}
                          />
                          <button
                            type="button"
                            className={styles.iconBtn}
                            onClick={() => savePrice(row)}
                            disabled={savingId === row.id}
                            aria-label="Guardar precio"
                          >
                            <Check size={15} aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            className={styles.iconBtn}
                            onClick={cancelEditing}
                            aria-label="Cancelar"
                          >
                            <X size={15} aria-hidden="true" />
                          </button>
                        </span>
                      ) : canManage ? (
                        <button
                          type="button"
                          className={styles.priceBtn}
                          onClick={() => startEditing(row)}
                          aria-label={`Editar el precio de ${row.product.name}`}
                        >
                          {formatPrice(row.price)}
                        </button>
                      ) : (
                        <span className={styles.priceStatic}>{formatPrice(row.price)}</span>
                      )}
                    </td>
                    <td>
                      {canManage ? (
                        <label className={styles.stockToggle}>
                          <input
                            type="checkbox"
                            checked={row.in_stock}
                            disabled={savingId === row.id}
                            onChange={() => toggleStock(row)}
                            aria-label={`Stock de ${row.product.name} en ${row.supermarket.name}`}
                          />
                          <span>{row.in_stock ? 'Sí' : 'No'}</span>
                        </label>
                      ) : (
                        <span>{row.in_stock ? 'Sí' : 'No'}</span>
                      )}
                    </td>
                    {canManage && (
                      <td>
                        <button
                          type="button"
                          className={styles.deleteBtn}
                          onClick={() => handleDelete(row)}
                          disabled={savingId === row.id}
                          aria-label={`Dejar de vender ${row.product.name} en ${row.supermarket.name}`}
                        >
                          <Trash2 size={15} aria-hidden="true" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {showModal && (
        <ProductFormModal
          stores={stores}
          defaultStoreId={storeId || undefined}
          onClose={() => setShowModal(false)}
          onCreated={handleCreated}
        />
      )}
    </>
  )
}
