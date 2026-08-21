-- Operadores de FreshMart que aprueban o rechazan las solicitudes de alta de
-- las cadenas, y el registro auditable de esas decisiones.

CREATE TABLE platform_admins (
  id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name  TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Append-only: aprobar, rechazar y suspender son decisiones con consecuencias
-- comerciales, así que queda quién, cuándo y por qué. Mismo rol que
-- order_status_log para los pedidos.
CREATE TABLE chain_verification_log (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chain_id   UUID NOT NULL REFERENCES chains(id) ON DELETE CASCADE,
  status     chain_status NOT NULL,
  changed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  note       TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chain_verification_log_chain ON chain_verification_log(chain_id);


-- ── RLS ───────────────────────────────────────────────────────────────────
ALTER TABLE platform_admins        ENABLE ROW LEVEL SECURITY;
ALTER TABLE chain_verification_log ENABLE ROW LEVEL SECURITY;

-- CERO policies para `authenticated` en ambas tablas: solo el backend las lee y
-- las escribe. La lista de administradores de la plataforma no es algo que un
-- cliente deba poder enumerar, y el log de verificación contiene las notas
-- internas de la revisión.
--
-- platform_admins se puebla a mano por SQL. No hay, ni debe haber, un endpoint
-- para darse de alta como administrador.
