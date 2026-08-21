-- Staff de los supermercados. La tabla estaba documentada en ARQUITECTURA.md
-- §7.1 desde el principio pero nunca se había migrado.

CREATE TABLE supermarket_users (
  id             UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  chain_id       UUID NOT NULL REFERENCES chains(id) ON DELETE CASCADE,
  -- NULL = acceso a toda la cadena. Con valor = staff acotado a una sucursal.
  supermarket_id UUID REFERENCES supermarkets(id) ON DELETE SET NULL,
  role           staff_role NOT NULL DEFAULT 'staff',
  full_name      TEXT NOT NULL,
  phone          TEXT,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_supermarket_users_chain ON supermarket_users(chain_id);

-- Exactamente un owner por cadena: es quien responde por los datos fiscales y
-- el único que puede tocar el equipo. Índice parcial, así los demás roles no
-- quedan limitados.
CREATE UNIQUE INDEX idx_one_owner_per_chain
  ON supermarket_users(chain_id) WHERE role = 'owner';


-- ── Helper para las policies ──────────────────────────────────────────────
-- Una policy sobre supermarket_users que consulte supermarket_users entra en
-- recursión infinita (Postgres re-evalúa la policy al leer la tabla desde
-- adentro). El patrón estándar es encapsular la lectura en una función
-- SECURITY DEFINER, que no aplica RLS.
--
-- EXCEPCIÓN DOCUMENTADA a la regla de SEGURIDAD.md §5.3: esta función SÍ es
-- invocable por `authenticated`. No recibe parámetros y se auto-acota con
-- auth.uid(), así que un cliente que la llame solo puede obtener su propio
-- chain_id — que ya conoce. No hay nada que escalar.
CREATE OR REPLACE FUNCTION public.current_staff_chain_id()
RETURNS UUID LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT chain_id FROM public.supermarket_users
  WHERE id = auth.uid() AND is_active;
$$;

REVOKE EXECUTE ON FUNCTION public.current_staff_chain_id FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.current_staff_chain_id TO authenticated;
GRANT  EXECUTE ON FUNCTION public.current_staff_chain_id TO service_role;


-- ── RLS ───────────────────────────────────────────────────────────────────
ALTER TABLE supermarket_users ENABLE ROW LEVEL SECURITY;

-- Un staff ve a los compañeros de su propia cadena, y a nadie más.
CREATE POLICY "supermarket_users_select_own_chain"
  ON supermarket_users FOR SELECT TO authenticated
  USING (chain_id = public.current_staff_chain_id());

-- Ninguna policy de INSERT/UPDATE/DELETE para authenticated: el alta y la baja
-- de staff pasan exclusivamente por el backend, igual que orders (005). Si el
-- staff pudiera escribir su propia fila, se ascendería a 'owner' solo.


-- ── El staff no es un consumidor ──────────────────────────────────────────
-- handle_new_user (002) crea una fila en `profiles` para TODO usuario nuevo de
-- auth.users, incluido el staff de un supermercado. Eso deja a cada empleado
-- con un perfil de consumidor fantasma y hace ambigua la pregunta "¿este
-- usuario qué es?". Se discrimina por un flag en el metadata que escribe el
-- backend al crear la cuenta.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Sin el flag se asume consumidor: preserva el comportamiento de 002 para
  -- cualquier alta que no venga del registro de supermercados.
  IF COALESCE(NEW.raw_user_meta_data ->> 'account_type', 'consumer') <> 'consumer' THEN
    RETURN NEW;
  END IF;

  INSERT INTO public.profiles (id, full_name, phone)
  VALUES (
    NEW.id,
    NEW.raw_user_meta_data ->> 'full_name',
    NEW.raw_user_meta_data ->> 'phone'
  );
  RETURN NEW;
END;
$$;
