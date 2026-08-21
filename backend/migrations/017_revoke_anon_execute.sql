-- CORRECCIÓN DE SEGURIDAD — severidad crítica.
--
-- La migración 006 intentó cerrar el acceso de los clientes a las funciones
-- SECURITY DEFINER con:
--
--     REVOKE EXECUTE ... FROM PUBLIC;
--     REVOKE EXECUTE ... FROM authenticated;
--
-- pero eso NO alcanza en Supabase. El proyecto trae configurado
--
--     ALTER DEFAULT PRIVILEGES IN SCHEMA public
--       GRANT EXECUTE ON FUNCTIONS TO anon, authenticated, service_role;
--
-- así que cada función nueva nace con un grant DIRECTO a `anon`, además del
-- que hereda de PUBLIC. Revocar de PUBLIC no lo toca, y revocar de
-- `authenticated` tampoco: el grant a `anon` sobrevive.
--
-- Verificado sobre la base real antes de este arreglo:
--
--     proname                     | proacl
--     create_order_with_items     | {postgres=X/postgres,anon=X/postgres,service_role=X/postgres}
--     cancel_order                | {postgres=X/postgres,anon=X/postgres,service_role=X/postgres}
--
-- Consecuencia: `anon` es el rol que usa PostgREST cuando la petición llega
-- SIN JWT, solo con la anon key — que va embebida en el bundle del frontend y
-- es pública por diseño. Cualquiera podía hacer
--
--     POST /rest/v1/rpc/create_order_with_items
--     apikey: <anon key>
--     { "p_user_id": "<uuid de cualquier víctima>", ... }
--
-- y crear pedidos a nombre de otro usuario, sin autenticarse, salteándose por
-- completo la validación de order_service.py. Con 014 aplicada, lo mismo valía
-- para review_chain: una cadena podía auto-aprobarse y entrar al comparador.
--
-- No se editan 006 ni 014 porque ya están aplicadas (NORMAS.md §5.2): el
-- arreglo va acá, y así cualquier entorno reconstruido desde 001 termina en el
-- estado correcto.

REVOKE EXECUTE ON FUNCTION public.create_order_with_items    FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.cancel_order               FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.register_supermarket_chain FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.review_chain               FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.create_order_with_items    TO service_role;
GRANT EXECUTE ON FUNCTION public.cancel_order               TO service_role;
GRANT EXECUTE ON FUNCTION public.register_supermarket_chain TO service_role;
GRANT EXECUTE ON FUNCTION public.review_chain               TO service_role;

-- current_staff_chain_id NO entra acá: es la excepción documentada de
-- SEGURIDAD.md §5.3. No recibe parámetros, se auto-acota con auth.uid() y solo
-- devuelve el chain_id del propio llamante. Para `anon`, auth.uid() es NULL y
-- la función devuelve NULL, así que no filtra nada.

-- A partir de ahora, toda función SECURITY DEFINER expuesta por PostgREST se
-- revoca de los TRES: PUBLIC, anon y authenticated.
