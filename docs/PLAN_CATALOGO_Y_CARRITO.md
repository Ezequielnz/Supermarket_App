# FreshMart — Plan: carga de productos y carrito

> **Versión:** 2.0 · **Fecha:** 2026-08-22 · **Estado: IMPLEMENTADO**
>
> Plan de trabajo para el sprint que sigue al onboarding de supermercados.
> Complementa `ARQUITECTURA.md`; las reglas de `NORMAS.md` y `SEGURIDAD.md`
> aplican sin excepción.
>
> La v2.0 registra lo que se implementó y **en qué se corrigió el plan** al
> chocar contra el código y la base reales. Los desvíos están en §11; no se
> reescribió el cuerpo del documento para que se pueda ver qué se planeó y qué
> terminó pasando.

---

## 1. Objetivo

Cerrar el circuito que hoy está cortado por la mitad:

```
HOY                                        AL TERMINAR ESTE SPRINT

Supermercado aprobado                      Supermercado aprobado
      │                                          │
      └── no puede cargar nada                   └── carga productos y precios
                                                       │
Catálogo = seed manual (007)                     Catálogo = lo que cargan los supers
      │                                                │
Consumidor busca por nombre                      Consumidor explora con precios
dentro de una lista                              y agrega al carrito
      │                                                │
      └── compara → pedido                             └── compara → pedido
```

**Alcance deliberadamente corto:** que un supermercado pueda cargar *algunos*
productos para probar el flujo, no su catálogo entero. La importación masiva
(CSV, API, scraping) queda fuera y se menciona en §9 como trabajo posterior.

---

## 2. Las dos decisiones que estructuran el plan

### 2.1 El carrito **es** una lista de compras

No se crea una tabla `carts`. Sería un duplicado exacto de `shopping_lists` y
forkearía el camino al checkout en dos, cuando el que ya existe funciona de
punta a punta (lista → `/lists/{id}/compare` → checkout → `orders`).

Lo único que falta es la noción de "cuál de mis listas es el carrito activo":
se resuelve con una columna `is_cart` y un índice único parcial (§4.2).

| Concepto de producto | Implementación |
|---|---|
| Carrito | `shopping_lists` con `is_cart = true` |
| Agregar al carrito | `POST /lists/{cart_id}/items` |
| Guardar el carrito como lista | `PATCH` que pone `is_cart = false` |
| Vaciar el carrito | Borrar sus items |

### 2.2 El carrito NO se ata a un supermercado

Esta es la decisión importante y conviene tenerla explícita, porque la pregunta
aparece apenas se dibuja la pantalla de explorar.

Cuando el consumidor ve "Leche entera 1L — $1199 en PanelMarket" y toca
*Agregar*, hay dos lecturas posibles:

| Opción | Qué se agrega | Consecuencia |
|---|---|---|
| **A — Recomendada** | El producto **genérico** (`product_id`) | El carrito se sigue pudiendo comparar entre todos los supermercados. El precio que se ve es informativo: "el mejor precio hoy". |
| B | El producto **de ese supermercado** | El carrito queda atado a una tienda. Deja de haber comparador: es una app de delivery. |

Se implementa **A**. Es la propuesta de valor del producto (`ARQUITECTURA.md`
§1: "el sistema compara precios en múltiples supermercados") y además es lo que
el esquema ya modela — `shopping_list_items` guarda `product_id` sin
`supermarket_id`, a propósito.

La pantalla de explorar muestra el mejor precio y qué supermercado lo tiene,
como información para decidir. La elección real de dónde comprar sigue pasando
por el comparador, al final.

> Si en algún momento se quiere B, es un producto distinto y necesita su propio
> plan: cambia el esquema de `shopping_list_items`, el comparador pierde sentido
> y el checkout se simplifica. No es un ajuste, es un pivote.

---

## 3. Estado del que se parte

Verificado sobre el código y la base al 2026-08-21. **Esta tabla describe el
punto de partida, no el estado actual**: todo lo que dice "no existe" o "está
roto" se resolvió en este sprint (ver §7 y §12).

