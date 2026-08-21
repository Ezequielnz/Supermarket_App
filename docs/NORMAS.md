# FreshMart — Normas del Proyecto

> Documento de referencia para desarrolladores y agentes de IA.  
> Toda contribucion al proyecto DEBE respetar estas normas sin excepcion.
>
> En materia de seguridad, `SEGURIDAD.md` tiene precedencia sobre este documento.

---

## 1. Principios Generales

1. **Claridad sobre cleverness.** El codigo debe ser facil de leer por un humano sin contexto.
2. **Una responsabilidad por archivo.** Cada componente, servicio o endpoint tiene un proposito unico y acotado.
3. **Consistencia ante todo.** Los patrones establecidos en este documento se aplican en todo el proyecto, sin excepciones por "conveniencia".
4. **Sin magia oculta.** Evitar abstracciones excesivas que esconden el flujo real del programa.
5. **Falla rapido y visible.** Los errores deben surgir temprano, con mensajes claros. No silenciar excepciones.

---

## 2. Estructura del Proyecto

El proyecto es un **monorepo** con tres sub-proyectos independientes:

```
Supermarket_App/
├── supermarket_front/    # Consumer App
├── supermarket_admin/    # Supermarket Dashboard
├── backend/              # FastAPI API
└── docs/                 # Documentacion
    ├── ARQUITECTURA.md
    ├── NORMAS.md          # este archivo
    ├── SEGURIDAD.md
    └── PLAN_CATALOGO_Y_CARRITO.md
```

- **Nunca** mezclar codigo de `supermarket_front` con `supermarket_admin`. Son
  dos productos distintos. Los archivos que coinciden (`api.js`,
  `supabaseClient.js`, `ProtectedRoute.jsx`) estan **duplicados a proposito**:
  duplicar es mas barato que un paquete compartido que acopla los dos ciclos de
  release.
- **Nunca** poner logica de negocio en el frontend; esta va en el backend.
- **Nunca** hacer llamadas directas a Supabase desde el frontend; todas las operaciones pasan por el backend.

> **Excepcion:** Supabase Auth puede usarse directamente desde el frontend solo para login/logout/refresh de sesion.

---

## 3. Frontend — Convenciones React

### 3.1 Nombrado

| Elemento | Convencion | Ejemplo |
|---|---|---|
| Componentes | PascalCase | `OrderCard.jsx` |
| Paginas | PascalCase + sufijo `Page` | `ListDetailPage.jsx` |
| Hooks | camelCase + prefijo `use` | `useOrders.js` |
| Servicios | camelCase + sufijo `.service` | `orders.service.js` |
| CSS Modules | mismo nombre que el componente | `OrderCard.module.css` |
| Context | PascalCase + sufijo `Context` | `AuthContext.jsx` |
| Variables/funciones | camelCase | `fetchOrderById` |
| Constantes globales | UPPER_SNAKE_CASE | `ORDER_STATUSES` |

### 3.2 Estructura de un Componente

El orden interno de un archivo `.jsx` es siempre:

```jsx
// 1. Imports externos
import { useState } from 'react'
import { ArrowRight } from 'lucide-react'

// 2. Imports internos
import { fetchOrders } from '../services/orders.service'
import styles from './MyComponent.module.css'

// 3. Constantes del modulo (fuera del componente)
const MAX_ITEMS = 10

// 4. Componente principal (default export siempre al final del archivo)
export default function MyComponent({ prop1, prop2 }) {
  // 4a. Estado
  // 4b. Efectos
  // 4c. Handlers
  // 4d. Render
  return (...)
}
```

### 3.3 CSS Modules

- **Cada componente tiene su propio `.module.css`.** No hay CSS global excepto `index.css`.
- `index.css` contiene **unicamente** las variables CSS (design tokens) y los resets base.
- Los nombres de clase en CSS Modules usan **camelCase**: `.cardTitle`, `.heroAccent`.
- **No usar estilos inline** salvo para valores dinamicos que provienen de datos (ej: color de fondo variable).
- Usar `clamp()` para tipografia fluida y `env(safe-area-inset-*)` para padding en moviles.

