# FreshMart — Seguridad del Proyecto

> **Versión:** 1.0 · **Fecha:** 2026-08-21
>
> Documento normativo. Toda contribución al proyecto DEBE respetar estas reglas,
> igual que `NORMAS.md`. Donde este documento y `NORMAS.md` se solapen, este
> tiene precedencia en materia de seguridad.

---

## 1. Alcance y modelo de amenazas

### 1.1 Qué protegemos

FreshMart custodia tres activos de valor muy distinto:

| Activo | Por qué importa |
|---|---|
| **Datos personales del consumidor** | Nombre, correo, teléfono e historial de compras. Un historial de compras revela hábitos, dieta, salud y composición del hogar. |
| **Datos de los supermercados** | Razón social, CUIT, direcciones, contactos y — sobre todo — **su lista de precios completa**, que es información comercial sensible frente a sus competidores. |
| **Integridad de los pedidos** | Un pedido falsificado o alterado hace que un supermercado prepare mercadería que nadie pagó, o que un cliente pague de más. |

A futuro se suma un cuarto: **los medios de pago** (sección 7).

### 1.2 Actores

| Actor | Confianza | Puede |
|---|---|---|
| Anónimo | Ninguna | Ver la landing, registrarse |
| Consumidor autenticado | Baja | Gestionar sus listas y sus pedidos |
| Staff de supermercado (`staff`) | Media | Operar pedidos de **su** cadena |
| Owner de cadena (`owner`) | Media-alta | Todo lo anterior + perfil, sucursales y equipo de su cadena |
| Admin de plataforma | Alta | Aprobar/rechazar cadenas |
| Backend (`service_role`) | Total | Bypasea RLS por completo |

**Regla base:** ningún actor confía en datos que provengan de un actor de menor confianza sin validarlos.

### 1.3 Escenarios de amenaza priorizados

| # | Escenario | Impacto | Mitigación principal |
|---|---|---|---|
| T1 | Robo de credenciales de staff | Alto | MFA obligatorio para `owner`, verificación de correo, bloqueo por intentos fallidos (§3) |
| T2 | Falsificación de pedidos con la anon key | Alto | Sin policies de INSERT/UPDATE en `orders`; RPC `SECURITY DEFINER` con `REVOKE` (§5) |
| T3 | Una cadena manipula los precios de otra | Alto | Autorización derivada del JWT, nunca de un header (§4) |
| T4 | Scraping masivo del comparador | Medio-alto | Rate limiting y throttling (§11) |
| T5 | Fuga de PII de consumidores | Alto | Clasificación y minimización de datos (§2, §12) |
| T6 | Escalada vía `SERVICE_ROLE_KEY` filtrada | **Crítico** | Gestión de secretos y rotación (§6) |

T6 es el peor caso del sistema: esa clave bypasea RLS y da acceso de lectura y escritura a **toda** la base de datos. Si se filtra, no hay control de acceso que la contenga.

---

## 2. Clasificación de datos

Cuatro niveles. El nivel determina quién puede leer el dato, si puede aparecer en logs y cuánto se retiene.

| Nivel | Definición | En logs |
|---|---|---|
| **Público** | Puede exponerse sin autenticación | Sí |
| **Interno** | Requiere autenticación; su fuga no daña a una persona | Sí, sin volumen |
| **Confidencial** | Datos personales o comerciales; su fuga causa daño | **Nunca** |
| **Restringido** | Secretos y credenciales | **Nunca** |

### 2.1 Clasificación por tabla

| Tabla / columna | Nivel | Quién lee | Retención |
|---|---|---|---|
| `products` (catálogo global) | Público | Cualquiera | Indefinida |
| `chains.trade_name`, `logo_url` | Público | Cualquiera | Mientras esté activa |
| `supermarkets` (dirección, horarios) | Público | Cualquiera | Mientras esté activa |
| `supermarket_products.price` | **Interno** | Consumidores autenticados | Indefinida + histórico |
| `profiles.full_name`, `phone` | **Confidencial** | El propio usuario, backend | Hasta baja de cuenta |
| `auth.users.email` | **Confidencial** | El propio usuario, backend | Hasta baja de cuenta |
| `shopping_lists`, `orders`, `order_items` | **Confidencial** | Dueño + supermercado del pedido | 5 años (fiscal) |
| `chains.tax_id` (CUIT), `legal_name` | **Confidencial** | Owner de la cadena, admin | Mientras esté activa |
| `supermarket_users` | **Confidencial** | Staff de la cadena, backend | Hasta baja |
| `SERVICE_ROLE_KEY`, `ANON_KEY` | **Restringido** | Solo el entorno de ejecución | Rotación semestral |

### 2.2 Regla de precios

Los precios son **Interno**, no Público: son el activo comercial que los supermercados nos confían. Un endpoint que devuelva precios sin autenticación, o sin límite de volumen, entrega gratis el trabajo de relevamiento de todas las cadenas a un competidor. Ver §11.