| Pieza | Estado |
|---|---|
| `products` (catálogo global) | Existe, con `ean` UNIQUE, `size_value`, `size_unit` (migración 016) |
| `supermarket_products` (precio por sucursal) | Existe, con `price_history` por trigger (016) |
| Escritura al catálogo | **Imposible hoy**: 003 no creó policies de INSERT/UPDATE y no hay endpoint |
| `GET /products` | Devuelve productos **sin ningún dato de precio** |
| `POST /lists/{id}/items` | Existe, pero ver §4.1 — está roto para "agregar dos veces" |
| Carrito | **No existe.** `CartDrawer.jsx` es código muerto: no lo importa nadie, tiene 4 productos hardcodeados y precios en `float` con `$` |
| `Navbar` | Recibe `cartCount` y `onCartOpen` y no usa ninguno (lo marca el linter) |
| Panel del supermercado | Tiene perfil, sucursales y equipo. Falta la sección de productos |
| `require_approved_chain` | Implementada en `core/security.py`, **todavía sin usar** por ningún endpoint |
| `get_list_or_404` | Devolvía **500 en vez de 404** para una lista ajena: `.maybe_single()` devuelve `None`, no un objeto con `.data = None` (ver §11.4) |
| Precios del seed | Cargados en **pesos** dentro de una columna de centavos, y el front hacía `.toFixed(2)` encima (ver §11.1) |

---

## 4. Fase 0 — Cimientos

Dos arreglos chicos de los que depende todo lo demás. Van primero.

### 4.1 `POST /lists/{id}/items` tiene que ser idempotente por producto

**Es una regresión introducida por la migración 009.** Esa migración agregó

```sql
ALTER TABLE shopping_list_items ADD CONSTRAINT unique_product_per_list UNIQUE (list_id, product_id);
```

para que un producto repetido no rompiera la comparación contándolo dos veces.
Pero `list_service.add_item` hace un `.insert()` plano: agregar el mismo
producto por segunda vez ahora viola el constraint y sale como 500.

Y "agregar dos veces el mismo producto" es exactamente lo que hace un carrito
todo el tiempo.

**Cambio en `backend/app/services/list_service.py`:**

- Si el par `(list_id, product_id)` ya existe → sumar `quantity` a la fila
  existente y devolverla.
- Si no existe → insertar.
- El `upsert` de PostgREST **no** sirve acá: pisaría la cantidad en vez de
  sumarla. Va un `SELECT` y después `UPDATE` o `INSERT`, o una RPC si se quiere
  atomicidad estricta frente a dos pestañas abiertas.

**Nuevo endpoint** para el control de cantidad del carrito (el `−` / `+`):

| Método | Ruta | Descripción |
|---|---|---|
| PATCH | `/lists/{list_id}/items/{item_id}` | Fija `quantity` (no suma). Para sacar el ítem está DELETE |

**Tests** (`backend/tests/test_lists.py`): agregar dos veces suma cantidades;
`PATCH` fija; `PATCH` con `quantity <= 0` da 422 por el `gt=0` del schema.

### 4.2 Migración `020_add_cart_flag.sql`

```sql
ALTER TABLE shopping_lists
  ADD COLUMN is_cart BOOLEAN NOT NULL DEFAULT FALSE;

-- Un solo carrito por usuario. Índice parcial: las listas normales no se ven
-- afectadas. Mismo patrón que idx_one_owner_per_chain (012).
CREATE UNIQUE INDEX idx_one_cart_per_user
  ON shopping_lists(user_id) WHERE is_cart;
```

**Servicio** `get_or_create_cart(user_id)` en `list_service.py`: devuelve la
lista con `is_cart = true` del usuario, y si no existe la crea con nombre
"Mi carrito". Se llama en cada operación de carrito, así el consumidor nunca
tiene que crear nada a mano.

