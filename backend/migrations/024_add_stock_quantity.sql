-- Stock de verdad: cuántas unidades hay, no solo "hay / no hay".
--
-- La 003 dejó `supermarket_products.in_stock BOOLEAN`, que es un interruptor
-- que alguien tiene que acordarse de bajar. Con eso, el pedido de orders.py
-- filtra por `in_stock = true` y nunca descuenta nada: dos consumidores pueden
-- comprar la misma última unidad y el supermercado se entera en el mostrador.
-- Es exactamente el caso que NORMAS.md §5.1 llama "un dato que miente tarde o
-- temprano".
--
-- Esta migración agrega la cantidad, la mantiene coherente con el booleano y
-- convierte la creación del pedido en una RESERVA atómica.

-- ── 1. La cantidad ────────────────────────────────────────────────────────
-- NUMERIC(10,2) y no INTEGER porque hay productos que se venden por peso: 2,5
-- kg de asado es un stock válido. Misma escala que order_items.quantity, así
-- una resta nunca pierde precisión contra lo que se pidió.
--
-- NULL es un valor con significado: "esta sucursal no lleva control unitario
-- de este producto". Frutas y verduras a granel, panadería, fiambrería. Para
-- esas filas manda `in_stock` y nada se descuenta. Sin este NULL, el importador
-- obligaría a inventar un número para cada producto sin stock informado, y un
-- 0 inventado saca el producto de la venta.
ALTER TABLE supermarket_products
  ADD COLUMN stock_quantity NUMERIC(10,2);

ALTER TABLE supermarket_products
  ADD CONSTRAINT stock_quantity_not_negative
    CHECK (stock_quantity IS NULL OR stock_quantity >= 0);

COMMENT ON COLUMN supermarket_products.stock_quantity IS
  'Unidades disponibles en esta sucursal. NULL = sin control unitario (granel): manda in_stock y no se descuenta. 0 fuerza in_stock = FALSE vía sync_in_stock_with_quantity.';

CREATE INDEX idx_sp_supermarket_in_stock
  ON supermarket_products(supermarket_id, in_stock);


-- ── 2. El booleano no puede contradecir a la cantidad ─────────────────────
-- Con dos campos que dicen lo mismo, tarde o temprano dicen cosas distintas:
-- stock_quantity = 0 con in_stock = true es un producto que se vende sin
-- existencias. La regla es de una sola dirección a propósito:
--
--   cantidad 0        -> in_stock = FALSE, siempre, no es negociable.
--   cantidad positiva -> in_stock queda como está.
--
-- La segunda mitad importa tanto como la primera: un encargado puede querer
-- despublicar un producto que sí tiene en góndola (lo reservó, está vencido,
-- lo retiró el proveedor). Si la cantidad forzara `true`, el próximo import
-- volvería a publicar lo que alguien bajó a mano.
CREATE OR REPLACE FUNCTION public.sync_in_stock_with_quantity()
RETURNS TRIGGER LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
  IF NEW.stock_quantity IS NOT NULL AND NEW.stock_quantity <= 0 THEN
    NEW.in_stock := FALSE;
  END IF;
  RETURN NEW;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.sync_in_stock_with_quantity() FROM PUBLIC, anon, authenticated;

CREATE TRIGGER sync_in_stock_with_quantity_on_write
  BEFORE INSERT OR UPDATE OF stock_quantity, in_stock ON supermarket_products
  FOR EACH ROW EXECUTE FUNCTION public.sync_in_stock_with_quantity();


-- ── 3. Crear un pedido RESERVA el stock ───────────────────────────────────
-- Misma firma que la 006: order_service.py no cambia su llamada. Lo que cambia
-- es que ahora cada ítem descuenta dentro de la MISMA transacción que crea el
-- pedido.
--
-- Python ya valida el stock antes de llamar (order_service.create_order), pero
-- esa validación vive entre un SELECT y un INSERT: dos pedidos simultáneos por
-- la última unidad la leen disponible los dos. La condición va acá, en el
-- WHERE del UPDATE, que es el único lugar donde Postgres serializa a los dos
-- competidores. Es la defensa en profundidad de SEGURIDAD.md §4.4, igual que
-- cancel_order revalidando el ownership.
CREATE OR REPLACE FUNCTION public.create_order_with_items(
  p_user_id UUID, p_supermarket_id UUID, p_list_id UUID,
  p_pickup_scheduled TIMESTAMPTZ, p_notes TEXT, p_total_price INTEGER,
  p_items JSONB  -- [{"product_id":"...","quantity":2,"unit_price":1250,"subtotal":2500}, ...]
)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_order_id UUID;
  v_item JSONB;
  v_quantity NUMERIC;
