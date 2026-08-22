# FreshMart — Arquitectura del Proyecto

> **Versión:** 2.0 · **Fecha:** 2026-08-21
>
> Ver también `NORMAS.md` (convenciones), `SEGURIDAD.md` (normativo en materia
> de seguridad) y `PLAN_CATALOGO_Y_CARRITO.md` (plan del próximo sprint).

---

## 1. Visión General

FreshMart tiene dos portales diferenciados:

| Portal | Audiencia | Dominio sugerido |
|---|---|---|
| **Consumer App** | Usuarios finales | `app.freshmart.com` |
| **Supermarket Dashboard** | Administradores de supermercados | `admin.freshmart.com` |

**Propuesta de valor:** El usuario arma listas de compra, el sistema compara precios en múltiples supermercados registrados, el usuario elige dónde comprar y agenda el retiro. El supermercado recibe el pedido, lo arma y notifica cuando está listo.

---

## 2. Estructura del Monorepo

```
Supermarket_App/
├── supermarket_front/     # Consumer App  (React + Vite)
├── supermarket_admin/     # Supermarket Dashboard (React + Vite)
├── backend/               # API REST (Python + FastAPI)
└── docs/
    ├── ARQUITECTURA.md              # este archivo
    ├── NORMAS.md
    ├── SEGURIDAD.md
    └── PLAN_CATALOGO_Y_CARRITO.md   # proximo sprint
```

---

## 3. Diagrama de Alto Nivel

```
Consumer App                    Supermarket Dashboard
app.freshmart.com               admin.freshmart.com
React + Vite                    React + Vite
      |                               |
      +----------+  REST  +-----------+
                 |        |
          FastAPI Backend
          api.freshmart.com
          /auth /products /lists /orders /supermarkets /admin
                 |
          Supabase
          PostgreSQL + Auth
```

---

## 4. Frontend — Consumer App (supermarket_front/)

### 4.1 Stack
- React 18 + Vite, CSS Modules, lucide-react
- react-router-dom v6 (rutas protegidas)

### 4.2 Estructura de Directorios

```
supermarket_front/src/
├── App.jsx                    # Router raiz
├── index.css                  # Design tokens CSS globales
├── components/
│   ├── Navbar.jsx / .module.css      # solo la landing publica
│   ├── AppNav.jsx / .module.css      # navegacion de /app + badge del carrito
│   ├── CartDrawer.jsx / .module.css
│   └── shared/                # ProtectedRoute
├── pages/
│   ├── LandingPage.jsx        # / — publica
│   ├── AuthPage.jsx           # /auth
│   └── app/                   # Rutas protegidas
│       ├── DashboardPage.jsx  # /app
│       ├── ExplorePage.jsx    # /app/explore — catalogo con precios
│       ├── ListsPage.jsx      # /app/lists
│       ├── ListDetailPage.jsx # /app/lists/:id — comparador
│       ├── CheckoutPage.jsx   # /app/checkout
│       ├── OrdersPage.jsx     # /app/orders
│       └── TrackingPage.jsx   # /app/orders/:id
├── hooks/
│   ├── useAuth.js
│   ├── useCart.js
│   ├── useLists.js
│   └── useOrders.js
├── lib/
│   └── money.js               # centavos <-> pesos, en un solo lugar
├── services/
│   ├── api.js                 # Cliente HTTP base (fetch wrapper)
│   ├── auth.service.js
│   ├── cart.service.js
│   ├── lists.service.js
│   ├── products.service.js
│   └── orders.service.js
└── context/
    ├── AuthContext.jsx
    └── CartContext.jsx        # carrito compartido entre explorar/drawer/badge
```

> **`lib/` es una carpeta nueva** respecto de la estructura original, y la
> justificacion que pide NORMAS.md §9 es esta: `money.js` no habla con la API
> (no es un `service`) ni renderiza (no es un `component`), y lo usan pantallas
> que no comparten servicio. Tenerlo suelto en cada una fue justamente el bug
> que arrastraba el proyecto — `total.toFixed(2)` sobre centavos mostraba
> $405000.00 donde iba $4.050,00.