**Endpoints:**

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/lists/cart` | El carrito activo con sus items. Lo crea si no existe |
| POST | `/lists/cart/items` | Atajo de `POST /lists/{cart_id}/items` sin tener que saber el id |
| POST | `/lists/cart/save` | Convierte el carrito en lista guardada (`is_cart = false`); el próximo agregado crea uno nuevo |

> `/lists/cart` va **antes** de `/lists/{list_id}` en el router, o FastAPI
> intenta parsear `"cart"` como UUID y devuelve 422.

---

## 5. Fase 1 — El supermercado carga productos

### 5.1 El problema de fondo: identidad del producto

Si cada supermercado crea su propia fila "Leche entera 1L", el comparador deja
de funcionar: `compare_list` agrupa por `product_id`, así que dos filas
distintas para la misma leche son dos productos que nunca se comparan entre sí.

Hoy eso se sostiene sólo porque el seed 007 cargó los tres supermercados juntos.
En cuanto entren supermercados reales hace falta una clave de identidad, y esa
clave es el **código de barras (EAN)**, que ya está en el esquema desde la 016:

```sql
CREATE UNIQUE INDEX idx_products_ean ON products(ean) WHERE ean IS NOT NULL;
```

**Flujo de resolución** (servicio `catalog_service.resolve_product`):

```
El supermercado carga un producto con EAN
              │
     ¿existe products.ean = X?
              │
      ┌───────┴────────┐
     Sí                No
      │                 │
 usa ese product_id   crea el producto global y usa ese id
      │                 │
      └────────┬────────┘
               │
   upsert en supermarket_products (supermarket_id, product_id, price)
```

Sin EAN (frutas, verdura, fiambrería a granel) el matcheo automático no es
confiable. Para esos casos el backend ofrece candidatos por nombre (`ilike`
sobre el índice trigram de la 009) y el staff **elige explícitamente** entre
vincular a uno existente o crear uno nuevo. Nunca se adivina.

### 5.2 Quién puede escribir el catálogo global — y qué no puede

`products` es una tabla **compartida entre competidores**. Que un supermercado
pueda escribirla es necesario y a la vez es superficie de abuso: renombrar
"Leche La Serenísima 1L" a algo desfavorable afectaría a los precios de todos
los demás que cuelgan de esa fila.

Reglas, en la migración y en el servicio:

- Un supermercado **puede crear** filas nuevas en `products`.
- Un supermercado **NO puede editar ni borrar** filas existentes de `products`.
  Si los datos de un producto global están mal, se reporta y lo corrige un
  admin de plataforma.
- Un supermercado **sólo puede escribir `supermarket_products` de sus propias
  sucursales**. Filtro explícito por `chain_id` en Python: el backend usa
  `service_role` y bypasea RLS (`SEGURIDAD.md` §5.1).
- Sólo cadenas **aprobadas**: estos endpoints usan `require_approved_chain`,
  que hoy está implementada y sin usar.
- El `UNIQUE` sobre `ean` es la red que impide duplicar por código de barras.

Se registra `created_by_chain_id` en `products` para poder auditar quién
introdujo cada fila.

### 5.3 Migración `021_allow_catalog_writes.sql`

```sql
ALTER TABLE products
  ADD COLUMN created_by_chain_id UUID REFERENCES chains(id) ON DELETE SET NULL;