---

## 3. Autenticación

### 3.1 Verificación de tokens

Supabase Auth emite los JWT de sesión. El backend los verifica **contra el JWKS público del proyecto** (ES256/RS256), no con un secreto compartido — ver `app/core/security.py`.

```python
# CORRECTO — clave asimétrica publicada vía JWKS, cacheada por PyJWKClient
_jwks_client = jwt.PyJWKClient(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json")
payload = jwt.decode(token, signing_key.key, algorithms=["ES256", "RS256"], audience="authenticated")

# INCORRECTO — HS256 con secreto compartido: quien lo tenga puede FIRMAR tokens,
# no solo verificarlos. Un secreto de verificación filtrado se vuelve un secreto
# de emisión.
payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
```

**Nunca** deshabilitar la verificación de firma, ni siquiera para depurar.

### 3.2 Contraseñas

- Mínimo 8 caracteres, máximo 72 (límite real de bcrypt; truncar en silencio es un bug de seguridad).
- El hashing lo hace Supabase Auth. **El proyecto nunca almacena ni transporta contraseñas fuera del alta.**
- Prohibido loguear el cuerpo de `/auth/register` o de cualquier request con contraseña.
- **Protección contra contraseñas filtradas activada** en Supabase Auth (contrasta contra HaveIBeenPwned). Es un toggle del panel: Authentication → Policies. Ver D11 en §16.

### 3.3 Verificación de correo

| Tipo de cuenta | `email_confirm` | Motivo |
|---|---|---|
| Staff de supermercado | **`False`** (confirmación real obligatoria) | Publica precios y recibe pedidos: la cuenta debe pertenecer a quien dice ser |
| Admin de plataforma | **`False`** + alta manual | Máximo privilegio |
| Consumidor | `False` (objetivo) | Ver §16 — hoy es `True`, es deuda |

Crear un usuario con `email_confirm: True` significa **marcar el correo como verificado sin que nadie lo haya confirmado**. Permite registrarse con la dirección de otra persona.

### 3.4 MFA

Obligatorio para `owner` de cadena y `platform_admin`. Opcional y recomendado para `manager`. Se implementa con el soporte TOTP de Supabase Auth.

### 3.5 Sesiones

- Access token de vida corta con refresh automático.
- El logout invalida la sesión del lado de Supabase, no solo el estado de React.
- Cambio de contraseña o baja de un staff → **revocar todas sus sesiones**.

### 3.6 Bloqueo por intentos fallidos

Límite de intentos fallidos por cuenta y por IP, con backoff exponencial. La respuesta ante credenciales inválidas es **idéntica** exista o no la cuenta: nunca "ese correo no está registrado".

---

## 4. Autorización

### 4.1 La pertenencia se deriva del token, jamás del cliente

```python
# CORRECTO — la cadena sale de la fila de supermarket_users indexada por el `sub` del JWT
def get_current_staff(credentials = Depends(bearer_scheme)) -> CurrentStaff:
    payload = _verify(credentials.credentials)
    staff = _lookup_supermarket_user(payload["sub"])   # fuente de verdad: la DB

# INCORRECTO — un header lo elige el cliente: el staff de la cadena A manda el UUID de la B
chain_id = request.headers["X-Supermarket-ID"]
```

> Esto corrige lo propuesto originalmente en `ARQUITECTURA.md §8`. Un identificador de tenant controlado por el cliente es una escalada horizontal servida en bandeja.

### 4.2 Matriz de permisos

| Recurso | Consumidor | staff | manager | owner | platform_admin |
|---|---|---|---|---|---|
| Listas propias | CRUD | — | — | — | — |
| Pedidos propios | Crear, leer, cancelar | — | — | — | — |
| Pedidos de su cadena | — | Leer, cambiar estado | Íd. | Íd. | — |
| Precios de su cadena | — | Leer | CRUD | CRUD | — |
| Sucursales de su cadena | — | Leer | CRUD | CRUD | — |
| Perfil de la cadena | — | Leer | Leer | Editar | Leer |
| Equipo de la cadena | — | — | — | CRUD | — |
| Aprobar cadenas | — | — | — | — | Sí |

### 4.3 404 en vez de 403 para recursos ajenos

Cuando el recurso existe pero es de otro usuario se devuelve **404**, no 403: un 403 confirma que el recurso existe. Patrón ya establecido en `app/services/list_service.py`.

`403` se reserva para cuando el actor tiene acceso legítimo al recurso pero le falta el **rol** (ej.: un `staff` intentando editar el perfil de la cadena).

### 4.4 Autorización en cada capa

Validar en el endpoint **y** en el servicio **y** en la base. Ninguna capa asume que la anterior filtró: `cancel_order` en `006_create_order_rpc.sql` revalida el ownership dentro de la transacción aunque Python ya lo había comprobado.

---

## 5. RLS y `service_role_key`

