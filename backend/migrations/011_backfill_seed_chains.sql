-- Adopta los supermercados que ya existen (los 3 del seed 007) bajo una cadena
-- cada uno, para poder poner supermarkets.chain_id en NOT NULL.
--
-- Se resuelve de forma genérica sobre "todo supermarket sin chain_id" en vez de
-- nombrar Carrefour/Vital/Jaguar a mano: así funciona igual si alguien cargó
-- otro supermercado a mano antes de correr esto.

-- Los CUIT son placeholders con formato válido (11 dígitos, prefijo 30 de
-- persona jurídica) porque los datos reales no los tenemos: estas cadenas son
-- de demo. Al aprobar una cadena real, el CUIT llega por el registro.
WITH orphans AS (
  SELECT id, name, address,
         ROW_NUMBER() OVER (ORDER BY created_at, name) AS n
  FROM supermarkets
  WHERE chain_id IS NULL
),
created AS (
  INSERT INTO chains (legal_name, trade_name, tax_id, contact_email, status, reviewed_at)
  SELECT
    o.name || ' S.A.',
    o.name,
    '30' || LPAD(o.n::TEXT, 9, '0'),
    LOWER(REGEXP_REPLACE(o.name, '[^a-zA-Z0-9]', '', 'g')) || '@example.com',
    'approved',
    NOW()
  FROM orphans o
  RETURNING id, trade_name
)
UPDATE supermarkets s
SET chain_id = c.id
FROM created c
WHERE s.chain_id IS NULL AND s.name = c.trade_name;


-- Descomponer el `address` del seed ('Av. Rivadavia 1234, CABA') en los campos
-- estructurados. Solo para las filas que todavía no los tienen.
UPDATE supermarkets
SET street = TRIM(SPLIT_PART(address, ',', 1)),
    city   = NULLIF(TRIM(SPLIT_PART(address, ',', 2)), '')
WHERE street IS NULL AND address IS NOT NULL;


-- Horario por defecto para las sucursales de demo: lunes a sábado 8-21.
-- Sin esto, la validación de pickup_scheduled contra store_hours rechazaría
-- todos los pedidos de los supermercados del seed.
INSERT INTO store_hours (supermarket_id, weekday, opens_at, closes_at)
SELECT s.id, d.weekday, TIME '08:00', TIME '21:00'
FROM supermarkets s
CROSS JOIN (SELECT generate_series(1, 6) AS weekday) d
WHERE NOT EXISTS (
  SELECT 1 FROM store_hours sh WHERE sh.supermarket_id = s.id AND sh.weekday = d.weekday
);


-- Recién ahora se puede exigir la cadena: toda sucursal pertenece a una.
ALTER TABLE supermarkets ALTER COLUMN chain_id SET NOT NULL;