CREATE INDEX idx_products_created_by_chain ON products(created_by_chain_id);
```

Sin policies nuevas de INSERT/UPDATE para `authenticated`: toda escritura sigue
pasando por el backend, igual que `orders`. La 003 ya dejó el catálogo como
solo-lectura para los clientes y eso no cambia.

### 5.4 Backend

**Schemas** (`app/schemas/catalog.py`, nuevo):

- `ProductDraft` — `ean` (8–14 dígitos, opcional), `name`, `brand`, `unit`,
  `size_value`, `size_unit`, `category`, `image_url`
- `SupermarketProductCreate` — `product_id` **o** `product` (el draft), más
  `supermarket_id`, `price` (int, centavos, `gt=0`) e `in_stock`
- `SupermarketProductUpdate` — `price`, `in_stock`
- `SupermarketProductOut` — producto + precio + stock + `updated_at`
- `ProductMatchOut` — candidatos para el matcheo manual

Todo campo de texto con `max_length` (`SEGURIDAD.md` §9.1). Precios `int` en
centavos, nunca `float` (`NORMAS.md` §4.3).

**Servicios:**

| Archivo | Funciones |
|---|---|
| `app/services/catalog_service.py` (nuevo) | `resolve_product`, `search_catalog_candidates` |
| `app/services/supermarket_product_service.py` (nuevo) | `list_my_products`, `add_product`, `update_product`, `remove_product` |

**Endpoints:**

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| GET | `/supermarkets/me/products` | Staff, cadena aprobada | Catálogo propio con precios, paginado, filtrable por sucursal y `?q=` |
| POST | `/supermarkets/me/products` | Owner/Manager, aprobada | Alta: resuelve el producto global y crea el precio |
| PATCH | `/supermarkets/me/products/{id}` | Owner/Manager, aprobada | Cambiar precio o stock |
| DELETE | `/supermarkets/me/products/{id}` | Owner/Manager, aprobada | Dejar de vender ese producto |
| GET | `/supermarkets/me/products/lookup?ean=&q=` | Staff, aprobada | Buscar en el catálogo global antes de crear |

Al hacer `PATCH` de precio, el trigger `record_price_change` (016) archiva solo
el valor anterior en `price_history`. No hay que hacer nada extra.

**Tests** (`backend/tests/test_supermarket_products.py`): un EAN existente
vincula en vez de duplicar; un EAN nuevo crea el producto global; un
`supermarket_id` de otra cadena da 404; un `staff` recibe 403 al intentar crear;
una cadena en `pending_review` recibe 403.

### 5.5 Frontend del panel — `ProductsPage.jsx`

Ruta `/app/products`, con su entrada en el `Sidebar` (icono `Package`).

```
┌───────────────────────────────────────────────────────┐
│ Productos                       [ + Agregar producto ] │
│ Sucursal: [ Todas ▾ ]   Buscar: [___________]          │
├───────────────────────────────────────────────────────┤
│ Producto              Sucursal      Precio    Stock    │
│ Leche entera 1L       Centro       $1.199     [✓]  ⋯   │
│ Huevos L x12          Centro       $2.100     [✓]  ⋯   │
└───────────────────────────────────────────────────────┘
```

- El precio se **edita en línea**: es la operación más frecuente del panel y no
  merece un modal. Se muestra y se ingresa en pesos; la conversión a centavos
  vive en el `service`, en un solo lugar.
- El stock es un toggle que hace `PATCH` directo.
- La tabla scrollea dentro de su contenedor (`overflow-x: auto`); el body nunca
  scrollea en horizontal.

**Modal de alta, en dos pasos**, que es donde vive la resolución de §5.1:

1. **Buscar** — el staff ingresa el EAN o el nombre y el panel llama a `lookup`.
   - Coincidencia exacta por EAN: se muestra el producto encontrado y sólo se
     pide el precio. Es el camino rápido y hay que hacerlo obvio.
   - Candidatos por nombre: se listan para elegir, con un "Ninguno de estos, es
     un producto nuevo" al final.
   - Sin resultados: se pasa al paso 2 en modo alta.
2. **Completar** — nombre, marca, unidad, tamaño, categoría y precio.

Archivos: `pages/app/ProductsPage.jsx` + `.module.css`,
`components/ProductFormModal.jsx` + `.module.css`,
`services/products.service.js`.

---

## 6. Fase 2 — El consumidor explora y agrega al carrito

### 6.1 Backend: `GET /products` con contexto de precio

Hoy `GET /products` devuelve nombre y categoría, nada más. Una pantalla de
explorar sin precios no sirve para decidir.

Se extiende la respuesta con un resumen de precios:

```json
{
  "data": [
    {
      "id": "...",
      "name": "Leche entera 1L",
      "brand": null,
      "unit": "L",
      "category": "lácteos",
      "image_url": null,
      "best_price": 1199,
      "best_price_supermarket": { "id": "...", "name": "PanelMarket Centro" },
      "available_in": 4
    }
  ],
  "total": 128, "page": 1, "per_page": 20
}
```

**Sin N+1.** Dos consultas: la página de productos, y después *una* consulta de
precios con `.in_("product_id", ids_de_la_pagina)`. Con `per_page` topeado en
100 (ya lo está), el volumen queda acotado.

El filtro de visibilidad es **obligatorio**: sólo entran precios de sucursales
activas de cadenas aprobadas. Se reusa `is_supermarket_visible` de
`product_service.py` — la misma función que ya usan `compare_list` y
`get_product_prices`, para que las tres pantallas no puedan divergir.

Parámetros nuevos: `?category=`, `?sort=name|price`.

Un endpoint auxiliar para los filtros:

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/products/categories` | Categorías con productos disponibles |