### 5.1 RLS es defensa en profundidad, no la barrera principal

**El backend usa `SERVICE_ROLE_KEY` y bypasea RLS por completo.** Las policies protegen contra un cliente que use la anon key directamente contra la API de Supabase; **no** protegen ninguna consulta del backend.

```python
# CORRECTO — el filtro de ownership es explícito; es la ÚNICA barrera real
client.table("orders").select("*").eq("id", str(order_id)).eq("user_id", str(user_id))

# INCORRECTO — "la policy orders_select_own me cubre". No: service_role la ignora.
client.table("orders").select("*").eq("id", str(order_id))
```

**Regla obligatoria:** toda consulta del backend a una tabla con datos de un tenant (usuario o cadena) lleva el filtro de ownership escrito a mano. Sin excepciones.

### 5.2 RLS igual va en todas las tablas

`NORMAS.md §5.3` lo exige y se mantiene: es la red que atrapa el día que se filtre la anon key. Toda tabla nueva nace con `ENABLE ROW LEVEL SECURITY` en su migración.

Tablas sin ninguna policy para `authenticated` (solo el backend las toca): `platform_admins`, `chain_verification_log`, `price_history`, y la escritura de `orders` / `order_items` / `order_status_log`.

### 5.3 Funciones `SECURITY DEFINER`

Una función `SECURITY DEFINER` corre con los privilegios de su *owner* y **Postgres otorga `EXECUTE` a `PUBLIC` por defecto**. Sin revocarlo, cualquier cliente con la anon key la invoca vía `supabase.rpc(...)` pasando los parámetros que quiera.

```sql
-- OBLIGATORIO en TODA función SECURITY DEFINER, sin excepción.
-- Los TRES roles: PUBLIC, anon y authenticated.
REVOKE EXECUTE ON FUNCTION public.mi_funcion FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.mi_funcion TO service_role;
```

> **`anon` es el que se olvida, y es el peligroso.** Revocar de `PUBLIC` no
> alcanza: el proyecto Supabase trae
> `ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO anon, authenticated, service_role`,
> así que cada función nueva nace con un grant **directo** a `anon` que
> sobrevive al `REVOKE ... FROM PUBLIC`. Y `anon` es el rol con el que PostgREST
> atiende las peticiones que llegan **sin JWT**, solo con la anon key — que va
> embebida en el bundle del front y es pública por diseño. Una función
> `SECURITY DEFINER` con grant a `anon` es una función que puede invocar
> cualquiera en internet, con los parámetros que quiera. Ver D10 en §16.

Además, siempre `SET search_path = public` en la definición: sin eso, un `search_path` manipulado puede desviar las llamadas internas hacia funciones del atacante.

Casos concretos del proyecto:
- `create_order_with_items` — sin `REVOKE`, cualquiera falsifica pedidos a nombre de otro pasando otro `p_user_id`.
- `create_orders_with_items` (compra dividida, migración 024) — lo mismo, multiplicado por la cantidad de supermercados del plan.
- `review_chain` — sin `REVOKE`, cualquier cadena se auto-aprueba y entra al comparador.

**Única excepción admitida:** una función sin parámetros que se auto-acote con
`auth.uid()` y solo devuelva un dato que el propio llamante ya conoce. El caso
del proyecto es `current_staff_chain_id()`, que existe para romper la recursión
de la policy de `supermarket_users` sobre sí misma. Toda excepción va comentada
en su migración explicando por qué no hay nada que escalar. Si la función acepta
un parámetro, no califica.

### 5.4 Verificación

```sql
-- Ninguna función SECURITY DEFINER debe listar authenticated ni PUBLIC en su ACL
SELECT proname,
       has_function_privilege('anon',          oid, 'EXECUTE') AS anon,
       has_function_privilege('authenticated', oid, 'EXECUTE') AS authenticated
FROM pg_proc
WHERE pronamespace = 'public'::regnamespace AND prosecdef;
-- Ambas columnas deben dar false, salvo las excepciones documentadas.

-- Ninguna tabla de public sin RLS
SELECT tablename FROM pg_tables
WHERE schemaname = 'public' AND NOT rowsecurity;
```

Ambas consultas van en el checklist de release. El *Security Advisor* de Supabase debe salir limpio.

---

## 6. Gestión de secretos

### 6.1 Dónde vive cada cosa

