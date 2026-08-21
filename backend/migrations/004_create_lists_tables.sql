CREATE TABLE shopping_lists (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name       TEXT NOT NULL DEFAULT 'Mi lista',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE shopping_list_items (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  list_id    UUID NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  quantity   NUMERIC(10,2) NOT NULL DEFAULT 1,
  note       TEXT
);

ALTER TABLE shopping_lists ENABLE ROW LEVEL SECURITY;
ALTER TABLE shopping_list_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "shopping_lists_select_own" ON shopping_lists FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "shopping_lists_insert_own" ON shopping_lists FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "shopping_lists_update_own" ON shopping_lists FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "shopping_lists_delete_own" ON shopping_lists FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- shopping_list_items no tiene user_id propio: ownership vía la lista padre.
CREATE POLICY "shopping_list_items_select_own" ON shopping_list_items FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM shopping_lists WHERE shopping_lists.id = shopping_list_items.list_id AND shopping_lists.user_id = auth.uid()));
CREATE POLICY "shopping_list_items_insert_own" ON shopping_list_items FOR INSERT TO authenticated
  WITH CHECK (EXISTS (SELECT 1 FROM shopping_lists WHERE shopping_lists.id = shopping_list_items.list_id AND shopping_lists.user_id = auth.uid()));
CREATE POLICY "shopping_list_items_update_own" ON shopping_list_items FOR UPDATE TO authenticated
  USING (EXISTS (SELECT 1 FROM shopping_lists WHERE shopping_lists.id = shopping_list_items.list_id AND shopping_lists.user_id = auth.uid()))
  WITH CHECK (EXISTS (SELECT 1 FROM shopping_lists WHERE shopping_lists.id = shopping_list_items.list_id AND shopping_lists.user_id = auth.uid()));
CREATE POLICY "shopping_list_items_delete_own" ON shopping_list_items FOR DELETE TO authenticated
  USING (EXISTS (SELECT 1 FROM shopping_lists WHERE shopping_lists.id = shopping_list_items.list_id AND shopping_lists.user_id = auth.uid()));
