# Sistema de Ventas y Stock

Sistema para varias sucursales con dos tipos de usuario:

- **Servidor** (backoffice): carga productos, compras, sucursales, usuarios y define el régimen fiscal.
- **Punto de venta (POS)**: vende, descuenta stock automáticamente y emite un comprobante interno.

El costo de cada producto se calcula con **costo promedio ponderado** a medida que entran compras, y la
ganancia de cada venta se calcula automáticamente según el **régimen fiscal** configurado (Monotributo o
Responsable Inscripto) — ver `backend/app/calculos.py` para la lógica exacta.

## Estructura

```
backend/     API en FastAPI + SQLAlchemy
frontend/    Login, POS y backoffice (HTML/CSS/JS sin build, listo para deployar como sitio estático)
render.yaml  Definición de despliegue en Render
```

## 1. Correr en local

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # en Windows (Git Bash): source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env           # completar SECRET_KEY y ADMIN_PASSWORD
alembic upgrade head           # crea/actualiza las tablas (nunca hay que borrar la base para esto)
uvicorn app.main:app --reload
```

> `psycopg2-binary` (necesario solo para PostgreSQL) quedó en `requirements-postgres.txt` aparte,
> porque en Windows suele fallar si no tenés `pg_config` instalado, y en local no hace falta —
> con SQLite alcanza para probar. Si vas a conectar a Postgres en local, usá:
> `pip install -r requirements-postgres.txt`.

La API queda en `http://127.0.0.1:8000` (documentación interactiva en `/docs`).
Al arrancar por primera vez se crea solo el usuario **servidor** inicial con el
`ADMIN_USERNAME` / `ADMIN_PASSWORD` que hayas puesto en `.env`.

Sin configurar `DATABASE_URL`, usa un archivo SQLite local (`ventas_stock.db`) — perfecto para probar.

### Frontend

Es HTML/JS plano, no necesita build. Basta con abrirlo con un servidor estático simple:

```bash
cd frontend
python -m http.server 5500
```

Abrí `http://127.0.0.1:5500/login.html`. Por defecto apunta a `http://127.0.0.1:8000` (ver `js/api.js`).

## 2. Primeros pasos dentro del sistema

1. Entrá como `admin` (usuario servidor).
2. En **Régimen fiscal**, elegí Monotributo o Responsable Inscripto — esto define cómo se calculan costo,
   IVA y ganancia en todo el sistema, y lo podés cambiar cuando lo necesites.
3. Creá al menos una **sucursal**.
4. Cargá tus **productos** (precio de venta, IVA, stock mínimo).
5. Registrá una **compra** para esa sucursal — esto suma stock y calcula el costo promedio.
6. Creá un **usuario punto de venta** asociado a esa sucursal.
7. Cerrá sesión y entrá con ese usuario para probar el **POS**: buscar producto, armar el ticket, cobrar.

## 3. Subir a GitHub y desplegar (mismo flujo que `gastos-api`)

```bash
git init
git add .
git commit -m "Sistema de ventas y stock"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/sistema-ventas-stock.git
git push -u origin main
```

### Backend en Render

1. En Render: **New > Blueprint**, apuntá al repo — va a leer `render.yaml` solo.
2. Creá la base de datos Postgres que pide el blueprint (o usá una que ya tengas) y completá
   `DATABASE_URL` con la **Internal Database URL** que te da Render.
3. Completá `ADMIN_PASSWORD` en las variables de entorno del servicio.
4. Deploy. Vas a tener tu API en algo como `https://ventas-stock-api.onrender.com`.

### Frontend

Es estático, así que podés desplegarlo como **Static Site** en Render (root: `frontend`) o en GitHub Pages.
Antes de deployar, en `frontend/js/api.js` cambiá:

```js
const API_BASE = window.API_BASE_URL || 'http://127.0.0.1:8000';
```

por la URL real de tu backend en Render (o seteá `window.API_BASE_URL` en un `<script>` antes de cargar `api.js`).

## 4. Migraciones de base de datos (Alembic) — ya no hace falta borrar la base

Antes, cada cambio en las tablas requería borrar `ventas_stock.db` y perder los datos
cargados. Eso ya no es así: el esquema lo maneja **Alembic**, que aplica los cambios
tabla por tabla sin tocar los datos existentes.

**De ahora en más, cuando te pase una actualización con cambios en la base de datos:**

```bash
cd backend
git pull   # o reemplazar los archivos como siempre
alembic upgrade head
uvicorn app.main:app --reload
```

Eso es todo — nunca más `rm ventas_stock.db`. Las migraciones viven en `backend/alembic/versions/`
y cada una sabe exactamente qué cambió (una tabla nueva, una columna nueva, etc.), así que solo
aplica esa diferencia puntual.

Si alguna vez querés ver el historial de cambios de la base: `alembic history`. Y si necesitás
revertir el último cambio: `alembic downgrade -1`.

## 5. Funcionalidad agregada en esta tanda

- **Formas de pago con banco/proveedor**: Backoffice → Formas de pago te deja cargar bancos y
  proveedores por tipo (ej. bajo Débito: "Banco Galicia"; bajo QR: "Mercado Pago", "MODO"). En
  el POS, al elegir Débito/Crédito/Transferencia/QR aparece un popup para elegir cuál — el dato
  queda guardado en cada venta y se ve en Informes. "Mercado Pago" como método pasó a llamarse
  **QR** (categoría más general que incluye Mercado Pago, MODO, etc. como proveedores).
- **Inventario**: conteo físico de stock por sucursal, comparado automáticamente contra el
  stock del sistema — corrige el stock y deja el desvío (merma o sobrante) registrado. Nuevo
  reporte de kardex con columnas Ingresos / Compras / Salidas / Ventas / Stock por producto.