### 4.3 Flujo del Usuario Consumidor

```
[Registro/Login]
      |
[Dashboard] ────────────────┬──────────────────┐
      |                     |                  |
[Explorar productos]   [Mis Listas]       [Mis Pedidos]
 — precio "desde" y          |                  |
   en cuantos supers         |                  |
      |                      |                  |
 [Agregar al carrito] ───────┤                  |
      |                      |                  |
 [Carrito (drawer)]          |                  |
  — cantidades, estimado     |                  |
      |                      |                  |
      └──> "Comparar precios" <──[Crear/editar lista]
                   |
         [Comparar precios por supermercado]
                   |
         [Elegir supermercado + fecha/hora de retiro]
                   |
         [Confirmar pedido]
                   |
         [Seguimiento: Recibido → Preparando → Listo → Completado]
```

**El carrito ES una lista de compras** (`shopping_lists.is_cart = true`), no una
tabla aparte. Por eso el carrito y una lista guardada desembocan en el mismo
comparador y el mismo checkout, en vez de tener dos caminos paralelos. El
carrito **no se ata a un supermercado**: se agregan productos genericos
(`product_id`) y la eleccion de donde comprar sigue pasando por el comparador,
al final. Ver `PLAN_CATALOGO_Y_CARRITO.md` §2.

---

## 5. Frontend — Supermarket Dashboard (supermarket_admin/)

### 5.1 Stack
Identico a supermarket_front.

### 5.2 Estructura de Directorios

Implementado (sprint de onboarding):

```
supermarket_admin/src/
├── App.jsx                     # hash-routing publico + HashRouter en /app
├── index.css                   # design tokens; --primary azul (el consumidor es verde)
├── components/
│   ├── Sidebar.jsx / .module.css
│   ├── TopBar.jsx / .module.css
│   ├── ProductFormModal.jsx / .module.css   # alta en 2 pasos: buscar y cargar
│   ├── ui/                     # Button, Input, Field, Badge
│   └── shared/
│       ├── ProtectedRoute.jsx  # exige sesion
│       └── ApprovedRoute.jsx   # ademas exige chain.status === 'approved'
├── pages/
│   ├── LandingPage.jsx         # /          — publica
│   ├── AuthPage.jsx            # /auth      — login
│   ├── RegisterPage.jsx        # /register  — wizard de 4 pasos
│   ├── PendingReviewPage.jsx   # /pending   — estado de la solicitud
│   └── app/
│       ├── AppLayout.jsx       # sidebar + outlet
│       ├── ProfilePage.jsx     # /app/profile
│       ├── StoresPage.jsx      # /app/stores
│       ├── ProductsPage.jsx    # /app/products — catalogo y precios
│       └── TeamPage.jsx        # /app/team   (solo owner)
├── hooks/
│   └── useAdminAuth.js
├── lib/
│   └── money.js                # copia de supermarket_front (NORMAS §2)
├── services/
│   ├── api.js                  # copia literal de supermarket_front (NORMAS §2)
│   ├── supabaseClient.js       # idem
│   ├── auth.service.js
│   ├── products.service.js
│   └── supermarket.service.js
└── context/
    └── AdminAuthContext.jsx
```

Pendiente para el siguiente sprint: `OrdersPage` y `OrderDetailPage` del
supermercado, mas la UI de moderacion de plataforma (hoy la aprobacion se hace
por `POST /admin/chains/{id}/review`). **El panel de pedidos es lo que mas
falta**: sin el, un pedido creado no lo ve nadie del lado del supermercado y
nunca sale de `pending`.

### 5.3 Onboarding del Supermercado