### 6.2 Frontend: `ExplorePage.jsx`

Ruta `/app/explore`. Es la pantalla que falta: hoy lo más parecido es el
buscador dentro de `ListDetailPage`, que sólo busca por nombre y no muestra
precios.

```
┌────────────────────────────────────────────────────────┐
│ Explorar productos                          🛒 3        │
│ [ Buscar…            ]  Categoría: [ Todas ▾ ]          │
├────────────────────────────────────────────────────────┤
│ ┌────────────┐ ┌────────────┐ ┌────────────┐           │
│ │ 🥛         │ │ 🥚         │ │ 🍞         │           │
│ │ Leche 1L   │ │ Huevos x12 │ │ Pan molde  │           │
│ │ desde      │ │ desde      │ │ desde      │           │
│ │ $1.199     │ │ $2.100     │ │ $1.050     │           │
│ │ PanelMarket│ │ Vital      │ │ Vital      │           │
│ │ en 4 supers│ │ en 3 supers│ │ en 3 supers│           │
│ │ [ Agregar ]│ │ [ Agregar ]│ │ [ Agregar ]│           │
│ └────────────┘ └────────────┘ └────────────┘           │
└────────────────────────────────────────────────────────┘
```

Detalles que importan:

- **"desde $1.199"**, no "$1.199". El precio es el mínimo entre supermercados, y
  decirlo así evita prometer un precio que después cambia al elegir tienda.
- **"en 4 supermercados"** comunica que el producto es comparable. Uno que está
  en un solo super no se puede comparar, y conviene que se note.
- Toque en la tarjeta → detalle con **todos** los precios
  (`GET /products/{id}/prices`, que ya existe y ya filtra por cadena aprobada).
- Búsqueda con `debounce` de 300 ms, igual que `ListDetailPage`.
- Paginación por botón "Ver más".

### 6.3 Frontend: el carrito de verdad

**Borrar `components/CartDrawer.jsx` y reescribirlo.** El actual es una maqueta:
4 productos hardcodeados, precios `float` en dólares y un botón de pago que no
hace nada. No hay nada que rescatar salvo el CSS, que sí se reusa.

El nuevo:

- Se alimenta de `useCart()` (hook nuevo, `hooks/useCart.js`) sobre
  `GET /lists/cart`.
- Cantidades con `−` / `+` → `PATCH /lists/{id}/items/{item_id}` (§4.1).
- Muestra **"Estimado desde $X"**, sumando el mejor precio de cada ítem, con la
  aclaración de que el total real depende del supermercado que se elija. Un
  total en firme sería mentira: el carrito no está atado a una tienda (§2.2).
- El botón principal es **"Comparar precios"**, no "Pagar": lleva a
  `/app/lists/{cart_id}`, que ya tiene el comparador y el camino al checkout.
- "Guardar como lista" → `POST /lists/cart/save`.

**`CartContext.jsx`** (`context/`): estado del carrito compartido entre la
pantalla de explorar, el drawer y el badge del contador, para que agregar un
producto actualice las tres cosas sin recargar.

**Navegación:** una barra de app con Explorar / Mis listas / Pedidos, más el
badge del carrito. Hoy no hay navegación dentro de `/app`: cada página tiene un
enlace "volver" y nada más. `Navbar.jsx` es sólo para la landing pública — sus
props `cartCount` y `onCartOpen`, que hoy no se usan y que el linter marca, se
conectan acá o se eliminan.

Archivos: `pages/app/ExplorePage.jsx` + `.module.css`,
`components/CartDrawer.jsx` (reescrito), `components/AppNav.jsx` + `.module.css`,
`context/CartContext.jsx`, `hooks/useCart.js`, `services/cart.service.js`.
Ruta nueva en `App.jsx`: `/app/explore`.

---

## 7. Orden de ejecución

Cada fila deja el sistema funcionando; se puede parar en cualquiera.

