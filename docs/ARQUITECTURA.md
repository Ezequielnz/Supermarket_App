# FreshMart — Arquitectura del Proyecto

> **Versión:** 1.0 · **Fecha:** 2026-08-20

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
    ├── ARQUITECTURA.md    # este archivo
    └── NORMAS.md
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
          /auth /products /lists /orders /supermarkets
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
│   ├── Navbar.jsx / .module.css
│   ├── CartDrawer.jsx / .module.css
│   ├── ui/                    # Button, Input, Badge, Modal, Toast
│   └── shared/                # Loader, EmptyState, ProtectedRoute
├── pages/
│   ├── LandingPage.jsx        # / — publica
│   ├── AuthPage.jsx           # /auth
│   └── app/                   # Rutas protegidas
│       ├── DashboardPage.jsx  # /app
│       ├── ListsPage.jsx      # /app/lists
│       ├── ListDetailPage.jsx # /app/lists/:id — comparador
│       ├── CheckoutPage.jsx   # /app/checkout
│       └── TrackingPage.jsx   # /app/orders/:id
├── hooks/
│   ├── useAuth.js
│   ├── useLists.js
│   └── useOrders.js
├── services/
│   ├── api.js                 # Cliente HTTP base (fetch wrapper)
│   ├── auth.service.js
│   ├── lists.service.js
│   ├── products.service.js
│   └── orders.service.js
└── context/
    └── AuthContext.jsx
```

### 4.3 Flujo del Usuario Consumidor

```
[Registro/Login]
      |
[Dashboard] → [Mis Listas]
                   |
         [Crear/editar lista — agrega productos]
                   |
         [Comparar precios por supermercado]
                   |
         [Elegir supermercado + fecha/hora de retiro]
                   |
         [Confirmar pedido]
                   |
         [Seguimiento: Recibido → Preparando → Listo → Completado]
```

---

## 5. Frontend — Supermarket Dashboard (supermarket_admin/)

### 5.1 Stack
Identico a supermarket_front.

### 5.2 Estructura de Directorios

```
supermarket_admin/src/
├── App.jsx
├── index.css
├── components/
│   ├── Sidebar.jsx / .module.css
│   ├── TopBar.jsx / .module.css
│   └── ui/
├── pages/
│   ├── AuthPage.jsx              # /auth
│   └── app/
│       ├── OrdersPage.jsx        # /app/orders
│       ├── OrderDetailPage.jsx   # /app/orders/:id
│       ├── ProductsPage.jsx      # /app/products
│       └── ProfilePage.jsx       # /app/profile
├── hooks/
│   ├── useAdminAuth.js
│   └── useOrders.js
└── services/
    ├── api.js
    ├── auth.service.js
    ├── orders.service.js
    └── products.service.js