```
[Landing /] → [Registro /register — wizard]
                 1. Datos del responsable
                 2. Datos de la cadena (razon social, CUIT)
                 3. Primera sucursal + horarios
                 4. Revision y envio
                        |
              [Confirmacion de correo]
                        |
              [Login] → chain.status ?
                        |
        ┌───────────────┼────────────────┐
   pending_review    approved      rejected / suspended
        |               |                 |
   [/pending]      [/app/profile]    [/pending + motivo]
```

### 5.4 Flujo Operativo (siguiente sprint)

```
[Login]
  |
[Dashboard de pedidos — ordenados por hora de retiro]
  |
[Detalle del pedido]
  — Numero, lista de productos, hora de retiro, cliente
  |
[Marcar como "Listo para retirar"]
  → Cliente recibe notificacion
  |
[Cliente retira → Marcar "Completado"]
```

---

## 6. Backend (backend/)

### 6.1 Stack
- Python 3.12+, FastAPI, Pydantic v2
- Supabase Python SDK, python-dotenv, uvicorn

### 6.2 Estructura de Directorios

```
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py              # Settings con Pydantic BaseSettings
│   │   ├── security.py            # Verificacion JWT Supabase
│   │   └── supabase_client.py     # Singleton del cliente Supabase
│   ├── api/
│   │   └── v1/
│   │       ├── router.py
│   │       └── endpoints/
│   │           ├── auth.py
│   │           ├── products.py
│   │           ├── lists.py
│   │           ├── orders.py
│   │           ├── supermarkets.py     # onboarding y panel
│   │           └── admin.py            # moderacion de plataforma
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── product.py
│   │   ├── shopping_list.py
│   │   ├── order.py
│   │   └── supermarket.py
│   └── services/
│       ├── auth_service.py
│       ├── product_service.py
│       ├── list_service.py
│       ├── comparison_service.py
│       ├── order_service.py
│       ├── supermarket_auth_service.py   # registro y moderacion
│       └── supermarket_service.py        # perfil, sucursales, equipo
├── migrations/                # SQL numerado, ver NORMAS.md §5.2
├── tests/
├── requirements.txt
├── requirements-dev.txt
└── .env.example
```

### 6.3 Endpoints de la API

**Base:** `https://api.freshmart.com/api/v1`

#### Auth
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| POST | /auth/register | Registro consumidor | Publico |

> El login **no** tiene endpoint propio, ni el del consumidor ni el del
> supermercado: va directo contra Supabase (`signInWithPassword`) desde cada
> frontend. Es la excepcion explicita de NORMAS.md §2.

#### Productos
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| GET | /products | Busqueda ?q= &category= &sort=name\|price, con mejor precio | Consumidor |
| GET | /products/categories | Categorias del catalogo | Consumidor |
| GET | /products/{id}/prices | Precios en todos los supers | Consumidor |

> `GET /products` devuelve, ademas del producto, `best_price`,
> `best_price_supermarket` y `available_in`. Son **dos consultas fijas** (la
> pagina de productos y una sola de precios sobre esos ids), no una por
> producto. Solo entran precios de sucursales activas de cadenas aprobadas: el
> filtro esta en Python porque el backend bypasea RLS (SEGURIDAD.md §5.1).

#### Listas de compra
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| GET | /lists | Mis listas | Consumidor |
| POST | /lists | Nueva lista | Consumidor |
| GET | /lists/{id} | Detalle | Consumidor |
| PUT | /lists/{id} | Renombrar | Consumidor |
| DELETE | /lists/{id} | Eliminar | Consumidor |
| POST | /lists/{id}/items | Agregar producto (suma si ya esta) | Consumidor |
| PATCH | /lists/{id}/items/{item_id} | Fijar cantidad | Consumidor |
| DELETE | /lists/{id}/items/{item_id} | Quitar producto | Consumidor |
| GET | /lists/{id}/compare | Comparar precios | Consumidor |

