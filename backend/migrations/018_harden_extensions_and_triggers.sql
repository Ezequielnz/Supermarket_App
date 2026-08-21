-- Cierra los avisos del Security Advisor de Supabase que quedaron después de
-- 008-017.

-- ── 1. Extensiones fuera de `public` ──────────────────────────────────────
-- 009 y 010 usaron `CREATE EXTENSION IF NOT EXISTS x` sin indicar esquema, así
-- que pg_trgm y citext quedaron en `public`, mezcladas con las tablas de la
-- aplicación. Supabase ya tiene un esquema `extensions` para esto (ahí viven
-- pgcrypto y uuid-ossp) y lo incluye en el search_path por default
-- ("$user", public, extensions), así que mover no rompe ninguna consulta.
--
-- Importa porque `public` es el esquema que PostgREST expone: cuanto menos
-- haya ahí que no sea de la aplicación, menos superficie de API.
ALTER EXTENSION pg_trgm SET SCHEMA extensions;
ALTER EXTENSION citext  SET SCHEMA extensions;

-- Las funciones SECURITY DEFINER declaran `SET search_path = public`, que NO
-- incluye `extensions`. Hoy ninguna compara valores citext (solo inserta, y
-- los casts se resuelven por OID, no por search_path), pero dejarlo así es una
-- trampa para la próxima función que sí lo haga.
ALTER FUNCTION public.register_supermarket_chain(UUID, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, JSONB, JSONB)
  SET search_path = public, extensions;
ALTER FUNCTION public.review_chain(UUID, UUID, chain_status, TEXT)
  SET search_path = public, extensions;


-- ── 2. Funciones de trigger no son API ────────────────────────────────────
-- handle_new_user y record_price_change son SECURITY DEFINER y heredaron el
-- grant a anon/authenticated de los default privileges de Supabase. En la
-- práctica PostgREST no puede invocarlas (devuelven `trigger`), pero el
-- advisor las marca con razón: el grant no tiene ningún motivo para existir y
-- la regla de SEGURIDAD.md §5.3 no admite excepciones por "no es explotable".
REVOKE EXECUTE ON FUNCTION public.handle_new_user()     FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.record_price_change() FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.set_updated_at()      FROM PUBLIC, anon, authenticated;

-- Los triggers ejecutan como el owner de la tabla, no como el rol de la
-- sesión, así que revocar acá no los afecta.


-- ── 3. current_staff_chain_id: sacar a anon ───────────────────────────────
-- Se mantiene el grant a `authenticated` porque la policy
-- supermarket_users_select_own_chain la evalúa como ese rol y sin EXECUTE la
-- policy falla. `anon` no la necesita: para una petición sin JWT auth.uid() es
-- NULL y la función devolvería NULL igual. Un grant que no hace falta se saca.
REVOKE EXECUTE ON FUNCTION public.current_staff_chain_id() FROM PUBLIC, anon;


-- ── 4. Lo que NO se cambia ────────────────────────────────────────────────
-- El advisor reporta `rls_enabled_no_policy` (nivel INFO) para platform_admins
-- y chain_verification_log. Es intencional y correcto: RLS activo sin ninguna
-- policy significa denegar todo a anon y authenticated, que es exactamente lo
-- que queremos. Solo el backend (service_role) las toca. Ver 013.
--
-- `rls_auto_enable` también aparece como SECURITY DEFINER ejecutable: es una
-- función gestionada por Supabase (devuelve `event_trigger`), no del proyecto.
-- No se toca.
