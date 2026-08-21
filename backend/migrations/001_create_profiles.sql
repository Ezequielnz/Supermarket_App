-- Tabla de perfil extendido del consumidor (referencia 1:1 a auth.users)
CREATE TABLE profiles (
  id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name  TEXT,
  phone      TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Un consumidor solo puede leer su propia fila
CREATE POLICY "profiles_select_own"
  ON profiles FOR SELECT
  USING (auth.uid() = id);

-- Un consumidor solo puede actualizar su propia fila
CREATE POLICY "profiles_update_own"
  ON profiles FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- No hay policy de INSERT ni DELETE para el rol "authenticated": la fila se
-- crea exclusivamente vía trigger (ver 002_create_profile_trigger.sql) y el
-- backend (service_role) bypasea RLS si en el futuro necesita administrar
-- perfiles directamente.