- **Gráficos en el Resumen** (Chart.js, incluido localmente en `frontend/js/vendor/` — no
  depende de internet): ventas por día de la semana, formas de pago más usadas, y ventas por mes.

- **Migraciones con Alembic** (ver sección 4) — el cambio más importante de esta tanda para el
  día a día, aunque no se vea en la interfaz.
- **Teléfono de sucursal** y **notas de categoría**, agregados de paso al armar las migraciones.

- **Modo offline del POS**: si se pierde la conexión, el POS sigue permitiendo vender —
  usa el catálogo cacheado en el navegador (IndexedDB) y guarda la venta en una cola local.
  Al recuperar la conexión, sincroniza automáticamente esas ventas con el servidor (reintenta
  cada 20 segundos y también al detectar que volvió la señal). Un indicador en el header
  muestra "En línea" / "Sin conexión" y cuántas ventas quedan pendientes de sincronizar.
  Limitaciones a tener en cuenta: **abrir y cerrar turno, ver/anular ventas y registrar
  movimientos de caja requieren conexión** (son operaciones que necesitan coordinarse con el
  servidor); solo la venta en sí funciona offline. El stock que se muestra offline es una
  foto de la última vez que hubo conexión, ajustada localmente por lo que ese mismo
  dispositivo fue vendiendo — si hay más de un POS vendiendo el mismo producto sin conexión
  al mismo tiempo, el servidor vuelve a validar el stock real al sincronizar y puede rechazar
  alguna venta si ya no había stock (quedaría marcada para revisión manual).

- **Razón social**: se edita en Backoffice → Negocio, y reemplaza el texto genérico "Backoffice"/"Punto de Venta" en ambas interfaces.
- **Categorías de productos**: sección propia (Backoffice → Categorías); se asignan al crear/editar un producto y sirven para filtrar en el POS.
- **Compras con proveedor y bultos por artículo**: cada línea de una compra puede tener su propio proveedor (si difiere del proveedor principal de la compra) y la cantidad de bultos recibidos.
- **Turnos numerados**: cada turno tiene un número correlativo por sucursal ("Turno N°1", "N°2"...).
- **Cancelar cierre de turno**: el modal de arqueo tiene una "✕" para cerrar sin confirmar el cierre.
- **Movimientos de caja**: ingresos y egresos de efectivo que no son ventas (ej. pago a un flete), registrados durante el turno y que se descuentan/suman al efectivo esperado del arqueo.
- **Anular ventas**: el usuario POS puede ver las ventas de su turno actual y anular alguna (repone el stock automáticamente). El servidor puede anular cualquier venta desde el backoffice vía API.
- **Propina**: se carga aparte del total de productos, no afecta el cálculo de IVA/ganancia.
- **Pago dividido**: una venta puede cobrarse combinando varias formas de pago (ej. mitad efectivo, mitad débito) — el sistema no deja confirmar hasta que la suma de los pagos cubra el total exacto.
- **Imagen de producto por archivo**: además de pegar una URL, se puede subir un archivo desde el backoffice (se guarda en `backend/static/uploads/`).
- **Informes**: pestaña con el detalle línea por línea de las ventas de un período (incluyendo anuladas), y el Resumen ahora desglosa por día de la semana y productos más vendidos.

**Nota sobre "multi-negocio"**: este sistema está pensado para una sola razón social con varias sucursales. Para usarlo con negocios distintos y completamente aislados entre sí (otro catálogo, otros usuarios, sin verse los datos unos a otros), lo más simple hoy es desplegar una instancia separada (otro backend + otra base) por negocio — el código ya lo permite sin cambios. Una arquitectura multi-tenant real (un solo backend atendiendo varios negocios aislados) es un proyecto aparte, no incluido acá.

## 6. Notas de diseño

- **Costo promedio ponderado (CPP)**: cada compra nueva recalcula el costo del producto ponderando por
  cantidad, así una compra puntual más cara o más barata no distorsiona la ganancia histórica.
- **Cambiar de régimen fiscal** afecta automáticamente el cálculo de costo de las próximas compras y la
  ganancia de las próximas ventas — no reescribe operaciones ya registradas (quedan con la lógica vigente
  al momento en que se cargaron, como corresponde contablemente).
- **Roles**: el usuario POS solo puede vender y ver stock/precios; todo lo demás (productos, compras,
  usuarios, configuración fiscal, reportes) requiere el rol servidor.
- El comprobante que emite el POS es un **número interno** (`SUCxxx-000001`), no es factura electrónica AFIP.
- **Turnos de caja**: el usuario POS necesita abrir un turno (declarando el efectivo inicial) antes de poder
  vender. Al cerrar, se hace un arqueo billete por billete y el sistema calcula la diferencia contra lo
  esperado (apertura + ventas en efectivo del turno) — las ventas con débito/crédito/transferencia no
  afectan ese cálculo, solo el efectivo. Las denominaciones de billetes están en `frontend/js/pos.js`
  (constante `DENOMINACIONES`) — si cambian los billetes en circulación, se edita ahí.
- **Forma de pago**: cada venta guarda el método (efectivo, débito, crédito, transferencia, Mercado Pago),
  visible en `/reportes/resumen-ventas` desglosado por método.
- **Imagen de producto**: el campo `imagen_url` es una URL externa (no hay upload de archivos todavía).
  Para escalar esto más adelante, lo natural es sumar un servicio de storage (S3, Cloudinary, o el storage
  de Render) y que el backoffice suba el archivo y guarde la URL resultante — la estructura ya está lista
  para eso, solo cambiaría de dónde sale la URL.
