-- Hasta ahora la policy de supermarkets era USING (true): todo usuario
-- autenticado veía todos los supermercados. Con el auto-registro abierto, eso
-- significaría que una cadena recién anotada (o rechazada, o suspendida)
-- aparece en el comparador apenas cargue precios.

DROP POLICY "supermarkets_select_authenticated" ON supermarkets;

CREATE POLICY "supermarkets_select_approved"
  ON supermarkets FOR SELECT TO authenticated
  USING (
    is_active
    AND EXISTS (
      SELECT 1 FROM chains c
      WHERE c.id = supermarkets.chain_id AND c.status = 'approved'
    )
  );

DROP POLICY "supermarket_products_select_authenticated" ON supermarket_products;

CREATE POLICY "supermarket_products_select_approved"
  ON supermarket_products FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM supermarkets s
      JOIN chains c ON c.id = s.chain_id
      WHERE s.id = supermarket_products.supermarket_id
        AND s.is_active
        AND c.status = 'approved'
    )
  );


-- Vista de conveniencia con el criterio de visibilidad en un solo lugar, para
-- que el backend no repita el join en cada servicio.
CREATE OR REPLACE VIEW public_supermarkets AS
  SELECT s.*, c.trade_name AS chain_name, c.logo_url AS chain_logo_url
  FROM supermarkets s
  JOIN chains c ON c.id = s.chain_id
  WHERE s.is_active AND c.status = 'approved';

-- security_invoker: la vista evalúa las policies del usuario que consulta, no
-- las del owner de la vista. Sin esto una vista es un agujero de RLS.
ALTER VIEW public_supermarkets SET (security_invoker = true);

GRANT SELECT ON public_supermarkets TO authenticated;


-- ATENCIÓN — esto NO alcanza por sí solo.
--
-- El backend usa SERVICE_ROLE_KEY y bypasea RLS por completo, así que estas
-- policies no filtran ni una fila de las consultas de comparison_service,
-- product_service u order_service. El filtro por cadena aprobada tiene que
-- estar TAMBIÉN escrito a mano en Python. Ver SEGURIDAD.md §5.1.
