import { useEffect, useRef, useState } from 'react'
import { Search, X, Check, PackagePlus, ArrowLeft } from 'lucide-react'

import Button from './ui/Button'
import Field from './ui/Field'
import Input from './ui/Input'
import { inputToCents } from '../lib/money'
import { inputToStock } from '../lib/stock'
import { createMyProduct, lookupProduct } from '../services/products.service'
import styles from './ProductFormModal.module.css'

// Espeja el enum product_unit de la migración 008. Si un día se agrega un
// valor, se agrega en la migración Y acá: la base rechaza cualquier otro.
const UNITS = ['un', 'kg', 'g', 'L', 'ml']

const STEP_SEARCH = 'search'
const STEP_DETAILS = 'details'

const EMPTY_DRAFT = {
  name: '', ean: '', brand: '', unit: '', size_value: '', category: '', image_url: '',
}

export default function ProductFormModal({ stores, defaultStoreId, onClose, onCreated }) {
  const [step, setStep] = useState(STEP_SEARCH)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const [storeId, setStoreId] = useState(defaultStoreId || stores[0]?.id || '')
  const [ean, setEan] = useState('')
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState(null)

  // Cuando está seteado, el alta VINCULA a ese producto global y no crea nada.
  const [linkedProduct, setLinkedProduct] = useState(null)
  const [draft, setDraft] = useState(EMPTY_DRAFT)
  const [price, setPrice] = useState('')
  const [stock, setStock] = useState('')
  const [inStock, setInStock] = useState(true)

  const dialogRef = useRef(null)

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    dialogRef.current?.focus()
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  async function handleSearch(e) {
    e.preventDefault()
    if (!ean.trim() && !query.trim()) return
    setSearching(true)
    setError(null)
    try {
      const found = await lookupProduct({
        ean: ean.trim() || undefined,
        q: query.trim() || undefined,
        supermarketId: storeId || undefined,
      })
      setResults(found)
      // Sin ninguna coincidencia no hay nada que elegir: se pasa directo a
      // cargar el producto nuevo, con lo que ya escribió precargado.
      if (!found.exact_match && found.candidates.length === 0) {
        startNewProduct()
      }
    } catch (err) {
      setError(err.message || 'No pudimos buscar en el catálogo.')
    } finally {
      setSearching(false)
    }
  }

  function linkTo(product) {
    setLinkedProduct(product)
    setStep(STEP_DETAILS)
  }

  function startNewProduct() {
    setLinkedProduct(null)
    setDraft({ ...EMPTY_DRAFT, name: query.trim(), ean: ean.trim() })
    setStep(STEP_DETAILS)
  }

  function updateDraft(field, value) {
    setDraft((prev) => ({ ...prev, [field]: value }))
  }

  function backToSearch() {
    setStep(STEP_SEARCH)
    setLinkedProduct(null)
    setError(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const cents = inputToCents(price)
    if (cents === null) {
      setError('Ingresá un precio mayor a cero.')
      return
    }
    // Vacío es `null` y significa "no llevo control de unidades" (granel), que
    // es distinto de cero. Solo undefined es un error de tipeo.
    const quantity = inputToStock(stock)
    if (quantity === undefined) {
      setError('Las unidades tienen que ser un número, o dejalo vacío si no las controlás.')
      return
    }
    if (!storeId) {
      setError('Elegí la sucursal donde se vende.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      await createMyProduct({
        supermarketId: storeId,
        price: cents,
        inStock,
        stockQuantity: quantity,
        productId: linkedProduct?.id,
        product: linkedProduct
          ? undefined
          : {
              name: draft.name,
              ean: draft.ean.trim() || null,
              brand: draft.brand.trim() || null,
              unit: draft.unit || null,
              size_value: draft.size_value ? Number(draft.size_value) : null,
              size_unit: draft.unit || null,
              category: draft.category.trim() || null,
              image_url: draft.image_url.trim() || null,
            },
      })
      onCreated()
    } catch (err) {
      setError(err.message || 'No pudimos cargar el producto.')
    } finally {
      setSaving(false)
    }
  }

  const storeOptions = (
    <Field id="product-store" label="Sucursal" required>
      {({ id, describedBy }) => (
        <select
          id={id}
          className={styles.select}
          value={storeId}
          onChange={(e) => setStoreId(e.target.value)}
          aria-describedby={describedBy}
          required
        >
          {stores.map((store) => (
            <option key={store.id} value={store.id}>{store.name}</option>
          ))}
        </select>
      )}
    </Field>
  )

  return (
    <div className={styles.overlay} role="presentation" onClick={onClose}>
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="product-modal-title"
        tabIndex={-1}
        ref={dialogRef}
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.head}>
          <div>
            <p className={styles.stepLabel}>
              Paso {step === STEP_SEARCH ? '1' : '2'} de 2
            </p>
            <h2 className={styles.title} id="product-modal-title">
              {step === STEP_SEARCH ? 'Buscar en el catálogo' : 'Completar y poner precio'}
            </h2>
          </div>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Cerrar">
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        {error && <p className={styles.error} role="alert">{error}</p>}

        {step === STEP_SEARCH ? (
          <form className={styles.body} onSubmit={handleSearch} noValidate>
            <p className={styles.help}>
              Buscá primero por código de barras. Si el producto ya está en el catálogo,
              tu precio se compara con el de las otras cadenas en vez de quedar aislado.
            </p>

            {storeOptions}

            <Field
              id="lookup-ean"
              label="Código de barras (EAN)"
              hint="8 a 14 dígitos. Es la forma más confiable de encontrar el producto."
            >
              {({ id, describedBy }) => (
                <Input
                  id={id}
                  value={ean}
                  inputMode="numeric"
                  placeholder="7790001000017"
                  onChange={(e) => setEan(e.target.value)}
                  aria-describedby={describedBy}
                />
              )}
            </Field>

            <Field id="lookup-name" label="O buscá por nombre">
              {({ id, describedBy }) => (
                <Input
                  id={id}
                  value={query}
                  placeholder="leche entera"
                  onChange={(e) => setQuery(e.target.value)}
                  aria-describedby={describedBy}
                />
              )}
            </Field>

            <div className={styles.actions}>
              <Button type="submit" disabled={searching || (!ean.trim() && !query.trim())}>
                <Search size={16} aria-hidden="true" />
                {searching ? 'Buscando…' : 'Buscar'}
              </Button>
            </div>

            {results?.exact_match && (
              <section className={styles.matchBlock}>
                <p className={styles.matchLabel}>
                  <Check size={15} aria-hidden="true" />
                  Coincidencia exacta por código de barras
                </p>
                <button
                  type="button"
                  className={styles.matchCard}
                  onClick={() => linkTo(results.exact_match)}
                  disabled={results.exact_match.already_listed}
                >
                  <span className={styles.matchName}>{results.exact_match.name}</span>
                  <span className={styles.matchMeta}>
                    {results.exact_match.already_listed
                      ? 'Ya lo vendés en esta sucursal'
                      : 'Usar este y solo poner el precio'}
                  </span>
                </button>
              </section>
            )}

            {results?.candidates?.length > 0 && (
              <section className={styles.matchBlock}>
                <p className={styles.matchLabel}>Productos parecidos por nombre</p>
                <p className={styles.help}>
                  El nombre no es identidad: elegí vos cuál es, o cargá uno nuevo.
                </p>
                <ul className={styles.candidates}>
                  {results.candidates.map((candidate) => (
                    <li key={candidate.id}>
                      <button
                        type="button"
                        className={styles.matchCard}
                        onClick={() => linkTo(candidate)}
                        disabled={candidate.already_listed}
                      >
                        <span className={styles.matchName}>{candidate.name}</span>
                        <span className={styles.matchMeta}>
                          {candidate.already_listed
                            ? 'Ya lo vendés en esta sucursal'
                            : [candidate.brand, candidate.ean].filter(Boolean).join(' · ') || 'Sin marca ni EAN'}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {results && (
              <button type="button" className={styles.newLink} onClick={startNewProduct}>
                <PackagePlus size={15} aria-hidden="true" />
                {results.exact_match || results.candidates.length > 0
                  ? 'Ninguno de estos, es un producto nuevo'
                  : 'Cargar como producto nuevo'}
              </button>
            )}
          </form>
        ) : (
          <form className={styles.body} onSubmit={handleSubmit} noValidate>
            <button type="button" className={styles.backLink} onClick={backToSearch}>
              <ArrowLeft size={15} aria-hidden="true" /> Volver a buscar
            </button>

            {linkedProduct ? (
              <section className={styles.linkedBlock}>
                <p className={styles.matchLabel}>
                  <Check size={15} aria-hidden="true" /> Producto del catálogo
                </p>
                <p className={styles.linkedName}>{linkedProduct.name}</p>
                <p className={styles.matchMeta}>
                  {[linkedProduct.brand, linkedProduct.ean, linkedProduct.category]
                    .filter(Boolean)
                    .join(' · ') || 'Sin datos adicionales'}
                </p>
                <p className={styles.help}>
                  Los datos del producto son compartidos entre todas las cadenas y no se
                  editan desde acá. Vos cargás tu precio.
                </p>
              </section>
            ) : (
              <>
                <Field id="draft-name" label="Nombre" required>
                  {({ id, describedBy }) => (
                    <Input
                      id={id}
                      value={draft.name}
                      onChange={(e) => updateDraft('name', e.target.value)}
                      aria-describedby={describedBy}
                      maxLength={200}
                      required
                    />
                  )}
                </Field>

                <div className={styles.row}>
                  <Field id="draft-ean" label="Código de barras (EAN)">
                    {({ id, describedBy }) => (
                      <Input
                        id={id}
                        value={draft.ean}
                        inputMode="numeric"
                        onChange={(e) => updateDraft('ean', e.target.value)}
                        aria-describedby={describedBy}
                        maxLength={14}
                      />
                    )}
                  </Field>

                  <Field id="draft-brand" label="Marca">
                    {({ id, describedBy }) => (
                      <Input
                        id={id}
                        value={draft.brand}
                        onChange={(e) => updateDraft('brand', e.target.value)}
                        aria-describedby={describedBy}
                        maxLength={120}
                      />
                    )}
                  </Field>
                </div>

                <div className={styles.row}>
                  <Field id="draft-size" label="Tamaño">
                    {({ id, describedBy }) => (
                      <Input
                        id={id}
                        type="number"
                        step="0.001"
                        min="0"
                        value={draft.size_value}
                        onChange={(e) => updateDraft('size_value', e.target.value)}
                        aria-describedby={describedBy}
                      />
                    )}
                  </Field>

                  <Field id="draft-unit" label="Unidad">
                    {({ id, describedBy }) => (
                      <select
                        id={id}
                        className={styles.select}
                        value={draft.unit}
                        onChange={(e) => updateDraft('unit', e.target.value)}
                        aria-describedby={describedBy}
                      >
                        <option value="">Sin especificar</option>
                        {UNITS.map((unit) => (
                          <option key={unit} value={unit}>{unit}</option>
                        ))}
                      </select>
                    )}
                  </Field>
                </div>

                <Field id="draft-category" label="Categoría">
                  {({ id, describedBy }) => (
                    <Input
                      id={id}
                      value={draft.category}
                      placeholder="lácteos"
                      onChange={(e) => updateDraft('category', e.target.value)}
                      aria-describedby={describedBy}
                      maxLength={80}
                    />
                  )}
                </Field>
              </>
            )}

            {storeOptions}

            <div className={styles.row}>
              <Field id="listing-price" label="Precio (en pesos)" required>
                {({ id, describedBy }) => (
                  <Input
                    id={id}
                    value={price}
                    inputMode="decimal"
                    placeholder="1250,00"
                    onChange={(e) => setPrice(e.target.value)}
                    aria-describedby={describedBy}
                    required
                  />
                )}
              </Field>

              <Field
                id="listing-stock-qty"
                label="Unidades"
                hint="Dejalo vacío si vendés a granel y no contás unidades. En cero, el producto no se ofrece."
              >
                {({ id, describedBy }) => (
                  <Input
                    id={id}
                    value={stock}
                    inputMode="decimal"
                    placeholder="Sin control"
                    onChange={(e) => setStock(e.target.value)}
                    aria-describedby={describedBy}
                  />
                )}
              </Field>
            </div>

            <div className={styles.row}>
              <div className={styles.stockField}>
                <label className={styles.checkboxLabel} htmlFor="listing-stock">
                  <input
                    id="listing-stock"
                    type="checkbox"
                    checked={inStock}
                    onChange={(e) => setInStock(e.target.checked)}
                  />
                  Publicar en la góndola
                </label>
              </div>
            </div>

            <div className={styles.actions}>
              <Button type="button" variant="ghost" onClick={onClose}>Cancelar</Button>
              <Button type="submit" disabled={saving}>
                {saving ? 'Guardando…' : 'Cargar producto'}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