#### Carrito
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| GET | /lists/cart | Carrito activo con sus items; lo crea si no existe | Consumidor |
| POST | /lists/cart/items | Agregar al carrito sin conocer su id | Consumidor |
| POST | /lists/cart/save | Guardarlo como lista (`is_cart = false`) | Consumidor |

> Estas rutas van declaradas **antes** de `/lists/{list_id}` en el router: al
> reves, FastAPI intenta parsear `"cart"` como UUID y devuelve 422.
>
> `POST /lists/{id}/items` es **idempotente por producto**: agregar dos veces el
> mismo producto suma la cantidad. Antes hacia un INSERT plano y violaba el
> `unique_product_per_list` de la 009 con un 500 — y agregar dos veces lo mismo
> es lo que hace un carrito todo el tiempo. Para fijar la cantidad (el control
> − / +) esta el `PATCH`.

#### Pedidos
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| POST | /orders | Crear pedido | Consumidor |
| GET | /orders | Mis pedidos | Consumidor |
| GET | /orders/{id} | Detalle + estado | Consumidor |
| GET | /orders/{id}/status | Estado actual (polling) | Consumidor |

#### Onboarding y Panel del Supermercado
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| POST | /supermarkets/register | Alta de una cadena | Publico |
| GET | /supermarkets/me | Perfil de la cadena y estado de revision | Staff |
| PATCH | /supermarkets/me | Editar perfil de la cadena | Owner |
| GET | /supermarkets/me/stores | Sucursales | Staff |
| POST | /supermarkets/me/stores | Agregar sucursal | Owner/Manager |
| GET | /supermarkets/me/stores/{id} | Detalle con horarios | Staff |
| PATCH | /supermarkets/me/stores/{id} | Editar sucursal y horarios | Owner/Manager |
| GET | /supermarkets/me/users | Equipo de la cadena | Owner |
| POST | /supermarkets/me/users | Invitar a un empleado | Owner |
| GET | /supermarkets/me/products | Catalogo propio con precios | Staff, cadena aprobada |
| GET | /supermarkets/me/products/lookup | Buscar en el catalogo global por `?ean=` o `?q=` | Staff, cadena aprobada |
| POST | /supermarkets/me/products | Empezar a vender un producto | Owner/Manager, aprobada |
| PATCH | /supermarkets/me/products/{id} | Cambiar precio o stock | Owner/Manager, aprobada |
| DELETE | /supermarkets/me/products/{id} | Dejar de venderlo | Owner/Manager, aprobada |

> El `{id}` de los dos ultimos es el de la fila de `supermarket_products` (el
> precio), **no** el del producto global.
>
> Son los primeros endpoints que usan `require_approved_chain`: publicar
> precios es operar, y una cadena en revision, rechazada o suspendida no opera.
> El rol `staff` lee pero no escribe (`require_approved_manager`), segun la
> matriz de SEGURIDAD.md §4.2.

#### Moderacion de Plataforma
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| GET | /admin/chains?status= | Cola de solicitudes | Admin plataforma |
| POST | /admin/chains/{id}/review | Aprobar / rechazar / suspender | Admin plataforma |

#### Siguiente sprint (aun no implementados)
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| GET | /supermarkets/me/orders | Pedidos del super | Staff |
| PATCH | /supermarkets/me/orders/{id}/status | Cambiar estado | Staff |

---

## 7. Base de Datos (Supabase / PostgreSQL)

> **La fuente de verdad del esquema son las migraciones**, en
> `backend/migrations/`. Esta seccion es el mapa y el porque; el DDL exacto no
> se duplica aca para que no quede desactualizado.

### 7.1 Modelo

