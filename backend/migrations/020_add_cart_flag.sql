-- El carrito ES una lista de compras, no una tabla nueva.
--
-- Una tabla `carts` sería un duplicado exacto de shopping_lists y forkearía el
-- camino al checkout en dos, cuando el que ya existe funciona de punta a punta
-- (lista -> /lists/{id}/compare -> checkout -> orders). Lo único que faltaba
-- era la noción de "cuál de mis listas es el carrito activo", y eso es una
-- columna.
--
-- Ver docs/PLAN_CATALOGO_Y_CARRITO.md §2.1.

ALTER TABLE shopping_lists
  ADD COLUMN is_cart BOOLEAN NOT NULL DEFAULT FALSE;

-- Un solo carrito por usuario. Índice parcial: las listas guardadas
-- (is_cart = false) no entran al índice, así que un usuario puede tener todas
-- las que quiera. Mismo patrón que idx_one_owner_per_chain de la 012.
CREATE UNIQUE INDEX idx_one_cart_per_user
  ON shopping_lists(user_id) WHERE is_cart;

-- GET /lists filtra por is_cart = false para no mezclar el carrito entre las
-- listas guardadas; el índice de user_id de la 009 ya cubre esa consulta.

COMMENT ON COLUMN shopping_lists.is_cart IS
  'Carrito activo del usuario. Uno solo por usuario (idx_one_cart_per_user). POST /lists/cart/save lo pasa a false y la lista queda guardada.';