```

### 5.3 Flujo del Supermercado

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
│   │           ├── comparison.py
│   │           ├── orders.py
│   │           ├── tracking.py
│   │           └── supermarkets.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── product.py
│   │   ├── shopping_list.py
│   │   ├── order.py
│   │   └── supermarket.py
│   └── services/
│       ├── comparison_service.py
│       ├── order_service.py
│       └── notification_service.py
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
| POST | /auth/login | Login (delega a Supabase) | Publico |
| POST | /auth/supermarket/login | Login del supermercado | Publico |

#### Productos
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| GET | /products | Busqueda ?q=leche | Consumidor |
| GET | /products/{id}/prices | Precios en todos los supers | Consumidor |

#### Listas de compra
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| GET | /lists | Mis listas | Consumidor |
| POST | /lists | Nueva lista | Consumidor |
| GET | /lists/{id} | Detalle | Consumidor |
| PUT | /lists/{id} | Renombrar | Consumidor |
| DELETE | /lists/{id} | Eliminar | Consumidor |
| POST | /lists/{id}/items | Agregar producto | Consumidor |
| DELETE | /lists/{id}/items/{item_id} | Quitar producto | Consumidor |
| GET | /lists/{id}/compare | Comparar precios | Consumidor |

#### Pedidos
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| POST | /orders | Crear pedido | Consumidor |
| GET | /orders | Mis pedidos | Consumidor |
| GET | /orders/{id} | Detalle + estado | Consumidor |
| GET | /orders/{id}/status | Estado actual (polling) | Consumidor |

#### Panel del Supermercado
| Metodo | Ruta | Descripcion | Rol |
|---|---|---|---|
| GET | /supermarkets/orders | Pedidos del super | Staff |
| GET | /supermarkets/orders/{id} | Detalle del pedido | Staff |
| PATCH | /supermarkets/orders/{id}/status | Cambiar estado | Staff |
| GET | /supermarkets/products | Catalogo y precios | Staff |
| PUT | /supermarkets/products/{id} | Actualizar precio | Staff |

---

## 7. Base de Datos (Supabase / PostgreSQL)

### 7.1 Tablas

#### profiles — Datos adicionales del consumidor
```sql
CREATE TABLE profiles (
  id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name  TEXT,
  phone      TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### supermarkets
```sql
CREATE TABLE supermarkets (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  address    TEXT,
  logo_url   TEXT,
  is_active  BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### supermarket_users — Staff autorizado
```sql
CREATE TABLE supermarket_users (
  id             UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  supermarket_id UUID NOT NULL REFERENCES supermarkets(id),
  role           TEXT DEFAULT 'staff'  -- 'admin' | 'staff'
);
```

#### products — Catalogo global
```sql
CREATE TABLE products (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name      TEXT NOT NULL,
  brand     TEXT,
  unit      TEXT,    -- 'kg' | 'L' | 'un' | 'g'
  category  TEXT,
  image_url TEXT
);
```

#### supermarket_products — Precio por supermercado
```sql
CREATE TABLE supermarket_products (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supermarket_id UUID NOT NULL REFERENCES supermarkets(id),
  product_id     UUID NOT NULL REFERENCES products(id),
  price          INTEGER NOT NULL,  -- centavos, evita float
  currency       TEXT DEFAULT 'ARS',
  in_stock       BOOLEAN DEFAULT TRUE,
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(supermarket_id, product_id)
);
```

#### shopping_lists
```sql
CREATE TABLE shopping_lists (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name       TEXT NOT NULL DEFAULT 'Mi lista',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### shopping_list_items
```sql
CREATE TABLE shopping_list_items (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  list_id    UUID NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  quantity   NUMERIC(10,2) NOT NULL DEFAULT 1,
  note       TEXT
);
```

#### orders
```sql
CREATE TABLE orders (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES auth.users(id),
  supermarket_id   UUID NOT NULL REFERENCES supermarkets(id),
  list_id          UUID REFERENCES shopping_lists(id),
  status           TEXT NOT NULL DEFAULT 'pending',
  pickup_scheduled TIMESTAMPTZ NOT NULL,
  total_price      INTEGER,
  notes            TEXT,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);
-- status: 'pending' | 'confirmed' | 'preparing' | 'ready' | 'completed' | 'cancelled'
```

#### order_items
```sql
CREATE TABLE order_items (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id   UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES products(id),
  quantity   NUMERIC(10,2) NOT NULL,
  unit_price INTEGER NOT NULL,
  subtotal   INTEGER NOT NULL
);
```

#### order_status_log — Historial de cambios
```sql
CREATE TABLE order_status_log (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id   UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  status     TEXT NOT NULL,
  changed_by UUID REFERENCES auth.users(id),
  note       TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 7.2 Estados del Pedido

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
| cancelled | Cualquiera | Pedido cancelado |

---

## 8. Autenticacion

- Supabase Auth maneja JWT para ambos tipos de usuario.
- Usuario sin fila en supermarket_users → consumidor.
- Usuario con fila en supermarket_users → staff del supermercado.

```
Consumidor:     Authorization: Bearer <jwt>
Supermercado:   Authorization: Bearer <jwt>
                X-Supermarket-ID: <supermarket_uuid>
```

---

## 9. Logica de Comparacion de Precios

**Endpoint:** GET /api/v1/lists/{id}/compare

1. Obtener todos los shopping_list_items de la lista.
2. Para cada product_id, consultar supermarket_products.
3. Agrupar por supermercado y sumar totales.
4. Si un supermercado no tiene algun producto → marcarlo incompleto.
5. Devolver resultados ordenados de menor a mayor.

**Respuesta:**
```json
{
  "list_id": "...",
  "items_count": 8,
  "results": [
    {
      "supermarket": { "id": "...", "name": "Vital" },
      "total": 104500,
      "currency": "ARS",
      "is_complete": true,
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
JWT_SECRET=...
ALLOWED_ORIGINS=https://app.freshmart.com,https://admin.freshmart.com
```

### Frontend (.env.local)
```
VITE_API_BASE_URL=https://api.freshmart.com/api/v1
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=...
```

---

## 11. Despliegue Sugerido

| Componente | Plataforma | URL |
|---|---|---|
| supermarket_front | Vercel / Netlify | app.freshmart.com |
| supermarket_admin | Vercel / Netlify | admin.freshmart.com |
| backend | Railway / Render | api.freshmart.com |
| Base de datos | Supabase managed | — |
