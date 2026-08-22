import { createContext, useCallback, useEffect, useState } from 'react'

import { useAuth } from '../hooks/useAuth'
import * as cartService from '../services/cart.service'

export const CartContext = createContext(null)

// El carrito lo comparten tres cosas que tienen que moverse juntas: la
// pantalla de explorar (que agrega), el drawer (que edita) y el badge del
// contador. Sin un estado compartido, agregar un producto actualizaría una
// sola de las tres hasta recargar la página.
//
// Es la excepción de NORMAS.md §3.6 al "Context solo para sesión": el carrito
// es estado de sesión del usuario, vive en el backend y lo leen componentes
// que no comparten un padre común.

export function CartProvider({ children }) {
  const { user } = useAuth()

  const [cart, setCart] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(false)

  const refresh = useCallback(async () => {
    if (!user) {
      setCart(null)
      return null
    }
    setLoading(true)
    try {
      const fresh = await cartService.getCart()
      setCart(fresh)
      setError(null)
      return fresh
    } catch (err) {
      setError(err.message || 'No pudimos cargar tu carrito.')
      return null
    } finally {
      setLoading(false)
    }
  }, [user])

  // GET /lists/cart crea el carrito si no existe, así que esto no se dispara
  // hasta que hay sesión: sin usuario no hay a quién crearle nada.
  useEffect(() => {
    if (user) refresh()
    else setCart(null)
  }, [user, refresh])

  async function addProduct(productId, quantity = 1) {
    await cartService.addToCart({ productId, quantity })
    return refresh()
  }

  async function setQuantity(itemId, quantity) {
    if (!cart) return
    await cartService.setItemQuantity(cart.id, itemId, quantity)
    return refresh()
  }

  async function removeItem(itemId) {
    if (!cart) return
    await cartService.removeCartItem(cart.id, itemId)
    return refresh()
  }

  async function saveAsList(name) {
    const saved = await cartService.saveCartAsList({ name })
    await refresh()
    return saved
  }

  const items = cart?.items ?? []
  // Cuántas líneas distintas, no cuántas unidades: es lo que espera ver quien
  // agregó tres productos, aunque de uno lleve dos.
  const count = items.length

  const value = {
    cart,
    items,
    count,
    loading,
    error,
    open,
    openCart: () => setOpen(true),
    closeCart: () => setOpen(false),
    refresh,
    addProduct,
    setQuantity,
    removeItem,
    saveAsList,
  }

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>
}