| # | Bloque | Depende de | Se verifica con | Estado |
|---|---|---|---|---|
| 1 | Fase 0: suma de cantidades + `PATCH` de ítem | — | `pytest` | ✅ |
| 2 | Fase 0: migración 020 + `/lists/cart` | 1 | `pytest` + curl | ✅ |
| 3 | Migración 021 + `catalog_service` + endpoints de productos del super | 2 | `pytest` + curl | ✅ |
| 4 | Panel: `ProductsPage` + modal de alta | 3 | Cargar 5 productos a mano | ✅ |
| 5 | `GET /products` con precios + `/products/categories` | 3 | curl | ✅ |
| 6 | Consumidor: `ExplorePage` | 5 | Ver los 5 productos del paso 4 | ✅ |
| 7 | Consumidor: `CartDrawer` + `CartContext` + `AppNav` | 2, 6 | Agregar y comparar | ✅ |
| 8 | Actualizar `ARQUITECTURA.md` §4, §5, §6, §7 y este documento | todo | Lectura | ✅ |

Migraciones aplicadas: **020** (`is_cart`), **021** (`created_by_chain_id`) y
**022** (reparación de datos del seed, ver §11.1).

---

## 8. Verificación de punta a punta

El recorrido que demuestra que el sprint está terminado. Con el backend en
`:8000`, el panel en `:5174` y la app del consumidor en `:5173`:

1. **Aprobar una cadena** — registrarla en `/register` y aprobarla con
   `POST /admin/chains/{id}/review` (procedimiento en `supermarket_admin/README.md`).
2. **Cargar productos** — en `/app/products`, agregar 5:
   - Uno con EAN que **ya existe** en el catálogo → tiene que **vincular**, no
     duplicar. Comprobar por SQL que `products` no creció.
   - Uno con EAN nuevo → crea la fila global, con `created_by_chain_id` cargado.
   - Uno sin EAN, eligiendo un candidato de la lista.
   - Uno sin EAN, creándolo nuevo.
   - Uno con precio más barato que el del seed, para que gane la comparación.
3. **Aislamiento entre cadenas** — con el JWT de otra cadena,
   `GET /supermarkets/me/products` no devuelve ninguno de los 5.
4. **Explorar** — en `/app/explore` como consumidor, los 5 aparecen con su
   precio y su supermercado. El del paso 2.5 figura como el "desde" más barato.
5. **Carrito** — agregar 3. El badge marca 3. Agregar uno **repetido**: la
   cantidad sube a 2 y no aparece una segunda tarjeta. Esto es exactamente lo
   que hoy rompería (§4.1).
6. **Comparar** — "Comparar precios" lleva al comparador con los productos del
   carrito, y el supermercado nuevo aparece en el ranking.
7. **Pedido** — elegir supermercado, confirmar y ver el pedido en
   `/app/orders/{id}`. El circuito completo, de la carga del super al pedido.
8. **Puerta de visibilidad** — suspender la cadena con
   `POST /admin/chains/{id}/review` y recargar `/app/explore`: sus productos
   tienen que desaparecer aunque las filas de precio sigan en la base. Es la
   prueba de que el filtro está en Python y no se confía en RLS.

**Regresión:** `pytest` completo en verde, `npm run build` y `npm run lint` en
los dos frontends, y el advisor de seguridad de Supabase sin hallazgos nuevos.

---

## 9. Fuera de alcance

Anotado para que no se cuele por el costado:

| Tema | Por qué queda afuera |
|---|---|
| Importación masiva (CSV / API / scraping) | Es un sprint propio: parseo, validación por fila, reporte de errores, trabajos en segundo plano. Cargar de a uno alcanza para probar el circuito |
| Imágenes de producto subidas por el super | Necesita Supabase Storage y la validación de subidas de `SEGURIDAD.md` §9.4. Por ahora, `image_url` |
| Panel de pedidos del supermercado | Sigue pendiente del sprint anterior. **Es lo que más falta**: sin él, un pedido creado no lo ve nadie y nunca sale de `pending` |
| Sustitutos y equivalencias entre marcas | La landing lo promete ("Ve cuánto ahorras con sustitutos"). Necesita el catálogo poblado primero |
| Rate limiting | D4 de `SEGURIDAD.md` §16, el hallazgo abierto de mayor severidad. `GET /products` con precios **aumenta** la exposición al scraping (§11.2), así que conviene cerrarlo cerca de este sprint |
| Moderación del catálogo global | Cuando varias cadenas creen productos van a aparecer duplicados sin EAN. Hará falta una herramienta de fusión para el admin de plataforma |

