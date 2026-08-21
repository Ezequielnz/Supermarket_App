-- Registro de una cadena y revisión de la solicitud, ambos atómicos.
--
-- Mismo razonamiento que create_order_with_items (006): el alta escribe en
-- chains, supermarkets, store_hours, supermarket_users y
-- chain_verification_log. Si falla a la mitad queda un usuario de auth.users
-- sin cadena — una cuenta que puede loguearse pero para la que get_current_staff
-- no encuentra nada. La transacción única evita ese estado.
--
-- El backend ya validó formato y unicidad en Python antes de llamar; acá se
-- persiste y se revalida lo que solo la base puede garantizar.

CREATE OR REPLACE FUNCTION public.register_supermarket_chain(
  p_user_id         UUID,
  p_legal_name      TEXT,
  p_trade_name      TEXT,
  p_tax_id          TEXT,
  p_contact_email   TEXT,
  p_contact_phone   TEXT,
  p_owner_full_name TEXT,
  p_owner_phone     TEXT,
  p_store           JSONB,  -- {"name","street","city","province","postal_code","phone"}
  p_hours           JSONB   -- [{"weekday":1,"opens_at":"08:00","closes_at":"21:00"}, ...]
)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_chain_id UUID;
  v_store_id UUID;
  v_hour     JSONB;
BEGIN
  IF EXISTS (SELECT 1 FROM public.supermarket_users WHERE id = p_user_id) THEN
    RAISE EXCEPTION 'user_already_staff';
  END IF;

  BEGIN
    INSERT INTO public.chains (
      legal_name, trade_name, tax_id, contact_email, contact_phone, status
    )
    VALUES (
      p_legal_name, p_trade_name, p_tax_id, p_contact_email, p_contact_phone, 'pending_review'
    )
    RETURNING id INTO v_chain_id;
  EXCEPTION WHEN unique_violation THEN
    -- El CUIT ya está registrado por otra cadena. Se distingue del resto de
    -- errores para que el backend devuelva 409 y no un 502 genérico.
    RAISE EXCEPTION 'chain_tax_id_taken';
  END;

  INSERT INTO public.supermarkets (
    chain_id, name, address, street, city, province, postal_code, phone, is_active
  )
  VALUES (
    v_chain_id,
    p_store ->> 'name',
    -- `address` se mantiene como texto de display, compuesto por el backend
    -- desde los campos estructurados.
    CONCAT_WS(', ', p_store ->> 'street', p_store ->> 'city'),
    p_store ->> 'street',
    p_store ->> 'city',
    p_store ->> 'province',
    p_store ->> 'postal_code',
    p_store ->> 'phone',
    TRUE
  )
  RETURNING id INTO v_store_id;

  FOR v_hour IN SELECT * FROM jsonb_array_elements(p_hours) LOOP
    INSERT INTO public.store_hours (supermarket_id, weekday, opens_at, closes_at)
    VALUES (
      v_store_id,
      (v_hour ->> 'weekday')::SMALLINT,
      (v_hour ->> 'opens_at')::TIME,
      (v_hour ->> 'closes_at')::TIME
    );
  END LOOP;

  -- Quien registra la cadena es su owner: el único rol que puede editar los
  -- datos fiscales y administrar el equipo.
  INSERT INTO public.supermarket_users (id, chain_id, role, full_name, phone)
  VALUES (p_user_id, v_chain_id, 'owner', p_owner_full_name, p_owner_phone);

  INSERT INTO public.chain_verification_log (chain_id, status, changed_by, note)
  VALUES (v_chain_id, 'pending_review', p_user_id, 'Solicitud de alta enviada');

  RETURN v_chain_id;
END;
$$;


-- Aprobación / rechazo / suspensión. Valida el rol de administrador DENTRO de
-- la transacción, además de la validación en Python: defensa en profundidad,
-- igual que cancel_order revalida el ownership del pedido.
CREATE OR REPLACE FUNCTION public.review_chain(
  p_chain_id UUID,
  p_admin_id UUID,
  p_status   chain_status,
  p_note     TEXT
)
RETURNS chains LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_chain chains%ROWTYPE;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.platform_admins WHERE id = p_admin_id) THEN
    RAISE EXCEPTION 'not_platform_admin';
  END IF;

  IF p_status = 'pending_review' THEN
    RAISE EXCEPTION 'invalid_review_status';
  END IF;

  -- Rechazar sin motivo deja al supermercado sin nada que corregir; además lo
  -- exige el CHECK rejected_needs_reason de 010.
  IF p_status = 'rejected' AND (p_note IS NULL OR TRIM(p_note) = '') THEN
    RAISE EXCEPTION 'rejection_reason_required';
  END IF;

  SELECT * INTO v_chain FROM public.chains WHERE id = p_chain_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'chain_not_found';
  END IF;

  IF v_chain.status = p_status THEN
    RAISE EXCEPTION 'chain_already_in_status';
  END IF;

  UPDATE public.chains
  SET status           = p_status,
      rejection_reason = CASE WHEN p_status = 'rejected' THEN p_note ELSE NULL END,
      reviewed_by      = p_admin_id,
      reviewed_at      = NOW()
  WHERE id = p_chain_id
  RETURNING * INTO v_chain;

  INSERT INTO public.chain_verification_log (chain_id, status, changed_by, note)
  VALUES (p_chain_id, p_status, p_admin_id, p_note);

  RETURN v_chain;
END;
$$;


-- CRÍTICO — mismo motivo que en 006. Son funciones SECURITY DEFINER y Postgres
-- otorga EXECUTE a PUBLIC por defecto:
--
--   * register_supermarket_chain invocable por un cliente = cualquiera con la
--     anon key crea cadenas a nombre de cualquier p_user_id.
--   * review_chain invocable por un cliente = cualquier cadena se auto-aprueba
--     pasando su propio id, salta la moderación y entra al comparador.
REVOKE EXECUTE ON FUNCTION public.register_supermarket_chain FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.register_supermarket_chain FROM authenticated;
GRANT  EXECUTE ON FUNCTION public.register_supermarket_chain TO service_role;

REVOKE EXECUTE ON FUNCTION public.review_chain FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.review_chain FROM authenticated;
GRANT  EXECUTE ON FUNCTION public.review_chain TO service_role;
