-- Reemplaza las columnas de texto libre por tipos enumerados. Hasta ahora nada
-- impedía escribir orders.status = 'lsito': la app quedaba con un pedido en un
-- estado que ningún código sabe manejar, y sin forma de detectarlo desde la DB.
-- Los enums mueven esa validación al único lugar que no se puede saltear.

CREATE TYPE order_status AS ENUM (
  'pending', 'confirmed', 'preparing', 'ready', 'completed', 'cancelled'
);

CREATE TYPE chain_status AS ENUM (
  'pending_review', 'approved', 'rejected', 'suspended'
);

CREATE TYPE staff_role AS ENUM ('owner', 'manager', 'staff');

CREATE TYPE product_unit AS ENUM ('kg', 'g', 'L', 'ml', 'un');


-- orders.status tiene DEFAULT 'pending', que hay que soltar antes de cambiar el
-- tipo y volver a poner después (Postgres no puede recastear un default en el
-- medio de un ALTER TYPE).
ALTER TABLE orders ALTER COLUMN status DROP DEFAULT;
ALTER TABLE orders ALTER COLUMN status TYPE order_status USING status::order_status;
ALTER TABLE orders ALTER COLUMN status SET DEFAULT 'pending';

ALTER TABLE order_status_log
  ALTER COLUMN status TYPE order_status USING status::order_status;

ALTER TABLE products
  ALTER COLUMN unit TYPE product_unit USING unit::product_unit;


-- currency: de TEXT libre a CHAR(3) con formato ISO 4217 verificado.
ALTER TABLE supermarket_products ALTER COLUMN currency DROP DEFAULT;
ALTER TABLE supermarket_products
  ALTER COLUMN currency TYPE CHAR(3) USING UPPER(TRIM(currency))::CHAR(3);
ALTER TABLE supermarket_products ALTER COLUMN currency SET DEFAULT 'ARS';
ALTER TABLE supermarket_products ALTER COLUMN currency SET NOT NULL;
ALTER TABLE supermarket_products
  ADD CONSTRAINT currency_iso4217 CHECK (currency ~ '^[A-Z]{3}$');


-- Las funciones de 006 insertan los literales 'pending' y 'cancelled' en
-- orders.status y order_status_log.status. Postgres castea el literal al enum
-- automáticamente, así que create_order_with_items y cancel_order siguen
-- funcionando sin cambios.
