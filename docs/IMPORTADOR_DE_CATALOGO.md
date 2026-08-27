# FreshMart — Importador de catálogo

> Cómo entra al comparador la planilla que exporta el ERP de un supermercado, y
> cómo se le enseña a leer un ERP nuevo.

---

## 1. El problema

Un supermercado chico tiene 3.000 productos; uno mediano, 15.000. Cargarlos de
a uno por el formulario del panel no es una opción, y ningún supermercado va a
reformatear su export para que se parezca al nuestro. El archivo llega como
sale del ERP:

```
LISTADO DE PRECIOS AL 27/08/2026
Sucursal: Centro

COD.BARRA        DESCRIPCION              MARCA        PRECIO COSTO  PRECIO VENTA  STOCK
7790001000017    LECHE ENTERA 1L          La Serenísima      980,00      1.234,56     12
```

Ahí adentro está todo lo que hay que resolver: el encabezado no está en la
primera fila, las columnas se llaman distinto que las nuestras, hay una columna
de costo que **no** es el precio de venta, los números están en formato
español, y el código de barras puede venir como `7.79E+12` si el ERP lo guardó
como número.

---

## 2. Las tres piezas

| Archivo | Responsabilidad |
|---|---|
| `services/spreadsheet_reader.py` | El archivo (xlsx / xls / csv) → una grilla de celdas. No interpreta nada. |
| `services/import_mapping.py` | Qué campo es cada columna, y qué dice cada celda. |
| `services/product_import_service.py` | Qué hacer con cada fila, y hacerlo. |

Están separados porque fallan por motivos distintos, y con un solo archivo el
error de un csv en latin-1 y el de una columna mal mapeada se mezclan en el
mismo stack.

---

## 3. El flujo, de punta a punta

```
  El encargado sube el archivo
            │
            ▼
  POST /supermarkets/me/products/import/preview      ← NO escribe
            │
            │   detecta hoja, fila de encabezado y columnas
            │   dice: "1.842 se actualizan, 96 se dan de alta, 12 no entran"
            ▼
  El encargado revisa y, si hace falta, corrige el mapeo a mano
            │
            ▼
  POST /supermarkets/me/products/import              ← escribe
            │
            ├─ crea en `products` lo que no existía (por EAN)
            ├─ upsert en `supermarket_products` (precio, stock, disponibilidad)
            ├─ opcional: despublica lo que el archivo no menciona
            └─ registra la corrida en `product_import_jobs`
```

**Nunca se escribe sin que la vista previa haya podido verse.** Son dos rutas y
no un flag `dry_run` porque la garantía tiene que ser estructural: el endpoint
que muestra no tiene código que escriba.

---

## 4. Detección de columnas

### 4.1 Normalización

`«  Precio de Venta ($) »` → `precio de venta`. Se sacan acentos, mayúsculas y
puntuación: ahí está la mayor parte de la variación entre un ERP y otro.

### 4.2 Puntaje

Cada par (columna, campo) recibe un puntaje:

| Coincidencia | Puntaje |
|---|---|
| El encabezado ES un sinónimo | 1000 |
| El encabezado empieza o termina con un sinónimo | 500 + largo del sinónimo |
| El sinónimo aparece como palabra suelta adentro | 200 + largo del sinónimo |
| Contiene una palabra descalificante | 0 |

Después se asigna de forma golosa, de mayor a menor puntaje, con una columna
por campo y un campo por columna. El largo del sinónimo desempata a favor del
más específico: `precio de venta` describe mejor a `PRECIO DE VENTA UNITARIO`
que el genérico `precio`.

### 4.3 Las palabras descalificantes

Son la mitad importante del algoritmo. `PRECIO COSTO` matchea "precio" tan bien
como `PRECIO VENTA`, y publicar el costo como precio de venta **le regala el
margen del supermercado a sus competidores**, que lo ven en el comparador. Por
eso `costo`, `compra`, `proveedor`, `anterior`, `neto`, `sin iva` y `mayorista`
dejan a una columna fuera de la carrera por `price`, aunque sea la única
candidata: si no hay una columna de precio de venta clara, el importador no
mapea ninguna y la pide a mano.