---

## 10. Riesgos

| Riesgo | Mitigación |
|---|---|
| Cada supermercado crea su propia versión del mismo producto y el comparador queda vacío | El EAN como clave de matcheo (§5.1) y el `lookup` obligatorio antes de crear. Es el riesgo central del sprint |
| Un supermercado degrada el catálogo compartido | No puede editar ni borrar filas globales, sólo crear (§5.2). `created_by_chain_id` deja el rastro |
| El "precio desde" confunde cuando el total real es otro | Lenguaje explícito en la UI: "desde", "estimado", y el total en firme sólo después de elegir supermercado |
| `GET /products` con precios se vuelve el endpoint más caro | Dos consultas fijas, `per_page` topeado, y los índices de la 009 (`idx_sp_product_id`, trigram sobre `name`) ya están |
| Exponer precios con más detalle facilita el scraping | Ver D4. La autenticación ya es obligatoria en `/products`; falta el límite por usuario |

---

## 11. Desvíos del plan (v2.0)

Lo que cambió al implementar, y por qué. Cada punto se detectó contrastando el
plan contra el código y la base reales, no en abstracto.

### 11.1 Los precios del seed estaban en pesos, no en centavos

El plan se contradecía a sí mismo: §5.5 dice "se ingresa en pesos; la conversión
a centavos vive en el service", pero el mockup de §6.2 imprime `best_price: 1199`
como "$1.199" — que en centavos es $11,99.

La base decidió el empate: `price` es INTEGER en centavos desde la 003 y
`NORMAS.md` §4.3 lo exige. Lo que estaba mal era **el dato**: el seed (007) cargó
1950 para un litro de aceite, o sea $19,50.

Y del lado del front el mismo error, espejado: `ListDetailPage`, `CheckoutPage` y
`TrackingPage` hacían `total.toFixed(2)` sobre centavos, mostrando "$405000.00"
donde iba "$4.050,00".

**Qué se hizo:** migración **022** multiplica los precios del seed por 100, y un
`lib/money.js` en cada front concentra la conversión. Se corrigieron de paso las
tres pantallas que ya estaban mal. `LandingPage` queda como está: sus números son
datos de demostración en pesos, no vienen de la API.

### 11.2 El carrito se colaba entre "Mis listas"

El plan define el carrito como una fila de `shopping_lists` (§2.1) pero nunca dice
qué hace `GET /lists` con ella. Sin filtrar, "Mi carrito" aparecía mezclado entre
las listas guardadas, y se podía renombrar o borrar como cualquier otra —
volviendo confuso el propio `POST /lists/cart/save`, cuyo sentido es justamente
mover la lista de un estado al otro.

**Qué se hizo:** `list_lists` filtra `is_cart = false`, y `is_cart` se expone en
las respuestas para que el front pueda distinguirlos.

### 11.3 `products.unit` es un ENUM, no texto libre

§5.4 describe `unit` y `size_unit` como campos más del draft. En la base son del
tipo `product_unit` (`kg`, `g`, `L`, `ml`, `un`), creado en la 008. Un valor fuera
de esa lista no es un dato feo: es un error 22P02 de Postgres que sale como **500**.

**Qué se hizo:** `ProductUnit` es un `Literal` en el schema, así falla como 422
señalando el campo. El `<select>` del panel ofrece exactamente esos cinco.

### 11.4 `.maybe_single()` devuelve `None`, no un objeto vacío

No estaba en el plan porque es anterior a él, pero apareció al construir el
carrito encima de `get_list_or_404`.

`postgrest-py` devuelve **`None` como respuesta completa** cuando no hay fila, no
un objeto con `.data = None`. `list_service.get_list_or_404` hacía `result.data`
directo: pedir la lista de otro usuario daba **500 en vez de 404**, que es
exactamente lo que `SEGURIDAD.md` §4.3 prohíbe para un recurso ajeno.

