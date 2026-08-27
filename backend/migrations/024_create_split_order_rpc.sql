-- Compra dividida: un plan que reparte la lista entre varios supermercados se
-- convierte en VARIOS pedidos, uno por supermercado (ver ARQUITECTURA.md §9.1).
--
-- Por qué una función nueva y no llamar N veces a create_order_with_items: cada
-- llamada RPC es su propia transacción. Si la tercera falla, el usuario queda
-- con dos pedidos hechos y un tercio de la compra sin encargar, sin forma de
-- saberlo desde la pantalla de confirmación. Un plan de compra se confirma
-- entero o no se confirma: por eso los N pedidos se escriben en una sola
-- transacción, que es exactamente el motivo por el que existe la migración 006.
--
-- El backend ya validó todo en Python antes de llamar acá (ownership de la
-- lista, visibilidad de cada supermercado, que el plan cubra la lista completa
-- sin repetir productos, stock y precios de cada grupo). Acá solo se persiste.
CREATE OR REPLACE FUNCTION public.create_orders_with_items(
  p_user_id UUID, p_list_id UUID, p_pickup_scheduled TIMESTAMPTZ, p_notes TEXT,
  -- [{"supermarket_id":"...","total_price":2500,
  --   "items":[{"product_id":"...","quantity":2,"unit_price":1250,"subtotal":2500}]}, ...]
  p_orders JSONB
)
RETURNS UUID[] LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_order     JSONB;
  v_item      JSONB;
  v_order_id  UUID;
  v_order_ids UUID[] := ARRAY[]::UUID[];
BEGIN
  FOR v_order IN SELECT * FROM jsonb_array_elements(p_orders) LOOP
    INSERT INTO public.orders (user_id, supermarket_id, list_id, status, pickup_scheduled, total_price, notes)
    VALUES (p_user_id, (v_order->>'supermarket_id')::UUID, p_list_id, 'pending',
            p_pickup_scheduled, (v_order->>'total_price')::INTEGER, p_notes)
    RETURNING id INTO v_order_id;

    FOR v_item IN SELECT * FROM jsonb_array_elements(v_order->'items') LOOP
      INSERT INTO public.order_items (order_id, product_id, quantity, unit_price, subtotal)
      VALUES (v_order_id, (v_item->>'product_id')::UUID, (v_item->>'quantity')::NUMERIC,
              (v_item->>'unit_price')::INTEGER, (v_item->>'subtotal')::INTEGER);
    END LOOP;

    INSERT INTO public.order_status_log (order_id, status, changed_by, note)
    VALUES (v_order_id, 'pending', p_user_id, 'Pedido creado (compra dividida)');

    v_order_ids := array_append(v_order_ids, v_order_id);
  END LOOP;

  RETURN v_order_ids;
END;
$$;

-- CRÍTICO, por lo mismo que en la 006: es SECURITY DEFINER. Si un cliente
-- autenticado pudiera invocarla vía supabase-js podría pasar cualquier
-- p_user_id y falsificar pedidos a nombre de otro usuario, salteándose por
-- completo la validación de order_service.py. Solo el backend (service_role).
REVOKE EXECUTE ON FUNCTION public.create_orders_with_items FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.create_orders_with_items FROM anon;
REVOKE EXECUTE ON FUNCTION public.create_orders_with_items FROM authenticated;
GRANT  EXECUTE ON FUNCTION public.create_orders_with_items TO service_role;
