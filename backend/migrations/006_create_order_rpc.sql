-- Igual que el trigger de profiles (002): crear un pedido escribe en 3 tablas
-- (orders, order_items, order_status_log) y debe ser atómico. El backend ya
-- validó todo en Python (ownership de la lista, stock, precios, total) antes
-- de llamar esta función — acá solo se persiste atómicamente.
CREATE OR REPLACE FUNCTION public.create_order_with_items(
  p_user_id UUID, p_supermarket_id UUID, p_list_id UUID,
  p_pickup_scheduled TIMESTAMPTZ, p_notes TEXT, p_total_price INTEGER,
  p_items JSONB  -- [{"product_id":"...","quantity":2,"unit_price":1250,"subtotal":2500}, ...]
)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_order_id UUID;
  v_item JSONB;
BEGIN
  INSERT INTO public.orders (user_id, supermarket_id, list_id, status, pickup_scheduled, total_price, notes)
  VALUES (p_user_id, p_supermarket_id, p_list_id, 'pending', p_pickup_scheduled, p_total_price, p_notes)
  RETURNING id INTO v_order_id;

  FOR v_item IN SELECT * FROM jsonb_array_elements(p_items) LOOP
    INSERT INTO public.order_items (order_id, product_id, quantity, unit_price, subtotal)
    VALUES (v_order_id, (v_item->>'product_id')::UUID, (v_item->>'quantity')::NUMERIC,
            (v_item->>'unit_price')::INTEGER, (v_item->>'subtotal')::INTEGER);
  END LOOP;

  INSERT INTO public.order_status_log (order_id, status, changed_by, note)
  VALUES (v_order_id, 'pending', p_user_id, 'Pedido creado');

  RETURN v_order_id;
END;
$$;

-- Cancelación: valida ownership y estado DENTRO de la transacción (defensa en
-- profundidad adicional a la validación en Python), atómico con el log.
CREATE OR REPLACE FUNCTION public.cancel_order(p_order_id UUID, p_user_id UUID, p_note TEXT)
RETURNS orders LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_order orders%ROWTYPE;
BEGIN
  SELECT * INTO v_order FROM public.orders WHERE id = p_order_id AND user_id = p_user_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'order_not_found';
  END IF;
  IF v_order.status IN ('completed', 'cancelled') THEN
    RAISE EXCEPTION 'order_not_cancellable';
  END IF;

  UPDATE public.orders SET status = 'cancelled', updated_at = NOW() WHERE id = p_order_id RETURNING * INTO v_order;
  INSERT INTO public.order_status_log (order_id, status, changed_by, note) VALUES (p_order_id, 'cancelled', p_user_id, p_note);
  RETURN v_order;
END;
$$;

-- CRÍTICO: revocar el EXECUTE que Postgres otorga a PUBLIC por defecto. Son
-- funciones SECURITY DEFINER — si un cliente autenticado pudiera invocarlas
-- vía supabase-js (`.rpc("create_order_with_items", {...})`), podría pasar
-- cualquier p_user_id y falsificar pedidos a nombre de otro usuario, saltando
-- por completo la validación de order_service.py. Solo el backend
-- (service_role) puede invocarlas.
REVOKE EXECUTE ON FUNCTION public.create_order_with_items FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.create_order_with_items FROM authenticated;
GRANT  EXECUTE ON FUNCTION public.create_order_with_items TO service_role;

REVOKE EXECUTE ON FUNCTION public.cancel_order FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.cancel_order FROM authenticated;
GRANT  EXECUTE ON FUNCTION public.cancel_order TO service_role;
