import { apiClient } from './api'

// Catálogo propio: los productos que esta cadena vende y a qué precio.
//
// Los precios viajan en centavos como enteros; la conversión desde/hacia pesos
// la hace lib/money.js en el punto donde el usuario los escribe o los lee.

export async function getMyProducts({ supermarketId, q, page = 1, per_page = 20 } = {}) {
  const params = new URLSearchParams({ page, per_page })
  if (supermarketId) params.set('supermarket_id', supermarketId)
  if (q) params.set('q', q)
  return apiClient.get(`/supermarkets/me/products?${params.toString()}`, { auth: true })
}

// Busca en el catálogo GLOBAL antes de crear, para vincular en vez de duplicar.
// Un producto duplicado no se compara contra el de las otras cadenas: son dos
// product_id distintos y el comparador los trata como productos diferentes.
export async function lookupProduct({ ean, q, supermarketId } = {}) {
  const params = new URLSearchParams()
  if (ean) params.set('ean', ean)
  if (q) params.set('q', q)
  if (supermarketId) params.set('supermarket_id', supermarketId)
  return apiClient.get(`/supermarkets/me/products/lookup?${params.toString()}`, { auth: true })
}

// `product_id` para vincular a un producto global existente, o `product` (el
// borrador) para proponer uno nuevo. El backend rechaza mandar los dos.
export async function createMyProduct({ supermarketId, price, inStock = true, productId, product }) {
  return apiClient.post(
    '/supermarkets/me/products',
    {
      supermarket_id: supermarketId,
      price,
      in_stock: inStock,
      product_id: productId ?? undefined,
      product: product ?? undefined,
    },
    { auth: true },
  )
}

export async function updateMyProduct(listingId, { price, inStock }) {
  return apiClient.patch(
    `/supermarkets/me/products/${listingId}`,
    { price, in_stock: inStock },
    { auth: true },
  )
}

export async function deleteMyProduct(listingId) {
  return apiClient.delete(`/supermarkets/me/products/${listingId}`, { auth: true })
}
