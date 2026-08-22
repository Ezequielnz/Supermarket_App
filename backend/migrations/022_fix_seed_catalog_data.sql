-- Dos reparaciones sobre los datos del seed (007). Ninguna cambia el esquema.

-- ── 1. Los precios del seed estaban en pesos, no en centavos ──────────────
--
-- `supermarket_products.price` es INTEGER en CENTAVOS desde la 003, y así lo
-- exige NORMAS.md §4.3. Pero el seed cargó 1950 para un litro de aceite: eso
-- es $19,50, no $1.950. El seed guardó pesos en una columna de centavos.
--
-- Se detectó al construir el formateo de precios del carrito: el front hacía
-- `total.toFixed(2)` sobre centavos, que es el mismo error del otro lado. Se
-- arregla acá, en el dato, y allá con un formatPrice() compartido — antes de
-- que existan precios reales cargados por supermercados, que sí van a venir en
-- centavos desde el panel.
--
-- price_history queda vacío para estas filas: el trigger record_price_change
-- archiva el valor ANTERIOR, y ese valor anterior era el que estaba mal. No
-- hay historia que preservar, son datos de seed.
UPDATE supermarket_products SET price = price * 100;


-- ── 2. EAN en los productos del seed ──────────────────────────────────────
--
-- El comparador depende de que la leche de Carrefour y la de Vital sean el
-- MISMO product_id. Con supermercados reales eso lo sostiene el código de
-- barras (idx_products_ean, migración 016), que es la clave de matcheo de
-- catalog_service.resolve_product.
--
-- Los 6 productos del seed nacieron sin EAN, así que la rama "el EAN ya existe
-- -> vinculá, no dupliques" no se podía probar contra el catálogo inicial: el
-- primer supermercado real que cargara leche crearía una fila paralela y la
-- comparación quedaría partida en dos sin que nadie lo notara.
--
-- EAN-13 con prefijo 779 (GS1 Argentina). Son datos de demostración: no
-- corresponden a productos reales de ningún fabricante.
UPDATE products SET ean = '7790001000017' WHERE name = 'Leche entera 1L';
UPDATE products SET ean = '7790001000024' WHERE name = 'Pan de molde';
UPDATE products SET ean = '7790001000031' WHERE name = 'Huevos L x12';
UPDATE products SET ean = '7790001000048' WHERE name = 'Aceite de girasol 1L';
UPDATE products SET ean = '7790001000055' WHERE name = 'Aceite de oliva extra virgen 1L';
UPDATE products SET ean = '7790001000062' WHERE name = 'Manteca 200g';