```css
/* CORRECTO */
.heroTitle {
  font-size: clamp(2rem, 6vw, 5rem);
  padding-left: max(1.25rem, env(safe-area-inset-left));
}

/* INCORRECTO */
<div style={{ fontSize: '3rem' }}>
```

### 3.4 Design Tokens

Todos los colores, radios y espaciados deben usar las variables CSS definidas en `index.css`:

```css
/* Variables disponibles */
--background    --foreground
--card          --card-foreground
--primary       --primary-foreground
--secondary     --secondary-foreground
--muted         --muted-foreground
--border        --input  --ring
--radius
```

**Nunca** usar colores hardcodeados como `#fff` o `rgb(0,0,0)` en los componentes. Usar siempre las variables.

### 3.5 Capa de Servicios

Todas las llamadas a la API pasan por archivos en `src/services/`. El componente **nunca** llama a `fetch` directamente.

```js
// services/orders.service.js
import { apiClient } from './api'

export async function getOrder(id) {
  return apiClient.get(`/orders/${id}`)
}

export async function updateOrderStatus(id, status) {
  return apiClient.patch(`/supermarkets/orders/${id}/status`, { status })
}
```

```jsx
// En el componente:
import { getOrder } from '../services/orders.service'

useEffect(() => {
  getOrder(orderId).then(setOrder).catch(handleError)
}, [orderId])
```

### 3.6 Manejo de Estado

- **Estado local** (useState): datos que solo usa ese componente.
- **Context** (AuthContext): solo para datos de sesion del usuario autenticado.
- **No** usar Redux, Zustand ni ninguna libreria de estado global adicional sin aprobacion explicita.

### 3.7 Routing

- Las rutas publicas (landing, auth) usan hash-routing simple del `App.jsx`.
- Las rutas protegidas usan `react-router-dom` v6 con un componente `ProtectedRoute` que verifica el token.
- Las rutas del admin (`supermarket_admin`) son completamente independientes.

---

## 4. Backend — Convenciones FastAPI

### 4.1 Nombrado

| Elemento | Convencion | Ejemplo |
|---|---|---|
| Archivos | snake_case | `order_service.py` |
| Clases Python | PascalCase | `OrderCreate`, `OrderResponse` |
| Funciones/variables | snake_case | `get_order_by_id` |
| Endpoints | snake_case en ruta | `/orders/{order_id}` |
| Constantes | UPPER_SNAKE_CASE | `ORDER_STATUSES` |

### 4.2 Estructura de un Endpoint

```python
# api/v1/endpoints/orders.py

from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.order import OrderCreate, OrderResponse
from app.services.order_service import create_order
from app.core.security import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def place_order(
    order_data: OrderCreate,
    current_user=Depends(get_current_user),
):
    """
    Crea un nuevo pedido a partir de una lista de compras del usuario.
    Requiere autenticacion de consumidor.
    """
    return await create_order(order_data, user_id=current_user.id)
```

Reglas:
- Todo endpoint tiene **docstring** con descripcion y requisitos.
- La logica de negocio va en `services/`, no en el endpoint.
- Los endpoints solo validan, llaman al servicio y devuelven la respuesta.
- Usar `status_code` explicito siempre.

### 4.3 Schemas Pydantic

- Un schema por operacion: `OrderCreate`, `OrderUpdate`, `OrderResponse`.
- `OrderResponse` es siempre el modelo de salida; nunca exponer campos internos (ej: password, service_role_key).
- Los precios siempre como `int` (centavos), nunca `float`.

```python
# schemas/order.py
from pydantic import BaseModel, UUID4
from datetime import datetime

class OrderCreate(BaseModel):
    list_id: UUID4
    supermarket_id: UUID4
    pickup_scheduled: datetime
    notes: str | None = None

class OrderResponse(BaseModel):
    id: UUID4
    status: str
    pickup_scheduled: datetime
    total_price: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

### 4.4 Manejo de Errores

- Usar `HTTPException` con codigos HTTP correctos.
- Nunca devolver `500` cuando el error es del cliente.
- Los errores de validacion los maneja Pydantic automaticamente (422).

```python
# CORRECTO
if not order:
    raise HTTPException(status_code=404, detail="Pedido no encontrado")

