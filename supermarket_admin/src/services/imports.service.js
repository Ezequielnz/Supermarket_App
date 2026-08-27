import { apiClient } from './api'

// Importación de catálogo desde la planilla del ERP.
//
// El archivo se sube DOS veces: una para la vista previa y otra para
// confirmar. Es a propósito. La alternativa —guardar el archivo en el servidor
// entre los dos pasos— obliga a un almacén temporal, a limpiarlo y a decidir
// qué pasa si el usuario nunca confirma. Subirlo de nuevo cuesta unos segundos
// y deja los dos endpoints sin estado, que es lo que hace que la vista previa
// no pueda escribir ni por accidente.

function importForm(file, { supermarketId, sheetName, headerRow, mapping, options = {} }) {
  const form = new FormData()
  form.append('file', file)
  form.append('supermarket_id', supermarketId)
  if (sheetName) form.append('sheet_name', sheetName)
  if (headerRow) form.append('header_row', String(headerRow))
  // El mapeo viaja como JSON dentro de un campo de texto: un multipart no
  // tiene forma de llevar un objeto anidado.
  if (mapping && Object.keys(mapping).length > 0) {
    form.append('mapping', JSON.stringify(mapping))
  }
  for (const [key, value] of Object.entries(options)) {
    form.append(key, String(value))
  }
  return form
}

// Qué entendió del archivo y qué haría con él. No escribe nada.
export async function previewProductImport(file, params) {
  return apiClient.upload(
    '/supermarkets/me/products/import/preview',
    importForm(file, params),
    { auth: true },
  )
}

// La corrida que sí escribe precios y stock.
export async function runProductImport(file, params) {
  return apiClient.upload(
    '/supermarkets/me/products/import',
    importForm(file, params),
    { auth: true },
  )
}

// Historial: qué archivo se subió, quién y qué hizo cada corrida.
export async function getProductImports({ page = 1, per_page = 10 } = {}) {
  const params = new URLSearchParams({ page, per_page })
  return apiClient.get(`/supermarkets/me/products/imports?${params.toString()}`, { auth: true })
}
