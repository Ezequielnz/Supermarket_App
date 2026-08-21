-- Separa la CADENA (la empresa: "Carrefour") de la SUCURSAL (el local:
-- "Carrefour Rivadavia 1234"). `supermarkets` ya tenía `address`, o sea que
-- funcionalmente ya era una sucursal; lo que faltaba era la entidad de arriba.
--
-- Se agrega `chains` POR ENCIMA en vez de renombrar `supermarkets` a `stores`:
-- el modelo resultante es el mismo, pero no hay que tocar los ~60 usos de
-- `supermarket` del backend ni los del front del consumidor, que hoy funcionan
-- y están testeados. orders.supermarket_id sigue apuntando al local donde se
-- retira, que es exactamente lo que significa.

CREATE EXTENSION IF NOT EXISTS citext;


CREATE TABLE chains (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  legal_name       TEXT NOT NULL,          -- razón social
  trade_name       TEXT NOT NULL,          -- nombre comercial: el que ve el consumidor
  tax_id           TEXT NOT NULL,          -- CUIT
  contact_email    CITEXT NOT NULL,        -- CITEXT: los correos no distinguen mayúsculas
  contact_phone    TEXT,
  logo_url         TEXT,
  status           chain_status NOT NULL DEFAULT 'pending_review',
  rejection_reason TEXT,
  reviewed_by      UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  reviewed_at      TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT tax_id_unique  UNIQUE (tax_id),
  CONSTRAINT tax_id_format  CHECK (tax_id ~ '^[0-9]{11}$'),
  -- Rechazar sin explicar por qué deja al supermercado sin nada que corregir.
  CONSTRAINT rejected_needs_reason
    CHECK (status <> 'rejected' OR rejection_reason IS NOT NULL)
);

CREATE INDEX idx_chains_status ON chains(status);

CREATE TRIGGER set_updated_at_chains
  BEFORE UPDATE ON chains
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- ── supermarkets pasa a ser la sucursal ───────────────────────────────────
-- La dirección estructurada reemplaza al `address TEXT`, que no permite filtrar
-- por ciudad ni ordenar por cercanía. `address` se conserva como texto de
-- display y lo mantiene el backend a partir de los campos nuevos.
ALTER TABLE supermarkets
  ADD COLUMN chain_id    UUID REFERENCES chains(id) ON DELETE CASCADE,
  ADD COLUMN street      TEXT,
  ADD COLUMN city        TEXT,
  ADD COLUMN province    TEXT,
  ADD COLUMN postal_code TEXT,
  ADD COLUMN latitude    NUMERIC(9,6),
  ADD COLUMN longitude   NUMERIC(9,6),
  ADD COLUMN phone       TEXT,
  ADD COLUMN updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- chain_id queda NULLABLE acá a propósito: los 3 supermercados del seed 007 no
-- tienen cadena todavía. La migración 011 los adopta y recién ahí lo pone
-- NOT NULL.

ALTER TABLE supermarkets
  ADD CONSTRAINT latitude_range  CHECK (latitude  IS NULL OR latitude  BETWEEN  -90 AND  90),
  ADD CONSTRAINT longitude_range CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180);

CREATE INDEX idx_supermarkets_chain_id ON supermarkets(chain_id);
CREATE INDEX idx_supermarkets_city     ON supermarkets(city);

CREATE TRIGGER set_updated_at_supermarkets
  BEFORE UPDATE ON supermarkets
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- ── Horarios de atención ──────────────────────────────────────────────────
-- No es adorno: es lo que permite validar orders.pickup_scheduled. Hoy se
-- acepta cualquier fecha, incluida una pasada o las 3 de la mañana.
CREATE TABLE store_hours (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supermarket_id UUID NOT NULL REFERENCES supermarkets(id) ON DELETE CASCADE,
  weekday        SMALLINT NOT NULL,   -- 0 = domingo, 6 = sábado (compatible con EXTRACT(DOW))
  opens_at       TIME NOT NULL,
  closes_at      TIME NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT weekday_range     CHECK (weekday BETWEEN 0 AND 6),
  CONSTRAINT closes_after_opens CHECK (closes_at > opens_at),
  CONSTRAINT one_range_per_weekday UNIQUE (supermarket_id, weekday)
);

CREATE INDEX idx_store_hours_supermarket ON store_hours(supermarket_id);


-- ── RLS ───────────────────────────────────────────────────────────────────
ALTER TABLE chains      ENABLE ROW LEVEL SECURITY;
ALTER TABLE store_hours ENABLE ROW LEVEL SECURITY;

-- El consumidor necesita ver el nombre y los horarios del super donde retira.
-- Solo cadenas aprobadas: una cadena en revisión no existe para el consumidor.
CREATE POLICY "chains_select_approved"
  ON chains FOR SELECT TO authenticated
  USING (status = 'approved');

CREATE POLICY "store_hours_select_authenticated"
  ON store_hours FOR SELECT TO authenticated
  USING (true);

-- Sin policies de INSERT/UPDATE/DELETE para authenticated en ninguna de las
-- dos: toda escritura pasa por el backend (service_role), igual que orders.
