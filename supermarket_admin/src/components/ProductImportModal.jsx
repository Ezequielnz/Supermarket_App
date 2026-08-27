import { useEffect, useRef, useState } from 'react'
import { X, Upload, FileSpreadsheet, AlertTriangle, CheckCircle2, ArrowLeft } from 'lucide-react'

import Button from './ui/Button'
import Field from './ui/Field'
import { formatPrice } from '../lib/money'
import { previewProductImport, runProductImport } from '../services/imports.service'
import styles from './ProductImportModal.module.css'

const STEP_FILE = 'file'
const STEP_PREVIEW = 'preview'
const STEP_RESULT = 'result'

// Los campos que el importador sabe llenar, con el nombre que entiende un
// encargado. El orden es el de importancia, no el del archivo: si alguien
// corrige un mapeo a mano, lo primero que busca es el precio.
const FIELD_LABELS = {
  ean: 'Código de barras',
  name: 'Nombre del producto',
  price: 'Precio de venta',
  stock_quantity: 'Stock (unidades)',
  in_stock: 'Activo / disponible',
  brand: 'Marca',
  category: 'Categoría',
  unit: 'Unidad',
  size_value: 'Contenido',
  size_unit: 'Unidad del contenido',
  image_url: 'Imagen',
}

const ACTION_LABELS = {
  create: 'Alta',
  update: 'Actualiza',
  skip: 'Se saltea',
  error: 'No entra',
}

const UNASSIGNED = ''

