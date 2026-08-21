-- Historial de precios y enriquecimiento del catálogo global.
--
-- Por qué ahora y no cuando se necesite: supermarket_products SOBRESCRIBE el
-- precio en cada update. La app ya le promete al usuario "Historial y
-- tendencias de precios" (AuthPage.jsx), y ese dato no se puede reconstruir
-- después — cada actualización que ocurra sin esta tabla es información
-- perdida para siempre. Es el único cambio del esquema que tiene fecha de
-- vencimiento.

CREATE TABLE price_history (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supermarket_id UUID NOT NULL REFERENCES supermarkets(id) ON DELETE CASCADE,
  product_id     UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  price          INTEGER NOT NULL,
  currency       CHAR(3) NOT NULL,
  recorded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT history_price_positive CHECK (price > 0)
);

-- La consulta natural es "la serie de este producto en este super, del más
-- reciente al más viejo".
CREATE INDEX idx_price_history_lookup
  ON price_history(supermarket_id, product_id, recorded_at DESC);


-- Guarda el precio ANTERIOR, no el nuevo: el vigente siempre está en
-- supermarket_products. Así la serie histórica más la fila actual dan la
-- secuencia completa sin duplicar el valor de hoy.
CREATE OR REPLACE FUNCTION public.record_price_change()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF NEW.price IS DISTINCT FROM OLD.price THEN
    INSERT INTO public.price_history (supermarket_id, product_id, price, currency, recorded_at)
    VALUES (OLD.supermarket_id, OLD.product_id, OLD.price, OLD.currency, OLD.updated_at);
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER record_price_change_on_update
  AFTER UPDATE OF price ON supermarket_products
  FOR EACH ROW EXECUTE FUNCTION public.record_price_change();


ALTER TABLE price_history ENABLE ROW LEVEL SECURITY;

-- Lectura con el mismo criterio que los precios vigentes (015): solo cadenas
-- aprobadas. Sin policies de escritura para authenticated: la tabla la llena
-- exclusivamente el trigger.
CREATE POLICY "price_history_select_approved"
  ON price_history FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM supermarkets s
      JOIN chains c ON c.id = s.chain_id
      WHERE s.id = price_history.supermarket_id
        AND s.is_active
        AND c.status = 'approved'
    )
  );


-- ── Catálogo global ───────────────────────────────────────────────────────
-- El comparador depende de que "Leche entera 1L" de Carrefour y la de Vital
-- sean el MISMO product_id. Hoy eso se sostiene solo porque el seed los cargó
-- juntos; cuando cada cadena suba su catálogo hace falta una clave real de
-- machaco, y esa clave es el código de barras.
ALTER TABLE products
  ADD COLUMN ean        TEXT,
  ADD COLUMN size_value NUMERIC(10,3),
  ADD COLUMN size_unit  product_unit;

-- UNIQUE pero nullable: los productos sin EAN (frutas, verduras, fiambrería a
-- granel) conviven con los envasados. En Postgres los NULL no colisionan entre
-- sí en un índice único.
CREATE UNIQUE INDEX idx_products_ean ON products(ean) WHERE ean IS NOT NULL;

ALTER TABLE products
  ADD CONSTRAINT ean_format CHECK (ean IS NULL OR ean ~ '^[0-9]{8,14}$'),
  ADD CONSTRAINT size_value_positive CHECK (size_value IS NULL OR size_value > 0);
