CREATE TABLE orders (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES auth.users(id),
  supermarket_id   UUID NOT NULL REFERENCES supermarkets(id),
  list_id          UUID REFERENCES shopping_lists(id) ON DELETE SET NULL,
  status           TEXT NOT NULL DEFAULT 'pending',
  pickup_scheduled TIMESTAMPTZ NOT NULL,
  total_price      INTEGER,
  notes            TEXT,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);
-- status: 'pending' | 'confirmed' | 'preparing' | 'ready' | 'completed' | 'cancelled'
-- list_id usa ON DELETE SET NULL (a diferencia del DDL original en
-- ARQUITECTURA.md, que no especifica acción): sin esto, borrar una lista que
-- ya generó un pedido fallaría con un error de FK. El pedido histórico debe
-- sobrevivir al borrado de la lista que le dio origen.

CREATE TABLE order_items (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id   UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  quantity   NUMERIC(10,2) NOT NULL,
  unit_price INTEGER NOT NULL,
  subtotal   INTEGER NOT NULL
);

CREATE TABLE order_status_log (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id   UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  status     TEXT NOT NULL,
  changed_by UUID REFERENCES auth.users(id),
  note       TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_status_log ENABLE ROW LEVEL SECURITY;

-- Solo SELECT. Ninguna policy de INSERT/UPDATE/DELETE para authenticated:
-- toda escritura pasa exclusivamente por el backend (service_role) a través
-- de las funciones RPC de 006. Así, aunque alguien obtenga la anon key y un
-- JWT válido, no puede falsificar pedidos ni alterar su estado directo contra
-- la API de Supabase.
CREATE POLICY "orders_select_own" ON orders FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "order_items_select_own" ON order_items FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM orders WHERE orders.id = order_items.order_id AND orders.user_id = auth.uid()));
CREATE POLICY "order_status_log_select_own" ON order_status_log FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM orders WHERE orders.id = order_status_log.order_id AND orders.user_id = auth.uid()));