### 4.4 La fila de encabezado

Se prueban las primeras 15 filas y gana la que reconoce más campos. Para
calificar tiene que tener con qué identificar al producto (EAN **o** nombre) y
algo que actualizar (precio **o** stock). Una fila con solo `CATEGORIA`
reconocido no es la tabla, es el título del reporte.

---

## 5. Lectura de celdas

### 5.1 Números: el problema de los separadores

`1.234` es mil doscientos treinta y cuatro en un export en español y uno con
veinticuatro centésimos en uno en inglés, y el archivo no dice cuál es. Las
reglas, en orden:

1. **Están los dos separadores** → el último es el decimal. `1.234,56` es
   español, `1,234.56` es inglés. Esto no falla nunca.
2. **Un solo separador con exactamente 3 dígitos detrás** → es de miles. Ni los
   precios ni los stocks reales se escriben con tres decimales.
3. **Un solo separador con otra cantidad** → es decimal. `19.99`, `1234,5`.

### 5.2 El código de barras

Es la clave de identidad de todo el sistema (ver §6), así que es donde más se
insiste:

| Lo que llega | Qué se hace |
|---|---|
| `7790001000017` (texto o número) | Se usa tal cual |
| `7790001000017.0` | Se corta en el punto. Los ceros **no** se recortan: en un EAN son dígitos |
| `779-0001-000017` | Se sacan guiones y espacios |
| `7.79E+12` | **Se rechaza** con instrucciones |
| `12345` (5 dígitos) | Se rechaza: el CHECK de la base pide 8 a 14 |

El caso de la notación científica merece la excepción. Convertirlo a entero da
`7790000000000`, que es un EAN perfectamente formado **de otro producto**: el
export guardó lo que la celda *mostraba*, y los dígitos que faltan no están en
ninguna parte. El mensaje dice qué hacer: exportar esa columna con formato de
texto.

Los ceros a la izquierda que Excel se comió tampoco se reponen. Un EAN-13 sin
su cero inicial son 12 dígitos, que la base acepta; rellenarlo a ciegas
inventaría un código que apunta a otro lado.

---

## 6. Identidad del producto

`products` es una tabla **compartida entre competidores**: el comparador
funciona porque el precio de Carrefour y el de Vital cuelgan de la misma fila.
Un importador que cree una fila nueva por cada línea del archivo vacía el
comparador en una sola corrida. La decisión, por fila:

```
¿tiene EAN?
├── sí → ¿existe products.ean = X?
│         ├── sí → se vincula. El nombre y la marca del archivo se DESCARTAN:
│         │        una cadena no reescribe la fila de la que cuelgan los
│         │        precios de sus competidores (SEGURIDAD.md §4.2).
│         └── no → se crea, con created_by_chain_id
└── no  → ¿el nombre completo matchea uno que esta sucursal ya vende?
          ├── uno solo  → se vincula
          ├── varios    → SE SALTEA, con el motivo
          └── ninguno   → ¿matchea un único producto del catálogo global?
                          ├── sí → se vincula
                          ├── varios → SE SALTEA, con el motivo
                          └── no → se crea
```

El matcheo por nombre no distingue mayúsculas ni acentos —los ERP exportan en
MAYÚSCULAS y una comparación exacta duplicaría todo el catálogo— pero sí exige
el nombre completo: no hay coincidencias parciales.

Saltear con motivo es un resultado legítimo y buscado. Vincular mal publica el
precio sobre el producto equivocado, que es peor que no importar la fila.

---

## 7. Precio, stock y disponibilidad

Qué se escribe en cada fila de `supermarket_products`:

| El archivo trae | Qué pasa |
|---|---|
| Precio y stock | Se actualizan los dos |
| Solo precio | El stock y la disponibilidad quedan como estaban |
| Solo stock | El precio queda como estaba |
| Stock en 0 | `in_stock` pasa a `false` (lo fuerza el trigger de la 024) |
| Stock positivo sobre una fila que estaba en 0 | Se vuelve a publicar |
| Nada de eso, y el producto no estaba cargado | Es un error de esa fila: `price` es NOT NULL y no hay precio que inventar |

La quinta fila es la que hay que entender: un producto que llegó a 0 quedó
despublicado por el trigger, y ese 0 solo pudo haberlo puesto una venta o un
import — con cantidad 0 no hay forma de que `in_stock` quede en `true`. Si
reponer stock no lo republicara, cada agotado necesitaría que alguien se
acuerde de reactivarlo a mano y la góndola se vaciaría sola. Lo que **no** pasa
es lo simétrico: si alguien despublicó a mano un producto que sí tiene
unidades, el import no lo vuelve a publicar.

### 7.1 `deactivate_missing`

Marca sin stock todo lo que la sucursal tiene cargado y el archivo no menciona.
Es lo correcto cuando el archivo es el catálogo completo y es un desastre
cuando es un export filtrado por categoría: despublica el resto de la góndola.
Por eso viene apagado, hay que pedirlo explícitamente, y la vista previa dice
**a cuántos productos afectaría** antes de confirmar.

---

## 8. Enseñarle un ERP nuevo

Es una línea. En `import_mapping.py`, dentro de `FIELD_SYNONYMS`, se agrega la
frase **normalizada** (sin acentos, en minúscula, sin puntuación) al campo que
corresponda:

```python
FIELD_SYNONYMS = {
    FIELD_PRICE: (
        "precio", "precio de venta", ...,
        "importe neto final",   # ← el ERP de la cadena X
    ),
    ...
}
```

Si el encabezado nuevo puede confundirse con otro campo, va también un hint
negativo en `FIELD_NEGATIVE_HINTS`. Y siempre un caso en
`tests/test_product_import.py::test_different_erps_map_to_the_same_fields`: los
sinónimos son datos, y los datos sin test se rompen callados.

Mientras tanto, el supermercado **no queda bloqueado**: la vista previa deja
corregir el mapeo a mano desde el panel para esa corrida.

---

## 9. Límites

| Qué | Cuánto | Por qué |
|---|---|---|
| Tamaño del archivo | 5 MB | Un catálogo de 20.000 productos en xlsx pesa ~1 MB |
| Filas por corrida | 20.000 | Se corta la lectura y se informa; no se rechaza el archivo |
| Columnas | 60 | Excel reporta miles si hay formato aplicado |
| Problemas reportados | 100 | Un archivo mal mapeado da un error por fila |
| Filas de muestra en la vista previa | 15, **los problemas primero** | Mostrar las 15 primeras esconde los 40 errores de más abajo |

---

## 10. Lo que el importador no hace

- **No es transaccional de punta a punta.** Son miles de filas contra PostgREST,
  no una función de Postgres. Las escrituras están ordenadas para que una caída
  a mitad de camino deje datos coherentes: primero los productos globales
  (idempotentes por EAN), después los precios (idempotentes por el `UNIQUE` de
  la sucursal). **Reintentar el mismo archivo converge al mismo estado.**
- **No corre en segundo plano.** Un archivo de 20.000 filas son ~40 lotes de
  escritura y el request se sostiene. Si aparece un supermercado con un catálogo
  que no entra en ese presupuesto, la respuesta es una cola de trabajos y no un
  timeout más largo.
- **No importa a varias sucursales a la vez.** Un precio es siempre el precio de
  una sucursal; una columna de "sucursal" dentro del archivo tendría que
  resolver a qué fila de `supermarkets` corresponde cada nombre, y eso se
  adivina mal.
- **No edita el catálogo global.** Ver §6.
