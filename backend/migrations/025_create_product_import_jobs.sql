-- Qué pasó en cada importación de catálogo.
--
-- Una importación toca cientos o miles de filas de precios y stock de una sola
-- vez. Cuando el lunes un producto aparece a un precio raro o desaparecido de
-- la góndola virtual, la pregunta es "¿quién subió qué archivo y qué hizo esa
-- corrida?". Sin esta tabla la respuesta no existe: price_history (016) guarda
-- el precio anterior pero no de dónde vino el nuevo.
--
-- Es el mismo criterio que order_status_log y chain_verification_log, y entra
-- en la tabla de SEGURIDAD.md §10.1: append-only, nunca se actualiza ni se
-- borra una fila.

CREATE TABLE product_import_jobs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chain_id         UUID NOT NULL REFERENCES chains(id) ON DELETE CASCADE,
  supermarket_id   UUID NOT NULL REFERENCES supermarkets(id) ON DELETE CASCADE,
  -- ON DELETE SET NULL: si el empleado se da de baja, la corrida sobrevive.
  -- Un log de auditoría que se borra con su autor no es un log de auditoría.
  created_by       UUID REFERENCES supermarket_users(id) ON DELETE SET NULL,

  file_name        TEXT NOT NULL,
  sheet_name       TEXT,
  -- El mapeo columna -> campo con el que se leyó el archivo. Es lo que explica
  -- por qué una corrida interpretó "IMPORTE" como precio: sin esto, un mapeo
  -- automático equivocado es irreproducible.
  column_mapping   JSONB NOT NULL DEFAULT '{}'::jsonb,

  rows_total       INTEGER NOT NULL DEFAULT 0,
  listings_created INTEGER NOT NULL DEFAULT 0,
  listings_updated INTEGER NOT NULL DEFAULT 0,
  products_created INTEGER NOT NULL DEFAULT 0,
  rows_skipped     INTEGER NOT NULL DEFAULT 0,
  rows_failed      INTEGER NOT NULL DEFAULT 0,
  -- Muestra acotada de los problemas ([{row, column, message}]). El servicio la
  -- topea antes de escribir: un archivo entero mal mapeado no puede convertir
  -- una fila de auditoría en un volcado de megabytes.
  issues           JSONB NOT NULL DEFAULT '[]'::jsonb,

  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT import_counts_not_negative CHECK (
    rows_total >= 0 AND listings_created >= 0 AND listings_updated >= 0
    AND products_created >= 0 AND rows_skipped >= 0 AND rows_failed >= 0
  )
);

-- La consulta natural es "las últimas importaciones de mi cadena".
CREATE INDEX idx_import_jobs_chain    ON product_import_jobs(chain_id, created_at DESC);
-- FK con índice, NORMAS.md §5.1.
CREATE INDEX idx_import_jobs_store    ON product_import_jobs(supermarket_id);
CREATE INDEX idx_import_jobs_author   ON product_import_jobs(created_by);


ALTER TABLE product_import_jobs ENABLE ROW LEVEL SECURITY;

-- El staff lee el historial de SU cadena. Cualquier rol: ver qué se importó es
-- lectura del catálogo propio, y la matriz de SEGURIDAD.md §4.2 le da lectura
-- de precios hasta al rol 'staff'. Escribir, importar y en general operar
-- sigue siendo de manager/owner y lo resuelve el backend.
CREATE POLICY "import_jobs_select_own_chain"
  ON product_import_jobs FOR SELECT TO authenticated
  USING (chain_id = public.current_staff_chain_id());

-- Sin policies de INSERT/UPDATE/DELETE, ni para authenticated ni para anon:
-- las filas las escribe solo el backend (service_role) al terminar una corrida,
-- y no las edita nadie nunca.