| Secreto | Dónde | Nunca |
|---|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` | Gestor de secretos del hosting | En el front, en el repo, en logs, en el navegador |
| `SUPABASE_ANON_KEY` | Variable de build del front | — (es pública por diseño, pero **no** sustituye autorización) |
| `SUPABASE_URL` | Ambos | — |

### 6.2 Reglas

- **Ningún secreto en el repositorio.** `.env` está en `.gitignore` y así se queda; se versiona solo `.env.example` con valores vacíos.
- **Ningún secreto hardcodeado.** Todo pasa por `core/config.py` (`NORMAS.md §4.6`).
- **Ningún secreto en logs ni en mensajes de error** devueltos al cliente.
- **Ningún secreto de más.** Una variable de entorno obligatoria que no se usa es superficie de exposición sin contrapartida: si no se usa, se borra.
- **Rotación semestral** de la `SERVICE_ROLE_KEY`, e inmediata ante sospecha de filtración.
- La anon key **no es una credencial de autorización**: es un identificador público de proyecto. Todo lo que proteja el sistema debe seguir protegido asumiendo que un atacante la tiene.

### 6.3 Si un secreto se filtra

1. Rotar la clave en Supabase **primero** (minutos, no horas).
2. Desplegar el backend con la clave nueva.
3. Revisar los logs de Supabase por accesos anómalos en la ventana de exposición.
4. Si hubo acceso a datos personales, activar §15.
5. Purgar el secreto del historial de git y forzar el push — **pero asumir que ya está comprometido**: la rotación es la mitigación real, no el borrado.

---

## 7. Medios de pago

> **Estado actual: FreshMart NO procesa pagos.** El flujo es armar la lista,
> retirar en el supermercado y pagar allí. Esta sección define la arquitectura
> **obligatoria** para el día que se agreguen pagos online. No es una sugerencia:
> es el diseño aprobado, y cualquier implementación que se desvíe debe pasar por
> una revisión de seguridad explícita antes de mergear.

### 7.1 Principio rector: los datos de tarjeta nunca tocan FreshMart

El único diseño aceptable es **tokenización con pasarela externa** (Mercado Pago, Stripe o equivalente):

```
Navegador del cliente ──── datos de tarjeta ────► Pasarela (iframe / SDK propio)
        │                                              │
        │◄──────────── token opaco ─────────────────────┘
        │
        └── token ──► Backend FreshMart ──► Pasarela: cobrar(token, monto)
```

El PAN (número de tarjeta), el CVV y la fecha de vencimiento viajan **del navegador a la pasarela directamente**, dentro de un iframe o SDK servido por la pasarela. FreshMart solo ve un token que no sirve fuera de su contexto.

### 7.2 Prohibiciones absolutas

Está **terminantemente prohibido**, sin excepción ni "solo para probar":

- Recibir PAN, CVV, PIN o banda magnética en cualquier endpoint de la API de FreshMart.
- Almacenar esos datos en Postgres, en caché, en archivos o en variables de entorno.
- Escribirlos en logs, en trazas de error, en Sentry o en cualquier telemetría.
- Construir un formulario de tarjeta propio en `supermarket_front` o `supermarket_admin`. El formulario lo renderiza la pasarela.
- Reenviar los datos "de paso" hacia la pasarela desde el backend (proxy). Eso mete a FreshMart dentro del alcance PCI completo.

**El CVV no se almacena jamás, ni cifrado, ni por un instante.** No existe justificación técnica ni de negocio.

### 7.3 Alcance PCI-DSS

Con el diseño de §7.1, FreshMart califica para **SAQ-A**, el cuestionario más liviano: aplica a comercios que externalizan por completo el manejo de datos de tarjeta. Mantener SAQ-A es un objetivo de arquitectura, no un trámite: cualquier atajo que haga pasar un PAN por nuestros servidores nos empuja a SAQ-D, con auditoría, escaneos trimestrales y controles de red que este proyecto no está en condiciones de sostener.

### 7.4 Qué sí se almacena

```sql
-- Diseño de referencia, NO implementado todavía
-- payments (
--   id, order_id, provider, provider_payment_id, provider_token,
--   amount INTEGER,          -- centavos, como todo el dinero del proyecto
--   currency CHAR(3),
--   status payment_status,   -- pending | authorized | captured | refunded | failed
--   card_brand TEXT,         -- 'visa' — dato de display, no identificatorio
--   card_last4 CHAR(4),      -- últimos 4 — permitido por PCI para reconciliación
--   created_at, updated_at
-- )
```

Solo referencias e identificadores de la pasarela, el monto, el estado, y como mucho marca y últimos 4 dígitos para que el usuario reconozca su tarjeta.

### 7.5 Webhooks

Los webhooks de la pasarela son un endpoint público que dispara cambios de estado con impacto económico. Requisitos:

- **Verificación de firma HMAC obligatoria** antes de mirar el cuerpo. Un webhook sin firma válida se descarta con 401 y se registra.
- **Idempotencia**: la pasarela reintenta. Guardar el `provider_event_id` con `UNIQUE` y descartar duplicados.
- **Nunca confiar en el monto del webhook**: contrastarlo contra el `orders.total_price` almacenado.
- Responder rápido (2xx) y procesar de forma asíncrona.

### 7.6 Liquidaciones a supermercados

El dinero que FreshMart cobra al consumidor y luego liquida a la cadena es un flujo **distinto** al pago, con datos bancarios propios (CBU/CVU, alias). Reglas:

- Los datos bancarios de la cadena son **Confidencial** y solo los ve el `owner` y el backend.
- Todo cambio de datos bancarios exige re-autenticación y MFA, notifica por correo al `owner`, y queda registrado en un log de auditoría. **El cambio de CBU es el vector clásico de fraude en marketplaces**: un atacante con la sesión del owner redirige las liquidaciones a su cuenta.
- Ventana de espera antes de liquidar a un CBU recién cambiado.

### 7.7 Antes de mergear cualquier código de pagos

- [ ] Ningún campo de tarjeta aparece en un schema Pydantic ni en un formulario propio.
- [ ] La firma de los webhooks se verifica antes de procesar.
- [ ] Los importes se manejan como `int` en centavos (`NORMAS.md §4.3`), nunca `float`.
- [ ] Los montos se validan contra el pedido en el backend, no se toman del cliente.
- [ ] Las claves de la pasarela están en el gestor de secretos (§6), y la clave secreta jamás en el front.
- [ ] Los pagos en test y en producción usan credenciales distintas y entornos separados.

---

## 8. Transporte y cabeceras

### 8.1 HTTPS en todas partes

TLS 1.2+ obligatorio en los tres despliegues. HSTS con `max-age` de al menos un año. Ningún endpoint acepta HTTP en producción, ni siquiera para redirigir datos sensibles.

### 8.2 CORS

```python
# CORRECTO — orígenes explícitos, métodos y cabeceras acotados
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,          # nunca ["*"] con credentials
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

