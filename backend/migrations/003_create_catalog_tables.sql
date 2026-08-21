CREATE TABLE supermarkets (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  address    TEXT,
  logo_url   TEXT,
  is_active  BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE products (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name      TEXT NOT NULL,
  brand     TEXT,
  unit      TEXT,    -- 'kg' | 'L' | 'un' | 'g'
  category  TEXT,
  image_url TEXT
);

CREATE TABLE supermarket_products (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supermarket_id UUID NOT NULL REFERENCES supermarkets(id),
  product_id     UUID NOT NULL REFERENCES products(id),
  price          INTEGER NOT NULL,  -- centavos, evita float
  currency       TEXT DEFAULT 'ARS',
  in_stock       BOOLEAN DEFAULT TRUE,
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(supermarket_id, product_id)
);

ALTER TABLE supermarkets ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE supermarket_products ENABLE ROW LEVEL SECURITY;

-- Catálogo de solo lectura: cualquier usuario autenticado puede leer, nadie
-- (ni authenticated ni anon) puede escribir. Solo service_role escribe (hoy
-- vía la migración de seed, a futuro vía el panel de supermercado).
CREATE POLICY "supermarkets_select_authenticated"
  ON supermarkets FOR SELECT TO authenticated USING (true);
CREATE POLICY "products_select_authenticated"
  ON products FOR SELECT TO authenticated USING (true);
CREATE POLICY "supermarket_products_select_authenticated"
  ON supermarket_products FOR SELECT TO authenticated USING (true);
-- Deliberadamente NO hay policies de INSERT/UPDATE/DELETE para authenticated
-- ni anon en ninguna de las tres tablas.