```
chains ──1:N──> supermarkets ──1:N──> store_hours
   │                 │
   │                 ├──1:N──> supermarket_products ──N:1──> products
   │                 │              │
   │                 │              └──> price_history
   │                 │
   │                 └──1:N──> orders ──1:N──> order_items
   └──1:N──> supermarket_users        └──1:N──> order_status_log

auth.users ──1:1──> profiles            (consumidor)
auth.users ──1:1──> supermarket_users   (staff)
auth.users ──1:1──> platform_admins     (operador de FreshMart)
```

**`chains` es la empresa; `supermarkets` es el local.** "Carrefour" es una
cadena; "Carrefour Rivadavia 1234" es un supermarket. Los precios y los pedidos
cuelgan del local, que es donde el cliente retira.

### 7.2 Tablas

| Tabla | Rol | Migracion |
|---|---|---|
| `profiles` | Perfil del consumidor (1:1 con auth.users) | 001 |
| `chains` | Cadena: razon social, CUIT, estado de verificacion | 010 |
| `supermarkets` | Sucursal: direccion estructurada, geo | 003, 010 |
| `store_hours` | Horarios por dia de cada sucursal | 010 |
| `supermarket_users` | Staff, con su rol y su cadena | 012 |
| `platform_admins` | Operadores de FreshMart | 013 |
| `chain_verification_log` | Auditoria de aprobaciones y rechazos | 013 |
| `products` | Catalogo global (con EAN para machear entre cadenas) | 003, 016, 021 |
| `supermarket_products` | Precio vigente por sucursal y producto | 003 |
| `price_history` | Precios anteriores, por trigger | 016 |
| `shopping_lists` / `shopping_list_items` | Listas del consumidor, y el carrito (`is_cart`) | 004, 020 |
| `orders` / `order_items` / `order_status_log` | Pedidos y su historial | 005 |

**`products` es una tabla compartida entre competidores.** Todos los precios de
"Leche entera 1L" cuelgan de la misma fila: eso es lo que hace posible el
comparador. De ahi las reglas de escritura, que se aplican en
`catalog_service.py` porque el backend bypasea RLS:

- Una cadena **puede crear** filas nuevas en `products`.
- Una cadena **no puede editar ni borrar** filas existentes. Si un producto
  global esta mal, lo corrige un admin de plataforma. Cuando el EAN que carga
  matchea uno que ya existe, el resto de los datos que manda se **descartan**:
  gana el que estaba.
- `created_by_chain_id` (021) deja el rastro de quien introdujo cada fila.
- El `UNIQUE` sobre `ean` (016) es la red que impide duplicar por codigo de
  barras. Sin EAN no hay matcheo automatico: el backend ofrece candidatos por
  nombre y el staff elige explicitamente. Nunca se adivina.

**El carrito no es una tabla.** Es `shopping_lists` con `is_cart = true`, con un
indice unico parcial (`idx_one_cart_per_user`) que permite uno solo por usuario.
`GET /lists` filtra `is_cart = false` para no mezclarlo con las listas
guardadas.

### 7.3 Tipos enumerados

Definidos en la migracion 008. Antes eran `TEXT` libre, sin nada que impidiera
un `status = 'lsito'`.

| Tipo | Valores |
|---|---|
| `order_status` | `pending`, `confirmed`, `preparing`, `ready`, `completed`, `cancelled` |
| `chain_status` | `pending_review`, `approved`, `rejected`, `suspended` |
| `staff_role` | `owner`, `manager`, `staff` |
| `product_unit` | `kg`, `g`, `L`, `ml`, `un` |

### 7.4 Reglas transversales

- **Dinero en centavos como `INTEGER`**, nunca `FLOAT` (NORMAS.md §5.1), con
  `CHECK (... > 0)`.
- **`created_at` / `updated_at` en toda tabla principal**, con `updated_at`
  mantenido por el trigger `set_updated_at` (009), no a mano.
- **Todas las FK tienen indice**: Postgres no los crea solo (009).
- **Toda FK declara su `ON DELETE`** de forma explicita (019). Los pedidos usan
  `RESTRICT`: son comprobantes fiscales y no desaparecen porque el cliente se de
  de baja. La baja de un consumidor se resuelve anonimizando (SEGURIDAD.md §12.5).