`allow_origins=["*"]` junto a `allow_credentials=True` es una combinación que los navegadores rechazan, y con orígenes explícitos igual conviene acotar métodos y cabeceras: reduce lo que un XSS en un origen permitido puede intentar.

### 8.3 Cabeceras de respuesta

| Cabecera | Valor |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `X-Frame-Options` | `DENY` (ninguna página de FreshMart se embebe) |
| `Content-Security-Policy` | Ver §8.4 |

### 8.4 CSP

CSP restrictiva en ambos fronts, sin `unsafe-eval`. El uso de Google Fonts en `index.css` obliga a permitir `fonts.googleapis.com` y `fonts.gstatic.com` explícitamente:

```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
font-src 'self' https://fonts.gstatic.com;
img-src 'self' data: https:;
connect-src 'self' https://api.freshmart.com https://*.supabase.co;
frame-ancestors 'none';
```

Cuando se agreguen pagos (§7), `frame-src` deberá permitir el dominio de la pasarela — y solo ese.

---

## 9. Validación de entrada

### 9.1 Pydantic es la frontera

Todo dato que entra a la API se valida con un schema Pydantic antes de llegar a la lógica. No se lee `request.json()` a mano.

```python
# CORRECTO — tipo, longitud y formato declarados
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=120)

# INCORRECTO — sin límite de longitud: un full_name de 10 MB es un DoS barato
full_name: str
```

**Toda cadena de texto lleva `max_length`.** Sin él, cualquier campo es un vector de agotamiento de memoria y disco.

### 9.2 Inyección SQL

El patrón `.eq()` / `.in_()` / `.ilike()` de `supabase-py` parametriza los valores y es seguro. Donde **deja de valer** es al construir filtros como texto:

```python
# CORRECTO
client.table("products").select("*").eq("id", str(product_id))

# INCORRECTO — string interpolado en un filtro crudo
client.table("products").select("*").filter("id", "eq", f"{user_input}")
```

Lo mismo aplica dentro de las funciones plpgsql: usar parámetros, nunca concatenar SQL con `EXECUTE`.

Los identificadores se tipan como `UUID` en la firma del endpoint, así FastAPI rechaza con 422 cualquier cosa que no lo sea antes de tocar la base.

### 9.3 XSS

React escapa por defecto. La regla es simple: **`dangerouslySetInnerHTML` está prohibido** en ambos fronts. Si alguna vez hiciera falta, requiere sanitización y aprobación explícita documentada.

El nombre comercial de una cadena y las notas de un pedido son texto que escribe un usuario y que ve otro: nunca se renderizan como HTML.

### 9.4 Subida de archivos (logos)

- Solo `image/png`, `image/jpeg`, `image/webp` y `image/svg+xml` **rechazado** (los SVG ejecutan scripts).
- Validar el tipo real por los magic bytes, no por la extensión ni por el `Content-Type` que manda el cliente.
- Límite de 2 MB.
- Servir desde Supabase Storage con nombre generado por el servidor, nunca con el nombre original.

### 9.5 Reglas de negocio como validación

Varias validaciones son de seguridad aunque parezcan de negocio:

- `pickup_scheduled` debe caer en el futuro y dentro del horario de la sucursal (`store_hours`).
- Los precios se leen **siempre** de la base al crear el pedido, nunca del cuerpo del request. Un cliente que pueda enviar `unit_price` fija su propio precio.
- Las cantidades y los precios llevan `CHECK (... > 0)` en la base, además de la validación en Pydantic.