El test que debía cubrirlo pasaba porque su mock devolvía `FakeResult(data=None)`,
que no es lo que hace la librería.

**Qué se hizo:** `core/supabase_client.single_row()` normaliza el caso en un solo
lugar documentado, y los tests usan `NO_ROW` (que es `None` de verdad).

### 11.5 El EAN del seed hacía intestable el matcheo

§8 paso 2 pide cargar "un EAN que ya existe en el catálogo" para comprobar que
vincula en vez de duplicar. Los 6 productos del seed tenían `ean = NULL`: el
camino no se podía ejercitar contra el catálogo inicial, y el primer supermercado
real que cargara leche habría creado una fila paralela sin que nadie lo notara.

**Qué se hizo:** la 022 les carga un EAN-13 de demostración (prefijo 779, GS1
Argentina).

### 11.6 El `AppNav` prometía una pantalla que no existía

§6.3 pide una barra con "Explorar / Mis listas / Pedidos", pero `/app/orders` no
era una ruta: solo existía `/app/orders/:id`. El `useOrders` estaba escrito y sin
usar por ninguna pantalla.

**Qué se hizo:** se agregó una `OrdersPage` mínima sobre `GET /orders` y el hook
que ya existía. Alternativa descartada: sacar "Pedidos" del nav, que dejaba al
usuario sin forma de volver a un pedido pasado.

### 11.7 Precisiones que el plan dejaba ambiguas

| Punto | Resolución |
|---|---|
| `{id}` en `PATCH`/`DELETE /supermarkets/me/products/{id}` | Es el id de la fila de `supermarket_products` (el precio), no el del producto global |
| Qué pasa en Explorar con una cadena suspendida (§8 paso 8) | **El producto queda, el precio desaparece.** `products` es global y compartido: no puede esconderse porque una cadena se suspenda. La UI muestra "Sin precio disponible" y `available_in: 0`. Lo que se verifica es que el precio no se filtre |
| Rol `staff` en `ProductsPage` | Ve los precios pero no los edita (matriz de `SEGURIDAD.md` §4.2): `require_approved_chain` para leer, `require_approved_manager` para escribir |
| EAN que matchea con otro nombre | Gana la fila que ya está; el draft se descarta. Una cadena no reescribe el catálogo de sus competidores (§5.2) |
| `best_price` de los ítems de una lista | Se agregó a `ShoppingListItemOut` para el "estimado desde" del drawer, con una sola consulta por lista |

---

## 12. Verificación ejecutada

No es una lista de intenciones: es lo que se corrió.

| Qué | Resultado |
|---|---|
| `pytest` completo | **61 pasan** (eran 28 antes del sprint) |
| Recorrido de §8 sobre HTTP real y JWT real | **Todo verde**, incluidos los 8 pasos |
| Render de los componentes nuevos (react-dom/server) | **27/27** consumidor, **19/19** panel |
| `npm run build` en ambos fronts | Sin errores |
| `npm run lint` en ambos fronts | Sin errores; se eliminaron los 3 avisos de `no-unused-vars` que había |

Lo que cubrió el recorrido de §8, sobre la base real:

- Una cadena en `pending_review` recibe 403 al tocar su catálogo; aprobada, opera.
- Un EAN existente **vincula** — `products` no creció — y el nombre global no se pisó.
- Un EAN nuevo crea la fila con `created_by_chain_id`.
- Un `supermarket_id` de otra cadena da 404, tanto para leer como para publicar.
- Un `staff` lee el catálogo y recibe 403 al escribir.
- En Explorar, el producto más barato del súper nuevo gana el "desde" y
  `available_in` sube a 4.
- **Agregar un producto repetido al carrito suma la cantidad** (1 → 2) y no crea
  una segunda línea: es exactamente lo que devolvía 500 antes de este sprint.
- `PATCH` fija la cantidad; con `quantity = 0` da 422.
- `GET /lists` no devuelve el carrito.
- El comparador lista al súper nuevo y el pedido se crea y se lee.
- Al suspender la cadena, sus precios desaparecen de Explorar y del comparador
  **aunque las filas sigan en la base** — la prueba de que el filtro está en
  Python y no se confía en RLS.