- **`orders.order_number`**: numero corto y legible, ademas del UUID. Un UUID no
  se canta en el mostrador.

### 7.5 Estados de la cadena

```
pending_review ──> approved ──> suspended
      │                ^            │
      │                └────────────┘
      └──> rejected ──> (corrige y reenvia)
```

| Estado | Significado | Visible en el comparador |
|---|---|---|
| `pending_review` | Registrada, esperando revision | No |
| `approved` | Verificada, operativa | **Si** |
| `rejected` | Rechazada, con motivo obligatorio | No |
| `suspended` | Dada de baja temporalmente | No |

**Solo las sucursales de cadenas `approved` entran al comparador.** Eso se
aplica en dos lugares y los dos son necesarios: las policies de la migracion 015
(para clientes que usen la anon key) y un filtro explicito en Python
(`is_supermarket_visible` en `product_service.py`), porque el backend usa
`service_role` y bypasea RLS. Ver SEGURIDAD.md §5.1.

### 7.6 Estados del Pedido

```
pending → confirmed → preparing → ready → completed
   └─────────────────────────────→ cancelled
```

| Estado | Disparado por | Significado |
|---|---|---|
| pending | Sistema al crear | Pedido recibido |
| confirmed | Supermercado | Super acepto |
| preparing | Supermercado | Armando la bolsa |
| ready | Supermercado | Bolsa lista para retirar |
| completed | Supermercado | Cliente retiro |
| cancelled | Consumidor o supermercado | Pedido cancelado |

### 7.7 Funciones RPC

Toda escritura que toque varias tablas pasa por una funcion `SECURITY DEFINER`,
para que sea atomica:

| Funcion | Escribe en | Migracion |
|---|---|---|
| `create_order_with_items` | orders, order_items, order_status_log | 006 |
| `cancel_order` | orders, order_status_log | 006 |
| `register_supermarket_chain` | chains, supermarkets, store_hours, supermarket_users, chain_verification_log | 014 |
| `review_chain` | chains, chain_verification_log | 014 |

Todas revocan `EXECUTE` de `PUBLIC`, `anon` y `authenticated`, y lo otorgan solo
a `service_role`. **Los tres roles, no dos**: Supabase otorga un grant directo a
`anon` por default privileges que sobrevive al `REVOKE ... FROM PUBLIC`. Ver
migracion 017 y SEGURIDAD.md §5.3.

## 8. Autenticacion

- Supabase Auth maneja JWT para los tres tipos de usuario.
- El backend verifica los tokens contra el **JWKS publico** del proyecto
  (ES256/RS256), no con un secreto compartido. Por eso no existe `JWT_SECRET`.
- El tipo de cuenta se deriva de la base, no del token:

| Ubicacion de la fila | Tipo de cuenta | Dependencia FastAPI |
|---|---|---|
| Ninguna tabla especial | Consumidor | `get_current_user` |
| `supermarket_users` | Staff de supermercado | `get_current_staff` |
| `platform_admins` | Admin de plataforma | `get_current_platform_admin` |

```
Todos:  Authorization: Bearer <jwt>
```

> **Cambio respecto de la version 1.0.** Esta ya no propone el header
> `X-Supermarket-ID: <uuid>`. Un identificador de tenant que elige el cliente
> es una escalada horizontal directa: el staff de la cadena A manda el UUID de
> la B y opera sobre datos ajenos. La pertenencia se resuelve consultando
> `supermarket_users` por el `sub` del JWT. Ver `SEGURIDAD.md` §4.1.

El alta de una cuenta de staff pasa `account_type: supermarket_staff` en el
`user_metadata`, lo que hace que el trigger `handle_new_user` **no** le cree
una fila en `profiles`: un usuario es consumidor XOR staff, nunca las dos cosas.

