-- Datos de ejemplo para probar el flujo de punta a punta sin depender todavía
-- del panel de supermercado. Nombres reutilizados de la demo de LandingPage.jsx.
-- Jaguar deliberadamente sin "Aceite de oliva extra virgen 1L" para poder
-- probar el caso is_complete = false en GET /lists/{id}/compare.
WITH new_supermarkets AS (
  INSERT INTO supermarkets (name, address, is_active) VALUES
    ('Carrefour', 'Av. Rivadavia 1234, CABA', true),
    ('Vital',     'Av. Corrientes 4500, CABA', true),
    ('Jaguar',    'Av. Cabildo 2100, CABA', true)
  RETURNING id, name
),
new_products AS (
  INSERT INTO products (name, brand, unit, category) VALUES
    ('Leche entera 1L', NULL, 'L', 'lácteos'),
    ('Huevos L x12', NULL, 'un', 'huevos'),
    ('Pan de molde', NULL, 'un', 'panadería'),
    ('Aceite de oliva extra virgen 1L', NULL, 'L', 'almacén'),
    ('Aceite de girasol 1L', NULL, 'L', 'almacén'),
    ('Manteca 200g', NULL, 'g', 'lácteos')
  RETURNING id, name
)
INSERT INTO supermarket_products (supermarket_id, product_id, price, in_stock)
SELECT s.id, p.id, v.price, v.in_stock
FROM (VALUES
  ('Carrefour', 'Leche entera 1L', 1300, true), ('Carrefour', 'Huevos L x12', 2200, true),
  ('Carrefour', 'Pan de molde', 1100, true), ('Carrefour', 'Aceite de oliva extra virgen 1L', 5200, true),
  ('Carrefour', 'Aceite de girasol 1L', 2100, true), ('Carrefour', 'Manteca 200g', 1800, true),
  ('Vital', 'Leche entera 1L', 1250, true), ('Vital', 'Huevos L x12', 2100, true),
  ('Vital', 'Pan de molde', 1050, true), ('Vital', 'Aceite de oliva extra virgen 1L', 4900, true),
  ('Vital', 'Aceite de girasol 1L', 1950, true), ('Vital', 'Manteca 200g', 1700, true),
  ('Jaguar', 'Leche entera 1L', 1400, true), ('Jaguar', 'Huevos L x12', 2300, true),
  ('Jaguar', 'Pan de molde', 1150, true), ('Jaguar', 'Aceite de girasol 1L', 2200, true),
  ('Jaguar', 'Manteca 200g', 1900, true)
  -- Jaguar sin fila para "Aceite de oliva extra virgen 1L" (intencional)
) AS v(supermarket_name, product_name, price, in_stock)
JOIN new_supermarkets s ON s.name = v.supermarket_name
JOIN new_products p ON p.name = v.product_name;
