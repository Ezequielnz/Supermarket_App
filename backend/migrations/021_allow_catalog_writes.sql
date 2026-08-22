-- El supermercado carga su catálogo.
--
-- `products` es una tabla COMPARTIDA ENTRE COMPETIDORES: todos los precios de
-- "Leche entera 1L" cuelgan de la misma fila, y por eso el comparador funciona.
-- Que una cadena pueda escribirla es necesario (si no, no hay catálogo) y a la
-- vez es superficie de abuso: renombrar esa fila afectaría a los precios de
-- todos los demás.
--
-- Las reglas, que se aplican en catalog_service.py porque el backend usa
-- service_role y bypasea RLS (docs/SEGURIDAD.md §5.1):
--
--   * Una cadena PUEDE crear filas nuevas en products.
--   * Una cadena NO PUEDE editar ni borrar filas existentes de products. Si un
--     producto global está mal, lo corrige un admin de plataforma.
--   * Una cadena solo escribe supermarket_products de SUS sucursales.
--   * Solo cadenas aprobadas (require_approved_chain).
--
-- Ver docs/PLAN_CATALOGO_Y_CARRITO.md §5.2.

ALTER TABLE products
  ADD COLUMN created_by_chain_id UUID REFERENCES chains(id) ON DELETE SET NULL;

-- ON DELETE SET NULL y no CASCADE: si la cadena que introdujo el producto se
-- da de baja, el producto sobrevive. Los precios de las otras cadenas cuelgan
-- de esa fila, y el seed (007) no tiene cadena de origen — la columna es
-- auditoría de quién lo creó, no ownership.
CREATE INDEX idx_products_created_by_chain ON products(created_by_chain_id);

COMMENT ON COLUMN products.created_by_chain_id IS
  'Cadena que introdujo esta fila del catálogo global. Auditoría, no ownership: nadie edita ni borra un producto global por ser su creador. NULL para el seed de la 007.';

-- Deliberadamente SIN policies de INSERT/UPDATE/DELETE para authenticated ni
-- anon, ni en products ni en supermarket_products. Toda escritura del catálogo
-- sigue pasando por el backend, igual que orders. La 003 dejó el catálogo como
-- solo-lectura para los clientes y eso NO cambia: lo que cambia es que ahora
-- el backend tiene endpoints para escribirlo en nombre de una cadena aprobada.