### 8.1 Roles del staff

| Rol | Puede |
|---|---|
| `owner` | Perfil fiscal de la cadena, sucursales, equipo. Uno solo por cadena. |
| `manager` | Sucursales y catalogo de su cadena. |
| `staff` | Operar pedidos. Solo lectura del resto. |

---

## 9. Logica de Comparacion de Precios

**Endpoint:** GET /api/v1/lists/{id}/compare

El consumidor **no lo dispara a mano**: el front lo llama solo al abrir la
lista (`useCompare`), con cache por lista de 5 minutos. El boton "Actualizar
precios" fuerza el recalculo.

1. Obtener todos los shopping_list_items de la lista, **ordenados por
   `(created_at, id)`**. Sin ORDER BY, PostgREST devuelve los items en orden no
   determinista y la lista guardada se ve distinta en cada visita (migracion
   023).
2. Para cada product_id, consultar supermarket_products con stock.
3. **Descartar los supermercados inactivos y los de cadenas no aprobadas**
   (`is_supermarket_visible`). Sin este paso, una cadena en revision apareceria
   en el comparador apenas cargue precios: el backend usa `service_role` y las
   policies de la migracion 015 no lo alcanzan.
4. Agrupar por supermercado y sumar totales **redondeando por item**
   (`round(price * quantity)`), igual que `order_service` al crear el pedido.
   Redondear una sola vez sobre la suma hacia que el comparador prometiera un
   total y el pedido cobrara otro cuando las cantidades son decimales.
5. Si un supermercado no tiene algun producto (o lo tiene sin stock), **nombrar
   ese producto en `missing`** y omitirlo de su total. Nunca se inventa un
   precio. Un supermercado que no tiene NINGUN producto de la lista no aparece.
6. Devolver los **completos primero** y, dentro de cada grupo, de menor a mayor
   total. Un total parcial no es comparable con uno completo: ordenar todo junto
   por precio pondria arriba al supermercado al que le falta media lista.

Un resultado incompleto **no ofrece el boton de checkout**: `POST /orders`
devuelve 409 si falta stock de algun producto, asi que elegirlo llevaria a un
error garantizado.

**Respuesta:**
```json
{
  "list_id": "...",
  "items_count": 8,
  "generated_at": "2026-08-22T14:05:00Z",
  "results": [
    {
      "supermarket": { "id": "...", "name": "Vital" },
      "total": 104500,
      "currency": "ARS",
      "is_complete": true,
      "items_covered": 8,
      "items_total": 8,
      "missing": [],
      "items": [
        { "product_id": "...", "product_name": "Leche 1L", "price": 1250, "in_stock": true }
      ]
    }
  ]
}
```

---

## 10. Variables de Entorno

### Backend (.env)
```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
ALLOWED_ORIGINS=https://app.freshmart.com,https://admin.freshmart.com
```

> Ya **no** hay `JWT_SECRET`: la verificacion va contra el JWKS publico
> (§8), asi que era un secreto obligatorio que ningun codigo leia — riesgo de
> filtracion sin contrapartida. Ver SEGURIDAD.md §6.2 y D2 en §16.

Plantilla en `backend/.env.example`.

### Frontend (.env.local) — igual en los dos frontends
```
VITE_API_BASE_URL=https://api.freshmart.com/api/v1
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=...
```

En local: `supermarket_front` corre en el puerto **5173** y `supermarket_admin`
en el **5174**. Los dos tienen que estar en `ALLOWED_ORIGINS` del backend.

---

## 11. Despliegue Sugerido

| Componente | Plataforma | URL |
|---|---|---|
| supermarket_front | Vercel / Netlify | app.freshmart.com |
| supermarket_admin | Vercel / Netlify | admin.freshmart.com |
| backend | Railway / Render | api.freshmart.com |
| Base de datos | Supabase managed | — |