---

## 10. Auditoría y logging

### 10.1 Qué se registra

| Evento | Dónde |
|---|---|
| Cambio de estado de un pedido | `order_status_log` (quién, cuándo, nota) |
| Aprobación / rechazo / suspensión de una cadena | `chain_verification_log` |
| Cambio de precio | `price_history` |
| Login exitoso y fallido | Logs de Supabase Auth |
| Alta y baja de staff | Log de aplicación |
| Cambio de datos bancarios (futuro) | Log de aplicación + notificación |

Los logs de auditoría son **append-only**: no se actualizan ni se borran filas.

### 10.2 Qué NUNCA se registra

- Contraseñas, en claro o hasheadas.
- Tokens JWT completos (si hace falta correlacionar, el `sub`, nunca el token).
- `SERVICE_ROLE_KEY` ni ninguna clave.
- Datos de tarjeta, en ninguna forma (§7.2).
- Cuerpos completos de request en endpoints con PII.
- Correos y teléfonos en logs de nivel `INFO`.

```python
# CORRECTO
logger.info("Pedido creado", extra={"order_id": order_id, "user_id": str(user_id)})

# INCORRECTO — vuelca PII al sistema de logs, que suele tener menos controles que la DB
logger.info(f"Pedido de {user.email} ({user.phone}): {payload.model_dump()}")
```

### 10.3 Errores hacia el cliente

Los mensajes de error son genéricos hacia afuera y detallados hacia adentro. `NORMAS.md §1.5` pide fallar visible; eso significa visible **en los logs del servidor**, no filtrar internals al cliente.

```python
# CORRECTO
raise HTTPException(status_code=502, detail="No se pudo completar el registro. Intenta nuevamente.")

# INCORRECTO — filtra estructura de la base y de las dependencias
raise HTTPException(status_code=500, detail=str(exc))
```

En producción, `FastAPI` corre sin `debug` y sin exponer `/docs` públicamente.

### 10.4 Retención

Logs de aplicación 90 días. Logs de auditoría de pedidos y cadenas: lo que exija la normativa fiscal (5 años).

---

## 11. Rate limiting y anti-abuso

### 11.1 Endpoints públicos que crean estado

`POST /auth/register` y `POST /supermarkets/register` son públicos y **crean usuarios reales en Supabase Auth**. Sin límite, permiten agotar la cuota del proyecto, ensuciar la base y usar nuestro dominio para enviar correos de confirmación a terceros.

| Endpoint | Límite |
|---|---|
| `POST /auth/register` | 5 / hora por IP, 3 / día por correo |
| `POST /supermarkets/register` | 3 / día por IP |
| Login | 10 / 15 min por IP y por cuenta, con backoff |
| Recuperación de contraseña | 3 / hora por correo |

Además, CAPTCHA en ambos formularios de registro.

### 11.2 Protección del comparador

`GET /products`, `GET /products/{id}/prices` y `GET /lists/{id}/compare` exponen, sumados, la base de precios completa. Son el activo que nos confían los supermercados (§2.2).

> **`GET /products` aumentó su exposición** al empezar a devolver `best_price`,
> `best_price_supermarket` y `available_in`: una sola página de 100 productos
> ahora entrega el mejor precio de cada uno y quién lo tiene. La autenticación
> sigue siendo obligatoria y `per_page` sigue topeado en 100, pero **falta el
> límite por usuario** — ver D4, que con este cambio pasa a ser más urgente, no
> menos.

- Requieren autenticación **siempre**. Ningún precio se sirve a un usuario anónimo.
- Límite por usuario autenticado: 100 req/min en catálogo, 30 req/min en comparación.
- `per_page` con tope duro (`le=100`, ya aplicado en los endpoints existentes).
- Alertar ante patrones de enumeración: un usuario que recorre el catálogo entero en minutos no está haciendo la compra.

### 11.3 Abuso entre cadenas

Una cadena registrada tiene, por diseño, acceso de lectura a los precios de sus competidores a través de la app de consumidor. Esto es inherente al producto. Lo que se controla:

- El alta pasa por revisión manual (`pending_review`), lo que introduce fricción para un competidor que quiera acceso automatizado.
- Los límites de §11.2 aplican por usuario, sin excepción para staff.
- Una cadena que dispara alertas de scraping se puede pasar a `suspended`.

---

## 12. Privacidad y retención

### 12.1 Marco aplicable

Ley 25.326 de Protección de Datos Personales (Argentina), y GDPR si se opera con residentes de la UE. Ambas comparten principios que aquí son obligatorios: minimización, finalidad, consentimiento y derecho de acceso y supresión.

### 12.2 Minimización

Solo se pide lo necesario para el servicio. Concretamente **no** se recolecta: DNI del consumidor, fecha de nacimiento, género, dirección particular ni geolocalización precisa. Si una feature futura los necesita, se justifica en el PR.