BEGIN
  INSERT INTO public.orders (user_id, supermarket_id, list_id, status, pickup_scheduled, total_price, notes)
  VALUES (p_user_id, p_supermarket_id, p_list_id, 'pending', p_pickup_scheduled, p_total_price, p_notes)
  RETURNING id INTO v_order_id;

  FOR v_item IN SELECT * FROM jsonb_array_elements(p_items) LOOP
    v_quantity := (v_item->>'quantity')::NUMERIC;

    -- Un solo UPDATE hace las tres cosas: bloquea la fila, comprueba que
    -- alcance y descuenta. `stock_quantity IS NULL` pasa el filtro y la resta
    -- deja NULL (NULL - n = NULL): el granel sigue rigiéndose por in_stock.
    UPDATE public.supermarket_products
       SET stock_quantity = stock_quantity - v_quantity
     WHERE supermarket_id = p_supermarket_id
       AND product_id = (v_item->>'product_id')::UUID
       AND in_stock
       AND (stock_quantity IS NULL OR stock_quantity >= v_quantity);

    IF NOT FOUND THEN
      -- Aborta la transacción entera: sin pedido, sin ítems, sin descuentos
      -- parciales. order_service lo traduce a 409.
      RAISE EXCEPTION 'insufficient_stock';
    END IF;

    INSERT INTO public.order_items (order_id, product_id, quantity, unit_price, subtotal)
    VALUES (v_order_id, (v_item->>'product_id')::UUID, v_quantity,
            (v_item->>'unit_price')::INTEGER, (v_item->>'subtotal')::INTEGER);
  END LOOP;

  INSERT INTO public.order_status_log (order_id, status, changed_by, note)
  VALUES (v_order_id, 'pending', p_user_id, 'Pedido creado');

  RETURN v_order_id;
END;
$$;


-- ── 4. Cancelar DEVUELVE el stock ─────────────────────────────────────────
-- Sin esto la reserva es una fuga: cada cancelación deja unidades apartadas
-- para un pedido que no existe, y el stock del supermercado baja solo.
--
-- El `in_stock` se reenciende únicamente si la fila está hoy en 0. Un 0 solo
-- puede haber apagado el booleano a través del trigger de arriba (con cantidad
-- en 0 no hay forma de que quede en true), así que devolver unidades ahí es
-- deshacer lo que hizo la reserva. Si la fila tiene cantidad positiva y está
-- despublicada, es una decisión humana y no se toca.
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

  UPDATE public.supermarket_products sp
     SET stock_quantity = sp.stock_quantity + oi.quantity,
         in_stock       = (sp.in_stock OR sp.stock_quantity = 0)
    FROM public.order_items oi
   WHERE oi.order_id = p_order_id
     AND sp.supermarket_id = v_order.supermarket_id
     AND sp.product_id = oi.product_id
     AND sp.stock_quantity IS NOT NULL;

  UPDATE public.orders SET status = 'cancelled', updated_at = NOW() WHERE id = p_order_id RETURNING * INTO v_order;
  INSERT INTO public.order_status_log (order_id, status, changed_by, note) VALUES (p_order_id, 'cancelled', p_user_id, p_note);
  RETURN v_order;
END;
$$;

-- Los REVOKE/GRANT de la 006 sobreviven al CREATE OR REPLACE (Postgres
-- conserva los privilegios de una función reemplazada), pero se repiten para
-- que esta migración se pueda leer sola. SEGURIDAD.md §5.3.
REVOKE EXECUTE ON FUNCTION public.create_order_with_items FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.create_order_with_items TO service_role;

REVOKE EXECUTE ON FUNCTION public.cancel_order FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.cancel_order TO service_role;
