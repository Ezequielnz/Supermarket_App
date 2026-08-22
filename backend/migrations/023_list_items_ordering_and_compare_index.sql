-- Orden estable de los items de una lista, e indice del camino caliente del
-- comparador.
--
-- Las dos cosas van juntas porque las dos salen del mismo cambio de producto:
-- la comparacion pasa a dispararse sola al abrir la lista, en vez de esperar a
-- que el usuario apriete "Comparar precios".

-- ── (a) Orden estable ─────────────────────────────────────────────────────
--
-- shopping_list_items era la unica tabla principal sin timestamps, asi que
-- get_list_detail no tenia por que ordenar y consultaba sin ORDER BY.
-- PostgREST no garantiza ningun orden: la misma lista guardada mostraba sus
-- productos en una secuencia distinta en cada visita. Para una lista a la que
-- el usuario vuelve, eso se ve como si la lista cambiara sola.
--
-- Las filas que ya existen quedan todas con el mismo NOW(), asi que el orden
-- de lectura es ("created_at", "id"): el id es el desempate determinista.

ALTER TABLE shopping_list_items
  ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

COMMENT ON COLUMN shopping_list_items.created_at IS
  'Momento en que el producto entro a la lista. Es el criterio de orden de get_list_detail y compare_list, desempatado por id: sin el, PostgREST devuelve los items en orden no determinista.';

-- ── (b) Indice del comparador ─────────────────────────────────────────────
--
-- price_context y compare_list corren la misma consulta:
--   .in_("product_id", ids).eq("in_stock", True)
--
-- El idx_sp_product_id de la 009 cubre el .in_() pero no el filtro de stock.
-- Mientras la comparacion era un boton, esa consulta corria cuando el usuario
-- la pedia; ahora corre en cada apertura de lista. El indice parcial espeja la
-- consulta exacta: solo indexa las filas con stock, que son las unicas que el
-- comparador mira, y trae supermarket_id para resolver el agrupado.

CREATE INDEX idx_sp_product_in_stock
  ON supermarket_products (product_id, supermarket_id)
  WHERE in_stock;

COMMENT ON INDEX idx_sp_product_in_stock IS
  'Camino caliente del comparador: supermarket_products filtrado por product_id IN (...) AND in_stock. Parcial a proposito — las filas sin stock nunca entran a una comparacion.';

-- RLS: sin cambios. No hay tablas nuevas y las cuatro policies
-- shopping_list_items_*_own de la 004 cubren la columna nueva.