if order.user_id != current_user.id:
    raise HTTPException(status_code=403, detail="Sin permiso para ver este pedido")

# INCORRECTO
return {"error": "not found"}   # nunca
return None                      # nunca para recursos no encontrados
```

### 4.5 Cliente Supabase

- Un unico cliente Supabase por entorno, inicializado en `core/supabase_client.py`.
- Usar `service_role_key` solo en el backend; jamas exponerlo al frontend.
- Los accesos a la base de datos van en los `services/`, no en los endpoints.

```python
# core/supabase_client.py
from supabase import create_client, Client
from app.core.config import settings

_client: Client | None = None

def get_supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _client
```

### 4.6 Configuracion

Toda configuracion viene de variables de entorno via `core/config.py` con Pydantic BaseSettings. **Nunca** hardcodear URLs, keys o secrets en el codigo.

```python
# core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    JWT_SECRET: str
    ALLOWED_ORIGINS: list[str] = []

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 5. Base de Datos

### 5.1 Convenciones de Tablas

- Nombres en **snake_case plural**: `shopping_lists`, `order_items`.
- Toda tabla tiene `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- Toda tabla principal tiene `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`.
- Las tablas cuyas filas se modifican tienen `updated_at`, mantenido por el
  **trigger `set_updated_at`**, no a mano en cada UPDATE. Un `updated_at` que
  depende de que alguien se acuerde de tocarlo miente tarde o temprano.
- Los precios siempre en **centavos como INTEGER**. Nunca FLOAT o NUMERIC para dinero.
- Las columnas de texto libre que sean criticas deben tener `NOT NULL`.
- **Los conjuntos cerrados de valores van como `ENUM`**, no como TEXT libre. Si
  un valor solo puede ser uno de N, la base lo tiene que saber.
- **Todo dato con rango valido lleva `CHECK`**: precios y cantidades `> 0`,
  fechas coherentes, formatos verificados. La validacion de Pydantic no protege
  contra un INSERT que no venga de la API.
- **Toda foreign key lleva su indice.** Postgres crea indices en las PK, no en
  las FK, y esas son justamente las columnas por las que se filtra.
- **Toda foreign key declara su `ON DELETE`** de forma explicita. Dejar el
  default (`NO ACTION`) es no haber elegido: la migracion 019 existe porque un
  `ON DELETE CASCADE` prometia una cascada que se frenaba tres tablas mas
  abajo.

### 5.2 Migraciones

- Los cambios de schema se documentan como archivos SQL numerados en `backend/migrations/`.
- Formato: `001_create_profiles.sql`, `002_add_pickup_column.sql`.
- Nunca modificar una migracion ya aplicada; siempre crear una nueva.

### 5.3 Row Level Security (RLS)

- RLS debe estar habilitado en **todas** las tablas.
- Un usuario consumidor solo puede leer/modificar sus propios datos.
- Un staff de supermercado solo puede leer datos de su cadena.
- **El backend (service_role) bypasea RLS siempre, no "cuando lo necesita".**
  Por eso RLS es defensa en profundidad y no la barrera principal: toda consulta
  del backend a datos de un tenant lleva su filtro de ownership escrito a mano.
  Ver SEGURIDAD.md §5.1 — es la regla que mas facil se olvida y la que mas caro
  sale.
- Una tabla con RLS y **cero policies** para `authenticated` es una decision
  valida y frecuente: significa "solo el backend toca esto".
- Toda funcion `SECURITY DEFINER` revoca `EXECUTE` de `PUBLIC`, `anon` **y**
  `authenticated`. Los tres. Ver SEGURIDAD.md §5.3.

---

## 6. API — Convenciones REST

- Siempre versionado: `/api/v1/...`
- Recursos en plural: `/orders`, `/lists`, `/products`.
- Acciones especiales como sub-recursos: `/orders/{id}/status`, `/lists/{id}/compare`.
- Codigos HTTP correctos:
  - `200` OK (GET exitoso)
  - `201` Created (POST exitoso)
  - `204` No Content (DELETE exitoso)
  - `400` Bad Request (datos invalidos del cliente)
  - `401` Unauthorized (sin autenticacion)
  - `403` Forbidden (autenticado pero sin permiso)
  - `404` Not Found
  - `422` Unprocessable Entity (falla de validacion Pydantic)
- Las respuestas de lista siempre incluyen paginacion: `{ data: [...], total: N, page: N, per_page: N }`.

---

## 7. Git y Control de Versiones

### 7.1 Ramas

```
main          → produccion, siempre estable
develop       → integracion, rama base para features
feature/xxx   → nueva funcionalidad
fix/xxx       → correccion de bug
chore/xxx     → cambios de configuracion, dependencias
```

### 7.2 Commits

Formato: `tipo(scope): descripcion breve en imperativo`

```
feat(orders): agregar endpoint de comparacion de precios
fix(auth): corregir validacion de JWT expirado
chore(deps): actualizar fastapi a 0.115
docs(readme): agregar instrucciones de setup local
style(landing): ajustar espaciado en seccion hero
```

Tipos validos: `feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `test`