### 12.3 Consentimiento

El registro exige aceptación explícita de Términos y Política de Privacidad, con la fecha y versión aceptadas registradas. Las casillas **no** vienen pre-marcadas.

### 12.4 Derechos del titular

| Derecho | Implementación |
|---|---|
| Acceso | Endpoint de exportación: perfil, listas y pedidos en JSON |
| Rectificación | `PATCH` del perfil |
| Supresión | Ver §12.5 |
| Oposición | Baja de notificaciones sin perder la cuenta |

Plazo de respuesta: 10 días hábiles.

### 12.5 Borrado sin romper el histórico

Un pedido tiene valor fiscal y contable para el supermercado: no se puede borrar porque el cliente se dé de baja. La solución es **anonimizar, no borrar**:

1. Borrar la fila de `auth.users` (cascada a `profiles` y `shopping_lists`).
2. `orders.user_id` pasa a un usuario centinela "cliente dado de baja".
3. `orders.notes` se vacía (puede contener texto libre con PII).
4. `order_items` se conserva íntegro: son productos y precios, no datos personales.

Resultado: el supermercado conserva sus registros de venta y la persona desaparece del sistema.

### 12.6 Datos de los supermercados

El CUIT y la razón social son datos de una persona jurídica, pero el `owner` es una persona física identificable. Se le aplican los mismos derechos sobre sus datos personales, sin que eso borre los registros comerciales de la cadena.

---

## 13. Backups y recuperación

- **PITR (Point-in-Time Recovery)** habilitado en Supabase, con ventana mínima de 7 días.
- **Prueba de restauración trimestral** sobre un proyecto de staging. Un backup que nunca se restauró no es un backup: es una suposición.
- Cifrado en reposo (lo provee Supabase) y en tránsito (§8.1).
- Los backups contienen datos **Confidenciales**: mismo control de acceso que la base productiva. Jamás se descargan a una máquina de desarrollo.
- Objetivos: **RPO 1 hora, RTO 4 horas**.

---

## 14. Dependencias

- `npm audit` y `pip-audit` corren en CI; una vulnerabilidad crítica o alta **frena el merge**.
- Lockfiles (`package-lock.json`, versiones fijadas en `requirements.txt`) siempre versionados.
- Antes de sumar una dependencia: evaluar si ya existe algo equivalente (`NORMAS.md §9`), y mirar mantenimiento, última publicación y número de dependencias transitivas.
- Actualizar `fastapi`, `supabase`, `PyJWT`, `react` y `vite` al menos trimestralmente.
- **`PyJWT` y `@supabase/supabase-js` son críticas**: son las que verifican y gestionan la autenticación. Sus parches de seguridad se aplican de inmediato, no en el ciclo trimestral.

---

## 15. Respuesta a incidentes

### 15.1 Severidades

| Nivel | Ejemplo | Respuesta |
|---|---|---|
| **S1 — Crítico** | `SERVICE_ROLE_KEY` filtrada, fuga de PII, acceso no autorizado a datos de otra cadena | Inmediata, 24/7 |
| **S2 — Alto** | Vulnerabilidad explotable sin exfiltración confirmada | < 24 h |
| **S3 — Medio** | Vulnerabilidad que requiere condiciones poco probables | < 1 semana |
| **S4 — Bajo** | Endurecimiento, mejoras defensivas | Siguiente sprint |

### 15.2 Procedimiento

1. **Contener** — rotar claves, revocar sesiones, deshabilitar el endpoint afectado. Contener antes que investigar.
2. **Evaluar** — qué datos, de cuántas personas o cadenas, en qué ventana temporal.
3. **Erradicar** — corregir la causa raíz, no el síntoma.
4. **Notificar** — ver §15.3.
5. **Post-mortem** — sin culpables, con acciones concretas y fechas. Actualizar este documento si el incidente reveló un hueco en las reglas.

### 15.3 Notificación

- **Agencia de Acceso a la Información Pública**: según lo que exija la normativa vigente ante una brecha de datos personales.
- **Personas afectadas**: sin demora indebida, en lenguaje claro, diciendo qué datos se expusieron y qué deben hacer.
- **Cadenas afectadas**: al `owner`, por correo y por teléfono si es S1.
- Bajo GDPR, cuando aplique: 72 horas a la autoridad de control.

Nunca se minimiza ni se oculta un incidente. La reputación se pierde por el encubrimiento, no por la brecha.

---

## 16. Deuda de seguridad actual

Hallazgos abiertos al 2026-08-21. Cada uno con su ubicación exacta.

