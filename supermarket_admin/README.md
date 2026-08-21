# FreshMart — Panel de supermercados

Portal para que los supermercados se registren en FreshMart y gestionen su
cadena. Es un proyecto independiente de `supermarket_front` (la app del
consumidor): no comparten código, por `docs/NORMAS.md` §2.

## Puesta en marcha

```bash
cp .env.local.example .env.local   # completar con los datos del proyecto Supabase
npm install
npm run dev                        # http://localhost:5174
```

El backend tiene que estar corriendo en `http://localhost:8000` y tener
`http://localhost:5174` en su `ALLOWED_ORIGINS`.

## Rutas

| Ruta | Acceso | Qué es |
|---|---|---|
| `/` | Pública | Landing: por qué sumar tu supermercado |
| `/register` | Pública | Wizard de alta en 4 pasos |
| `/auth` | Pública | Login del staff |
| `/pending` | Con sesión | Estado de la solicitud (en revisión, rechazada, suspendida) |
| `/app/profile` | Cadena aprobada | Datos de la cadena |
| `/app/stores` | Cadena aprobada | Sucursales y horarios |
| `/app/team` | Cadena aprobada, rol owner | Equipo |

## Cómo se accede al panel

El alta no es inmediata. El recorrido completo es:

1. **Registro** — el wizard manda un único `POST /supermarkets/register` al
   final. Los pasos anteriores son estado local, así que abandonar el wizard no
   deja nada a medio crear.
2. **Confirmación de correo** — se crea con `email_confirm: false`. Hasta
   confirmarlo no se puede iniciar sesión.
3. **Revisión** — la cadena queda en `pending_review` y no aparece en el
   comparador del consumidor. Un operador de FreshMart la aprueba o la rechaza.
4. **Panel** — solo con la cadena en `approved` se entra a `/app/*`. Lo
   controlan `ApprovedRoute` en el front y `require_approved_chain` en el
   backend; la del backend es la que manda.

## Aprobar una cadena en desarrollo

Todavía no hay UI de moderación (siguiente sprint). Hace falta un usuario en
`platform_admins`, que se puebla **solo por SQL** — a propósito: no existe, ni
debe existir, un endpoint para darse de alta como administrador.

```sql
INSERT INTO platform_admins (id, full_name)
VALUES ('<uuid del usuario en auth.users>', 'Tu nombre');
```

Después, con el JWT de ese usuario:

```bash
curl -X POST "http://localhost:8000/api/v1/admin/chains/<chain_id>/review" \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"status":"approved"}'
```

Rechazar exige motivo: `{"status":"rejected","note":"..."}`. El supermercado lo
ve en `/pending`.

## Scripts

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo en el puerto 5174 |
| `npm run build` | Build de producción a `dist/` |
| `npm run lint` | oxlint |
| `npm run preview` | Sirve el build |