---

## 8. Accesibilidad

- Todo elemento interactivo (`button`, `a`, inputs) tiene `aria-label` si su texto visible no es suficiente.
- Todas las imagenes tienen `alt` descriptivo.
- El contraste minimo de texto es WCAG AA (4.5:1).
- Los formularios tienen `label` asociado a cada input via `htmlFor` / `id`.
- El orden de tabulacion debe ser logico y seguir el flujo visual.

---

## 9. Lo Que Esta Prohibido

- **No** usar `any` en TypeScript (si se migra a TS en el futuro).
- **No** hacer llamadas a la DB desde los endpoints (solo desde `services/`).
- **No** exponer la `SERVICE_ROLE_KEY` de Supabase en el frontend.
- **No** usar `!important` en CSS excepto en casos extremos documentados.
- **No** silenciar errores con `try/catch` vacio.
- **No** hardcodear strings magicos; usar constantes nombradas.
- **No** eliminar tests existentes para hacer pasar un test nuevo.
- **No** crear archivos fuera de la estructura definida en ARQUITECTURA.md sin justificacion documentada.
- **No** instalar dependencias nuevas sin evaluar si ya existe algo equivalente en el proyecto.
- **No** confiar en RLS para proteger una consulta del backend: `service_role` la ignora.
- **No** tomar la identidad de un tenant (usuario o cadena) de un header, un
  query param o el body. Sale del JWT y se resuelve contra la base.
- **No** dejar una variable de entorno obligatoria que ningun codigo lee.

---

## 10. Checklist antes de hacer un PR / commit importante

- [ ] El codigo pasa sin errores en el servidor de desarrollo local.
- [ ] Los nuevos endpoints tienen su schema Pydantic de request y response.
- [ ] Los precios y cantidades monetarias son `int` (centavos), no `float`.
- [ ] No hay credenciales ni secrets en el codigo.
- [ ] Los nuevos componentes tienen su `.module.css` separado.
- [ ] Los estilos usan variables CSS del design token, no valores hardcodeados.
- [ ] Los elementos interactivos nuevos tienen `aria-label` si es necesario.
- [ ] El codigo nuevo sigue las convenciones de nombrado de la seccion 3 y 4.
- [ ] Las tablas nuevas tienen RLS, indices en sus FK y `ON DELETE` explicito.
- [ ] Las funciones `SECURITY DEFINER` nuevas revocan `EXECUTE` de `PUBLIC`, `anon` y `authenticated`.
- [ ] Se recorrio el checklist de `SEGURIDAD.md` §17 si el cambio toca backend,
      base de datos o autenticacion.