| # | Hallazgo | Ubicación | Sev. | Estado |
|---|---|---|---|---|
| D1 | `email_confirm: True` marca el correo como verificado sin que nadie lo confirme. Permite registrarse con la dirección de otra persona. | `app/services/auth_service.py` (`register_consumer`) | Alta | Abierto — el registro de supermercados ya nace con `False` |
| D2 | `JWT_SECRET` es obligatorio en `Settings` pero **no se usa**: la verificación va por JWKS. Un secreto que puede filtrarse sin dar nada a cambio. | `app/core/config.py` | Media | Resuelto en este sprint |
| D3 | CORS con `allow_methods=["*"]` y `allow_headers=["*"]` junto a `allow_credentials=True`. | `app/main.py` | Baja | **Corregido** — métodos y cabeceras enumerados |
| D4 | Sin rate limiting en ningún endpoint. `/auth/register` crea usuarios reales sin límite. | Todo el backend | **Alta** | Abierto |
| D5 | Sin cabeceras de seguridad ni CSP en las respuestas. | `app/main.py`, ambos fronts | Media | Abierto |
| D6 | `orders.pickup_scheduled` acepta cualquier `datetime`, incluso pasado o fuera del horario del local. | `app/schemas/order.py` | Media | Mitigado parcialmente con `store_hours` |
| D7 | Sin MFA para roles privilegiados. | Supabase Auth | Media | Abierto |
| D8 | Sin CAPTCHA en los formularios de registro. | Ambos fronts | Media | Abierto |
| D9 | Sin endpoint de exportación ni de borrado de datos personales (§12.4). | Backend | Media | Abierto |
| D10 | `create_order_with_items` y `cancel_order` tenían `EXECUTE` para `anon`: se podían invocar por PostgREST **sin JWT**, solo con la anon key, pasando cualquier `p_user_id`. Falsificación de pedidos a nombre de otro usuario. | `006_create_order_rpc.sql` | **Crítica** | **Corregido** en `017_revoke_anon_execute.sql` |
| D11 | Protección contra contraseñas filtradas desactivada en Supabase Auth: se aceptan contraseñas que ya aparecieron en brechas conocidas. | Panel de Supabase → Authentication | Media | Abierto — es un toggle, no requiere código |
| D12 | `get_list_or_404` devolvía **500 en vez de 404** para una lista de otro usuario: `.maybe_single()` de postgrest-py devuelve `None`, no un objeto con `.data = None`, así que `result.data` era un `AttributeError`. Un 500 donde va un 404 filtra que la ruta existe y contradice §4.3. El test que lo cubría pasaba porque su mock no imitaba a la librería. | `app/services/list_service.py` | Media | **Corregido** — `core/supabase_client.single_row()` normaliza el caso; los tests usan `NO_ROW` |

D12 es del mismo tipo que D10: los dos se detectaron al contrastar el código
contra el comportamiento **real** —la base en un caso, la librería en el otro— y
en los dos el test que debía cubrirlo pasaba igual. Un mock que no imita a la
dependencia no prueba nada; solo confirma que el mock hace lo que el mock hace.

D10 se detectó al verificar las ACL contra la base real durante este sprint, y
ya está cerrado. Es el ejemplo de por qué §5.4 pide correr esa consulta en cada
release y no confiar en que el `REVOKE` de la migración diga lo correcto: el
comentario de `006` explicaba bien el riesgo, pero le faltaba un rol.

**D4 es ahora la prioridad**: es el hallazgo abierto de mayor severidad y el más barato de cerrar.

---

## 17. Checklist de seguridad para PRs

Complementa el checklist de `NORMAS.md §10`. Se aplica a todo PR que toque backend, base de datos o autenticación.

- [ ] No hay credenciales, tokens ni claves en el código ni en los commits.
- [ ] Toda consulta del backend a datos de un tenant filtra explícitamente por ownership (§5.1).
- [ ] Toda tabla nueva tiene `ENABLE ROW LEVEL SECURITY` y sus policies.
- [ ] Toda función `SECURITY DEFINER` nueva tiene `REVOKE ... FROM PUBLIC, authenticated` y `SET search_path = public` (§5.3).
- [ ] Todo endpoint nuevo declara su dependencia de autenticación y el rol que exige.
- [ ] La pertenencia a una cadena se deriva del JWT, no de un parámetro ni de un header (§4.1).
- [ ] Todo campo de texto en un schema Pydantic tiene `max_length` (§9.1).
- [ ] Los precios se leen de la base, nunca del request (§9.5).
- [ ] Los mensajes de error hacia el cliente no filtran internals (§10.3).
- [ ] Ningún log nuevo escribe PII, tokens ni secretos (§10.2).
- [ ] Los recursos ajenos devuelven 404, no 403 (§4.3).
- [ ] Si toca pagos: se recorrió el checklist de §7.7.
- [ ] Si agrega un endpoint público: tiene rate limiting definido (§11).

---

## 18. Referencias

- OWASP Top 10 (2021) y OWASP API Security Top 10
- OWASP Application Security Verification Standard (ASVS), nivel 2
- PCI-DSS v4.0 — SAQ-A
- Ley 25.326 (Argentina) y su reglamentación
- Supabase — Row Level Security y Hardening the Data API
