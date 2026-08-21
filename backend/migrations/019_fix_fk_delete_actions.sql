-- Ninguna de estas foreign keys declaraba acción de borrado, así que quedaron
-- en NO ACTION por default. Se detectó al intentar borrar una cadena de prueba:
--
--   ERROR: update or delete on table "supermarkets" violates foreign key
--   constraint "supermarket_products_supermarket_id_fkey"
--
-- El ON DELETE CASCADE de `supermarkets.chain_id -> chains` prometía un borrado
-- en cascada que no podía completarse nunca: al llegar a supermarket_products
-- se frenaba. Una cadena rechazada que quisiera darse de baja quedaba trabada.
--
-- Es el mismo tipo de omisión que 005 ya había corregido para orders.list_id.
-- La decisión no es "cascada en todo": cada FK expresa una regla de negocio
-- distinta, y las de abajo están elegidas una por una.


-- ── Se borran con su padre ────────────────────────────────────────────────
-- Un precio solo existe en el contexto de la sucursal y del producto: sin
-- alguno de los dos no significa nada.
ALTER TABLE supermarket_products
  DROP CONSTRAINT supermarket_products_supermarket_id_fkey,
  ADD  CONSTRAINT supermarket_products_supermarket_id_fkey
       FOREIGN KEY (supermarket_id) REFERENCES supermarkets(id) ON DELETE CASCADE;

ALTER TABLE supermarket_products
  DROP CONSTRAINT supermarket_products_product_id_fkey,
  ADD  CONSTRAINT supermarket_products_product_id_fkey
       FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE;

-- Un ítem de lista referido a un producto que ya no está en el catálogo es
-- basura que rompe la comparación.
ALTER TABLE shopping_list_items
  DROP CONSTRAINT shopping_list_items_product_id_fkey,
  ADD  CONSTRAINT shopping_list_items_product_id_fkey
       FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE;


-- ── Se conservan aunque desaparezca el referido ───────────────────────────
-- El autor de un cambio de estado puede darse de baja; el registro de auditoría
-- tiene que sobrevivir. Se pierde quién fue, no que pasó.
ALTER TABLE order_status_log
  DROP CONSTRAINT order_status_log_changed_by_fkey,
  ADD  CONSTRAINT order_status_log_changed_by_fkey
       FOREIGN KEY (changed_by) REFERENCES auth.users(id) ON DELETE SET NULL;


-- ── Bloquean el borrado a propósito ───────────────────────────────────────
-- Estas se dejan explícitas como RESTRICT en vez de NO ACTION. El efecto es
-- casi el mismo, pero declarado: quien lea el esquema ve que la restricción es
-- deliberada y no un default que nadie eligió.
--
-- orders.user_id y orders.supermarket_id: un pedido es un comprobante con valor
-- fiscal y contable para el supermercado. No puede desaparecer porque el
-- cliente se dé de baja ni porque la sucursal cierre. La baja de un consumidor
-- se resuelve anonimizando, no borrando (docs/SEGURIDAD.md §12.5).
--
-- order_items.product_id: el detalle de lo que se vendió no se altera al sacar
-- un producto del catálogo.
ALTER TABLE orders
  DROP CONSTRAINT orders_user_id_fkey,
  ADD  CONSTRAINT orders_user_id_fkey
       FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE RESTRICT;

ALTER TABLE orders
  DROP CONSTRAINT orders_supermarket_id_fkey,
  ADD  CONSTRAINT orders_supermarket_id_fkey
       FOREIGN KEY (supermarket_id) REFERENCES supermarkets(id) ON DELETE RESTRICT;

ALTER TABLE order_items
  DROP CONSTRAINT order_items_product_id_fkey,
  ADD  CONSTRAINT order_items_product_id_fkey
       FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT;


-- Consecuencia buscada: una cadena SIN pedidos se puede borrar entera en
-- cascada (útil para purgar registros rechazados o de prueba), y una cadena CON
-- pedidos no se puede borrar. Para sacarla de circulación está el estado
-- 'suspended', que la oculta del comparador sin tocar el histórico.