export default function ProductImportModal({ stores, defaultStoreId, onClose, onImported }) {
  const [step, setStep] = useState(STEP_FILE)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const [storeId, setStoreId] = useState(defaultStoreId || stores[0]?.id || '')
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)

  const [createMissing, setCreateMissing] = useState(true)
  const [updateExisting, setUpdateExisting] = useState(true)
  const [deactivateMissing, setDeactivateMissing] = useState(false)

  const [preview, setPreview] = useState(null)
  const [mapping, setMapping] = useState({})
  const [sheetName, setSheetName] = useState(null)
  const [result, setResult] = useState(null)

  const dialogRef = useRef(null)

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    dialogRef.current?.focus()
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  function currentOptions() {
    return {
      create_missing: createMissing,
      update_existing: updateExisting,
      deactivate_missing: deactivateMissing,
    }
  }

  async function analyze({ nextMapping = mapping, nextSheet = sheetName } = {}) {
    if (!file || !storeId) {
      setError('Elegí la sucursal y el archivo.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const found = await previewProductImport(file, {
        supermarketId: storeId,
        sheetName: nextSheet,
        mapping: nextMapping,
        options: currentOptions(),
      })
      setPreview(found)
      setMapping(found.mapping)
      setSheetName(found.sheet_name)
      setStep(STEP_PREVIEW)
    } catch (err) {
      setError(err.message || 'No pudimos leer el archivo.')
    } finally {
      setBusy(false)
    }
  }

  // Cambiar una columna a mano vuelve a pedir la vista previa: el conteo de
  // altas y actualizaciones depende del mapeo, y mostrarlo desactualizado
  // sería mentir justo en la pantalla que existe para confirmar.
  function remap(fieldName, value) {
    const next = { ...mapping }
    if (value === UNASSIGNED) {
      delete next[fieldName]
    } else {
      next[fieldName] = Number(value)
    }
    setMapping(next)
    analyze({ nextMapping: next })
  }

  function changeSheet(name) {
    setSheetName(name)
    // El mapeo es de la hoja anterior: en otra hoja las columnas son otras.
    setMapping({})
    analyze({ nextMapping: {}, nextSheet: name })
  }

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      const done = await runProductImport(file, {
        supermarketId: storeId,
        sheetName,
        mapping,
        options: currentOptions(),
      })
      setResult(done)
      setStep(STEP_RESULT)
    } catch (err) {
      setError(err.message || 'No pudimos importar el archivo.')
    } finally {
      setBusy(false)
    }
  }

  function pickFile(selected) {
    if (!selected) return
    setFile(selected)
    setPreview(null)
    setMapping({})
    setSheetName(null)
    setError(null)
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragging(false)
    pickFile(e.dataTransfer.files?.[0])
  }

  const counts = preview?.counts
  const willWrite = counts ? counts.listings_created + counts.listings_updated : 0

  return (
    <div className={styles.overlay} role="presentation" onClick={onClose}>
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-modal-title"
        tabIndex={-1}
        ref={dialogRef}
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.head}>
          <div>
            <p className={styles.stepLabel}>
              {step === STEP_RESULT ? 'Listo' : `Paso ${step === STEP_FILE ? '1' : '2'} de 2`}
            </p>
            <h2 className={styles.title} id="import-modal-title">
              {step === STEP_FILE && 'Importar desde tu ERP'}
              {step === STEP_PREVIEW && 'Revisá qué entendimos'}
              {step === STEP_RESULT && 'Importación terminada'}
            </h2>
          </div>
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Cerrar">
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        {error && <p className={styles.error} role="alert">{error}</p>}

        {step === STEP_FILE && (
          <div className={styles.body}>
            <p className={styles.help}>
              Subí la planilla que exporta tu sistema (.xlsx, .xls o .csv). Reconocemos los
              nombres de columna más habituales — <em>Cod.Barra</em>, <em>EAN13</em>,
              {' '}<em>Descripción</em>, <em>Precio Venta</em>, <em>Stock</em> — y antes de
              guardar nada te mostramos qué entendimos.
            </p>

            <Field id="import-store" label="Sucursal" required>
              {({ id }) => (
                <select
                  id={id}
                  className={styles.select}
                  value={storeId}
                  onChange={(e) => setStoreId(e.target.value)}
                >
                  {stores.map((store) => (
                    <option key={store.id} value={store.id}>{store.name}</option>
                  ))}
                </select>
              )}
            </Field>

            <label
              className={`${styles.dropzone} ${dragging ? styles.dropzoneActive : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
            >
              <input
                type="file"
                className={styles.fileInput}
                accept=".xlsx,.xlsm,.xls,.csv,.txt"
                onChange={(e) => pickFile(e.target.files?.[0])}
              />
              {file ? (
                <>
                  <FileSpreadsheet size={22} aria-hidden="true" />
                  <span className={styles.fileName}>{file.name}</span>
                  <span className={styles.dropHint}>Elegí otro archivo si te equivocaste</span>
                </>
              ) : (
                <>
                  <Upload size={22} aria-hidden="true" />
                  <span className={styles.fileName}>Arrastrá el archivo o hacé clic</span>
                  <span className={styles.dropHint}>Hasta 5 MB</span>
                </>
              )}
            </label>

            <fieldset className={styles.options}>
              <legend className={styles.optionsTitle}>Qué puede hacer esta importación</legend>

              <label className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={updateExisting}
                  onChange={(e) => setUpdateExisting(e.target.checked)}
                />
                <span>Actualizar el precio y el stock de lo que ya vendo</span>
              </label>

              <label className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={createMissing}
                  onChange={(e) => setCreateMissing(e.target.checked)}
                />
                <span>Dar de alta los productos que todavía no cargué</span>
              </label>

              <label className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={deactivateMissing}
                  onChange={(e) => setDeactivateMissing(e.target.checked)}
                />
                <span>
                  Marcar sin stock lo que <strong>no aparezca</strong> en el archivo
                  <span className={styles.checkboxHint}>
                    Solo si el archivo es tu catálogo completo. Con un export parcial vas a
                    despublicar el resto de tu góndola.
                  </span>
                </span>
              </label>
            </fieldset>

            <div className={styles.actions}>
              <Button variant="secondary" onClick={onClose}>Cancelar</Button>
              <Button onClick={() => analyze()} disabled={busy || !file || !storeId}>
                {busy ? 'Leyendo…' : 'Analizar archivo'}
              </Button>
            </div>
          </div>
        )}

        {step === STEP_PREVIEW && preview && (
          <div className={styles.body}>
            <div className={styles.summary}>
              <span className={styles.summaryItem}>
                <strong>{counts.rows_total}</strong> filas leídas
              </span>
              <span className={styles.summaryItem}>
                <strong>{counts.listings_updated}</strong> se actualizan
              </span>
              <span className={styles.summaryItem}>
                <strong>{counts.listings_created}</strong> se dan de alta
              </span>
              {counts.rows_skipped > 0 && (
                <span className={styles.summaryItem}>
                  <strong>{counts.rows_skipped}</strong> se saltean
                </span>
              )}
              {counts.rows_failed > 0 && (
                <span className={`${styles.summaryItem} ${styles.summaryBad}`}>
                  <strong>{counts.rows_failed}</strong> no entran
                </span>
              )}
            </div>

            {counts.listings_deactivated > 0 && (
              <p className={styles.warning} role="alert">
                <AlertTriangle size={15} aria-hidden="true" />
                Vas a marcar sin stock <strong>{counts.listings_deactivated}</strong> productos
                que el archivo no menciona. Revisá que la planilla sea tu catálogo completo.
              </p>
            )}

            {preview.truncated && (
              <p className={styles.warning}>
                <AlertTriangle size={15} aria-hidden="true" />
                El archivo es muy largo y se leyó solo la primera parte. Subí el resto en otra tanda.
              </p>
            )}

            <div className={styles.sheetLine}>
              <span>
                Hoja <strong>{preview.sheet_name}</strong>, encabezados en la fila{' '}
                <strong>{preview.header_row}</strong>
              </span>
              {preview.sheet_names.length > 1 && (
                <select
                  className={styles.selectSmall}
                  value={preview.sheet_name}
                  onChange={(e) => changeSheet(e.target.value)}
                  aria-label="Elegir otra hoja del archivo"
                >
                  {preview.sheet_names.map((name) => (
                    <option key={name} value={name}>{name}</option>
                  ))}
                </select>
              )}
            </div>

            <div className={styles.mapping}>
              <p className={styles.blockTitle}>Columnas</p>
              <p className={styles.help}>
                Si alguna quedó mal asignada, corregila acá. Volvemos a leer el archivo con tu
                corrección antes de guardar nada.
              </p>
              <div className={styles.mappingGrid}>
                {Object.entries(FIELD_LABELS).map(([fieldName, label]) => (
                  <label key={fieldName} className={styles.mappingRow}>
                    <span className={styles.mappingLabel}>{label}</span>
                    <select
                      className={styles.selectSmall}
                      value={mapping[fieldName] ?? UNASSIGNED}
                      disabled={busy}
                      onChange={(e) => remap(fieldName, e.target.value)}
                    >
                      <option value={UNASSIGNED}>— sin asignar —</option>
                      {preview.columns.map((column) => (
                        <option key={column.index} value={column.index}>
                          {column.header || `Columna ${column.index + 1}`}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className={styles.blockTitle}>Muestra del archivo</p>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th scope="col">Fila</th>
                      <th scope="col">Qué pasa</th>
                      <th scope="col">Producto</th>
                      <th scope="col">Precio</th>
                      <th scope="col">Stock</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.sample.map((row) => (
                      <tr key={row.row}>
                        <td>{row.row}</td>
                        <td>
                          <span className={`${styles.tag} ${styles[`tag_${row.action}`]}`}>
                            {ACTION_LABELS[row.action]}
                          </span>
                        </td>
                        <td>
                          <span className={styles.cellName}>
                            {row.name || row.matched_product_name || '—'}
                          </span>
                          {(row.ean || row.message) && (
                            <span className={styles.cellMeta}>
                              {row.message || row.ean}
                            </span>
                          )}
                        </td>
                        <td>{row.price != null ? formatPrice(row.price) : '—'}</td>
                        <td>{row.stock_quantity ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className={styles.actions}>
              <Button variant="secondary" onClick={() => setStep(STEP_FILE)} disabled={busy}>
                <ArrowLeft size={15} aria-hidden="true" />
                Volver
              </Button>
              <Button onClick={confirm} disabled={busy || willWrite === 0}>
                {busy ? 'Importando…' : `Importar ${willWrite} producto${willWrite === 1 ? '' : 's'}`}
              </Button>
            </div>
          </div>
        )}

        {step === STEP_RESULT && result && (
          <div className={styles.body}>
            <p className={styles.done}>
              <CheckCircle2 size={18} aria-hidden="true" />
              Importamos <strong>{result.counts.listings_updated}</strong> actualizaciones y{' '}
              <strong>{result.counts.listings_created}</strong> altas
              {result.counts.listings_deactivated > 0 && (
                <>, y marcamos sin stock <strong>{result.counts.listings_deactivated}</strong></>
              )}
              .
            </p>

            {result.issues.length > 0 && (
              <div>
                <p className={styles.blockTitle}>
                  Filas que no entraron ({result.counts.rows_failed + result.counts.rows_skipped})
                </p>
                <ul className={styles.issues}>
                  {result.issues.map((issue, index) => (
                    <li key={`${issue.row}-${index}`}>
                      <strong>Fila {issue.row}</strong>
                      {issue.column ? ` · ${issue.column}` : ''} — {issue.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className={styles.actions}>
              <Button onClick={onImported}>Ver mi catálogo</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
