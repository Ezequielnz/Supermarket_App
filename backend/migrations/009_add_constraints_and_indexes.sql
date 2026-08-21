-- Integridad, índices y auditoría sobre el esquema que ya existía. Todo esto
-- debería haber estado desde 003-005; se agrega ahora, antes de que haya datos
-- reales, porque después cada CHECK requiere limpiar filas que ya lo violan.

-- ── 1. CHECKs de dominio ──────────────────────────────────────────────────
-- Nada impedía un precio negativo o una cantidad cero. Un subtotal negativo
-- baja el total del pedido: es un descuento arbitrario disfrazado de dato.
ALTER TABLE supermarket_products
  ADD CONSTRAINT price_positive CHECK (price > 0);

ALTER TABLE order_items
  ADD CONSTRAINT unit_price_positive CHECK (unit_price > 0),
  ADD CONSTRAINT order_item_quantity_positive CHECK (quantity > 0),
  ADD CONSTRAINT subtotal_positive CHECK (subtotal > 0);

ALTER TABLE shopping_list_items
  ADD CONSTRAINT list_item_quantity_positive CHECK (quantity > 0);

ALTER TABLE orders
  ADD CONSTRAINT total_price_positive CHECK (total_price IS NULL OR total_price > 0);

-- Un producto repetido en la misma lista rompe la comparación (lo cuenta dos
-- veces). La cantidad es el campo para pedir más de uno.
ALTER TABLE shopping_list_items
  ADD CONSTRAINT unique_product_per_list UNIQUE (list_id, product_id);


-- ── 2. Índices ────────────────────────────────────────────────────────────
-- Postgres NO crea índices en las foreign keys automáticamente (sí en las PK).
-- Todas estas columnas se filtran en cada request del flujo del consumidor.
CREATE INDEX idx_orders_user_id            ON orders(user_id);
CREATE INDEX idx_order_items_order_id      ON order_items(order_id);
CREATE INDEX idx_order_status_log_order_id ON order_status_log(order_id);
CREATE INDEX idx_shopping_lists_user_id    ON shopping_lists(user_id);
CREATE INDEX idx_list_items_list_id        ON shopping_list_items(list_id);
CREATE INDEX idx_sp_product_id             ON supermarket_products(product_id);

-- Índice compuesto para el panel del supermercado (ARQUITECTURA.md §5.3:
-- "pedidos ordenados por hora de retiro"). El orden de las columnas importa:
-- igualdad primero, rango al final.
CREATE INDEX idx_orders_supermarket_status
  ON orders(supermarket_id, status, pickup_scheduled);

-- product_service.list_products usa ilike("name", "%q%"). Un LIKE con comodín
-- inicial no puede usar un B-tree: sin esto es siempre un seq scan de toda la
-- tabla de productos.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_products_name_trgm ON products USING GIN (name gin_trgm_ops);


-- ── 3. Columnas de auditoría faltantes ────────────────────────────────────
-- NORMAS.md §5.1 exige created_at en toda tabla principal; products y
-- order_items nunca lo tuvieron.
ALTER TABLE products
  ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE order_items
  ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Las columnas existentes se endurecen: un created_at nulo no sirve para nada.
ALTER TABLE profiles             ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE supermarkets         ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE shopping_lists       ALTER COLUMN created_at SET NOT NULL,
                                 ALTER COLUMN updated_at SET NOT NULL;
ALTER TABLE orders               ALTER COLUMN created_at SET NOT NULL,
                                 ALTER COLUMN updated_at SET NOT NULL;
ALTER TABLE order_status_log     ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE supermarket_products ALTER COLUMN updated_at SET NOT NULL;


-- ── 4. updated_at automático ──────────────────────────────────────────────
-- Hasta ahora orders.updated_at solo se refrescaba dentro de cancel_order:
-- cualquier otro UPDATE (por ejemplo el cambio de estado que hará el panel del
-- supermercado) dejaba la columna mintiendo.
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER set_updated_at_orders
  BEFORE UPDATE ON orders
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER set_updated_at_shopping_lists
  BEFORE UPDATE ON shopping_lists
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER set_updated_at_supermarket_products
  BEFORE UPDATE ON supermarket_products
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER set_updated_at_products
  BEFORE UPDATE ON products
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- ── 5. Número de pedido legible ───────────────────────────────────────────
-- ARQUITECTURA.md §5.3 dice que el super ve el "Numero" del pedido. Un UUID no
-- se canta en el mostrador. La secuencia arranca en 1000 para que el primer
-- pedido no sea el #1.
CREATE SEQUENCE order_number_seq START 1000;
ALTER TABLE orders
  ADD COLUMN order_number BIGINT NOT NULL DEFAULT nextval('order_number_seq');
ALTER TABLE orders ADD CONSTRAINT order_number_unique UNIQUE (order_number);
