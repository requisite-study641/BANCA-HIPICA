# Prueba de edición
## Fase 8: Corrección del botón `#upload-race-btn` y validación end-to-end (2026-10-06)

**Problema:**
El botón de carga de cartelera (`#upload-race-btn`, "⬆ Procesar archivo") no respondía al hacer clic, y en la consola aparecía el error `Admin.uploadRaces is not a function`.

**Causa:**
El manejo del evento estaba definido dentro del IIFE del módulo (con `q(...).addEventListener(...)`), pero el módulo no se exponía globalmente — la referencia `Admin` no era accesible desde el contexto de la página ni el handler estaba registrado de forma explícita en el elemento del botón.

**Solución (`frontend/js/admin.js`):**
- Cambió el event listener interno de `q("#upload-race-btn").addEventListener("click", uploadRaces)` a un manejo **explícito** sobre el elemento real:
  ```javascript
  const uploadBtn = document.getElementById("upload-race-btn");
  if (uploadBtn) uploadBtn.onclick = () => uploadRaces();
  ```
- Se expuso el módulo globalmente mediante `window.Admin = publicApi;` al final del IIFE, quedando disponible `Admin.bind()`, `Admin.loadRaces()`, `Admin.uploadRaces()`, etc.

**Resultados:**
- ✅ Regreso del botón `#upload-race-btn` funcional: clic → llama directamente a `uploadRaces()` → carga del archivo por `FormData` al endpoint `/admin/races/upload`.
- ✅ Confirmación y validación exitosa de la carga end-to-end de carteleras oficiales:
  - Reporte INH real (Excel .xlsx) — 114 ejemplares importados correctamente, 0 errores.
  - CSV multilínea (reportes INH con campos citados y filas de etiquetas/valores separadas) — parseado sin errores.
  - Plantillas de prueba: 8 filas en `frontend/ejemplares_inh_ejemplo.csv`, 8 en `frontend/cartelera_ejemplo.csv`, 24 en `formato definitivo.xlsx`.

**Archivos modificados:**
- `frontend/js/admin.js`: registro directo `uploadBtn.onclick` en `bind()`; exposición `window.Admin = publicApi` al cierre del módulo
- `CONTEXT.md`: bitácora Fase 8 (este documento)

---

## Fase 7: Parseo INH consciente de columnas (2026-10-06)

**Problema:** 
El nuevo reporte INH real ("Ejemplares inscritos reunión 39.xlsx") tenía metadatos organizados en una cuadrícula por columna (etiqueta y valor en la misma columna, filas diferentes). El parser original basado en líneas (`parse_inh_report`) no podía detectar etiquetas/valores cuando estaban en columnas diferentes de la misma fila, causando 0 filas extraídas.

**Solución:**
Rediseñé `parse_inh_report` para ser **consciente de columnas**:
- Procesar cada celda individualmente (no concatenar la fila entera).
- Mantener estado `pending_label` **por índice de columna** (`Dict[int, str]`).
- Soportar tanto:
  - Etiqueta y valor en la **misma celda** (`"Carrera Nro:\n2"` → `"Carrera Nro: 2"`).
  - Etiqueta en una fila y valor en la fila **siguiente, misma columna** (exportación de celdas combinadas de Excel).
- Mejorar validación de filas de tabla: solo considerar filas donde la columna N°/dorsal contenga un número puro (`^\d{1,3}\.?$`), evitando confundir pies de página/observaciones con ejemplares.
- Mantener compatibilidad hacia atrás con reportes INH simples y casos de CSV plano mal detectado.

**Resultados:**
- ✅ Nuevo reporte INH real: 114 filas, 0 errores
- ✅ Regresión completa:
  - `frontend/ejemplares_inh_ejemplo.csv`: 8 filas, 0 errores
  - `frontend/cartelera_ejemplo.csv`: 8 filas, 0 errores  
  - `formato definitivo.xlsx`: 24 filas, 0 errores
- ✅ Ningún error introducido en funcionalidad existente

**Archivos modificados:**
- `backend/parsers.py`: reescrita función `parse_inh_report` (líneas ~226-429)
# CONTEXT.md — Banca Hípica P2P 🏇

> **Bitácora y guía técnica del proyecto.** Este archivo documenta la estructura de
> carpetas, los endpoints, el modelo de base de datos (SQLite) y las reglas de
> negocio (comisión del 5 %, tipos de duelo y escrow). Sirve como memoria de
> contexto para continuar el desarrollo sin perder continuidad.

**Última actualización:** 2026-10-06 — *Fases 7 y 8 completadas: parser INH columna-aware y botón de carga de cartelera funcional.*

---

## 1. Reglas de oro del proyecto

1. **CERO SHELL / TERMINAL:** toda creación y modificación de archivos se hace
   exclusivamente con las herramientas nativas de archivos/edición de VS Code.
   Ningún comando de shell, terminal o script de consola.
2. **`CONTEXT.md` obligatorio:** se debe mantener actualizado con estructura,
   endpoints, modelo de datos y reglas de negocio.
3. Convenciones: español en UI y comentarios, backend en Python (FastAPI),
   frontend estático móvil (HTML + Tailwind CDN), sin frameworks JS.

---

## 2. Estructura de carpetas

```
/BANCA HIPICA/
├── CONTEXT.md                     ← Este archivo (bitácora técnica)
├── backend/
│   ├── main.py                    ← Punto de entrada FastAPI + montaje del frontend
│   ├── database.py                ← Modelos SQLite + constantes de negocio + seed
│   ├── schemas.py                 ← Modelos Pydantic (peticiones/respuestas)
│   ├── security.py                ← Hash de contraseñas + token Bearer + require_admin
│   ├── parsers.py                 ← Parser de cartelera: reporte INH + CSV plano
│   ├── requirements.txt           ← Dependencias (fastapi, uvicorn, sqlalchemy…)
│   ├── banca_hipica.db            ← SQLite (se crea automáticamente al arrancar)
│   ├── __init__.py
│   └── routers/
│       ├── __init__.py
│       ├── auth.py                ← Registro / login / perfil / logout
│       ├── duel_types.py          ← CRUD de tipos de duelo (solo admin escribir)
│       ├── races.py               ← Cartelera: lectura + carga de archivo (admin)
│       ├── duels.py               ← Crear / listar / aceptar / cancelar / resolver
│       ├── payments.py            ← Banco, recargas y retiros (usuario + admin)
│       └── audit.py               ← Auditoría de balances, volumen y comisiones
└── frontend/
    ├── index.html                 ← SPA mobile-first (todas las vistas)
    ├── cartelera_ejemplo.csv      ← Plantilla CSV plano para la carga
    ├── ejemplares_inh_ejemplo.csv ← Plantilla del reporte oficial INH
    ├── css/styles.css             ← Componentes base (.card, .btn, .badge…)
    └── js/
        ├── api.js                 ← Cliente HTTP (Bearer, errores, sesión)
        ├── app.js                 ← Auth, navegación y vistas de usuario
        └── admin.js               ← Módulos de administración (CRUD, resolver…)
```

---

## 3. Cómo ejecutar el proyecto

> ⚠️ Estos comandos están documentados para el usuario; el asistente NO ejecuta
> shell según la regla de oro 1.

```bash
# 1) Desde la RAÍZ del proyecto (c:\BANCA HIPICA)
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r backend/requirements.txt

# 2) Arrancar el servidor (sirve API + frontend en el mismo puerto)
uvicorn backend.main:app --reload
```

- App móvil: `http://localhost:8000/`
- Swagger (API docs): `http://localhost:8000/docs`
- **Credenciales iniciales de administrador:** `admin` / `admin123`
  (sembradas en `database.seed_initial_data()`; cambiar tras el primer acceso).
- El registro público siempre crea cuentas con `role = "user"` y balance `0.00`.

---

## 4. Modelo de base de datos (SQLite — `backend/banca_hipica.db`)

Motor: **SQLAlchemy** (declarative). Las tablas se crean automáticamente con
`Base.metadata.create_all()` en el arranque.

| Tabla | Columnas | Notas |
|---|---|---|
| **`users`** | `id`, `username` (único), `password_hash`, `balance`, `role` (`'admin'` \| `'user'`), `created_at` | `password_hash = salt$sha256(salt:contraseña)` |
| **`auth_tokens`** | `id`, `token` (único), `user_id`, `created_at` | Sesiones móviles por `Authorization: Bearer <token>` |
| **`bank_info`** | `id`, `bank_name`, `phone`, `id_number` (cédula), `account_type`, `holder_name`, `updated_at` | Fila única centralizada del administrador |
| **`race_entries`** | `id`, `race_number`, `race_datetime`, `horse_number`, `horse_name` | Única constraint `(race_number, horse_number)` → upsert idempotente |
| **`official_results`** | `id`, `race_number`, `position` (1–5), `horse_number`, `horse_name`, `recorded_by`, `created_at` | **Marcador oficial de llegada (top 5)**; únicas `(race, posición)` y `(race, caballo)`. Un caballo fuera del top 5 no tiene fila ⇒ "fuera del marcador" (perdedor) |
| **`duel_types`** | `id`, `name`, `logic_rule`, `description` | CRUD exclusivo del admin |
| **`duels`** | `id`, `duel_type_id`, `race_number`, `race_datetime`, `horse_creator`, `horse_opponent`, `horse_creator_name`, `horse_opponent_name`, `horse_acceptor`, `stake`, `fee_percentage` (= 0.05), `status`, `creator_id`, `acceptor_id`, `winner_id`, `winner_horse_number`, `commission_amount`, `payout_amount`, `resolution_note`, `created_at`, `accepted_at`, `resolved_at` | Escrow + comisión |
| **`top_up_requests`** | `id`, `user_id`, `amount`, `reference`, `wallet_phone`, `status`, `created_at`, `reviewed_at`, `reviewed_by`, `note` | Recargas por pago móvil |
| **`withdrawal_requests`** | `id`, `user_id`, `amount`, `destination_phone`, `status`, `created_at`, `reviewed_at`, `reviewed_by`, `note` | Retiros |

**Estados**

- Duelo: `OPEN` → `ACTIVE` → `RESOLVED`.
- Solicitudes de pago: recarga `PENDING` → `APPROVED` | `REJECTED`;
  retiro `PENDING` → `PAID` | `REJECTED`.

**Seed automático (`database.seed_initial_data()`):**
usuario `admin`, 4 tipos de duelo por defecto (menor número / mayor número /
manual / **posiciones oficiales top 5**) y una fila vacía de `bank_info`.
En bases existentes creadas antes de la Fase 3, el tipo `OFFICIAL_FINISH` puede
crearse desde el panel de Tipos de Duelo.

---

## 5. Reglas de negocio

### 5.1 Comisión de la casa (5 %)
- `duels.fee_percentage = 0.05` se fija **al crear** cada duelo.
- Al resolver: `pozo = stake × 2`; `comisión = round(pozo × 0.05, 2)` (la casa);
  `pago = pozo − comisión` (95 %) se abona al usuario ganador.
- Las comisiones quedan auditables en `duels.commission_amount` y se suman en
  `GET /admin/audit`.

### 5.2 Escrow (retención de fondos)
| Momento | Efecto en balances |
|---|---|
| `POST /duels/create` | Se **descuenta** `stake` del creador y queda retenido (duelo `OPEN`). |
| `POST /duels/{id}/accept` | Se **descuenta** `stake` del oponente → pozo completo en escrow (`ACTIVE`). |
| `POST /admin/duels/{id}/resolve` | Pago 95 % al ganador + 5 % retenido como comisión. |
| `POST /duels/{id}/cancel` (solo `OPEN`, creador o admin) | Reembolso total al creador y **eliminación** del registro (mantiene los 3 estados oficiales). |
| Regla `TIE_REFUND` al resolver | Reembolso del 100 % a ambos, **sin comisión**. |

El escrow vivo se audita en `GET /admin/audit → escrow.total_held`
(= stakes `OPEN` + pozos `ACTIVE`).

### 5.3 Tipos de duelo y reglas lógicas (`duel_types.logic_rule`)
| `logic_rule` | Comportamiento al resolver |
|---|---|
| `LOWEST_HORSE_NUMBER` | Gana automáticamente el caballo de **menor** número. |
| `HIGHEST_HORSE_NUMBER` | Gana automáticamente el caballo de **mayor** número. |
| `MANUAL` | El administrador **debe** indicar `winner_horse_number` (resultado oficial). |
| `TIE_REFUND` | El admin declara empate → reembolso total, comisión 0. |
| `OFFICIAL_FINISH` | **Gana el caballo con mejor posición en el marcador oficial (1°-5°)**; requiere que la carrera tenga posiciones registradas; si ambos quedan fuera del top 5 → reembolso sin comisión. |

- Cuando la carrera **tiene marcador oficial**, la regla `MANUAL` también se
  **valida** contra él: la selección del admin debe coincidir con el ganador
  calculado (si coincide se usa directamente; si ambos están fuera del top 5
  se reembolsa). Las reglas numéricas (`LOWEST`/`HIGHEST`) son sintéticas y no
  se contrastan con el marcador.

- Solo el admin puede **crear, modificar y eliminar** tipos de duelo.
- `DELETE /admin/duel-types/{id}` devuelve **409** si existen duelos que lo
  referencian (se debe modificar en su lugar).
- El motor valida que el caballo ganador sea uno de los dos en pugna y que no
  contradiga una regla determinista.

### 5.4 Duelos (usuario y admin)
- El creador elige: **tipo de duelo + carrera + su caballo + caballo rival +
  stake**. Ambos caballos deben existir en esa carrera y ser distintos.
- El oponente **igual el stake** con un toque y queda asignado al caballo rival
  propuesto (`horse_acceptor = horse_opponent`).
- No se puede aceptar el propio duelo ni aceptar duelos `ACTIVE`/`RESOLVED`.
- **Solo el admin** resuelve duelos `ACTIVE`.

### 5.5 Pagos móviles y retiros
- **Recarga:** el usuario reporta monto + referencia + teléfono → `PENDING`;
  el admin aprueba (abona el balance) o rechaza (sin efecto).
- **Retiro:** el monto se descuenta **de inmediato** y queda retenido en la
  solicitud; el admin la marca `PAID` (ya no se toca el balance) o `REJECTED`
  (reembolsa el monto al usuario).

### 5.6 Resultados oficiales de llegada (1° al 5° lugar)
- El administrador registra por carrera **exactamente 5 posiciones**
  (`1°…5°`) con el número de cada ejemplar (tabla `official_results`).
- **Regla del top 5:** todo caballo que *no* figure en el 1° al 5° lugar está
  **fuera del marcador (no clasificado / perdedor)**.
- Al guardar el marcador, la API devuelve la **previsualización** de los duelos
  ACTIVOS de esa carrera con el ganador sugerido (`official_outcome`) y la
  nota explicativa; desde la UI se puede resolver con un toque.
- `POST /admin/duels/{id}/resolve` **usa o valida** el marcador:
  * Regla `OFFICIAL_FINISH`: calcula el ganador automáticamente (409 si la
    carrera no tiene marcador; reembolsa si ambos quedaron fuera del top 5).
  * Regla `MANUAL`: si hay marcador, la selección del admin debe coincidir
    (409 en caso contrario) y puede omitirse (se toma el del marcador).
- El marcador puede corregirse (el POST reemplaza el registro de la carrera);
  los duelos ya resueltos no se reabren.

## 6. Endpoints de la API

Autenticación: cabecera `Authorization: Bearer <token>` (obtenida en login).
`_admin` indica que el endpoint exige `role = "admin"` (403 en caso contrario).

### Auth
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/auth/register` | Crea cuenta (`role=user`, balance 0) y devuelve token (201) |
| POST | `/auth/login` | Devuelve `{token, user}` |
| GET | `/auth/me` | Perfil + balance actual |
| POST | `/auth/logout` | Invalida el token actual |

### Admin — Tipos de duelo (CRUD)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/duel-types` | Catálogo público (formulario de crear duelo) |
| GET | `/admin/duel-types/{id}` | Detalle (admin) |
| POST | `/admin/duel-types` | Crear (admin) |
| PUT | `/admin/duel-types/{id}` | Modificar (admin) |
| DELETE | `/admin/duel-types/{id}` | Eliminar (admin; 409 si está en uso) |

### Cartelera
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/races` | Cartelera oficial ordenada |
| POST | `/admin/races/upload` | **Carga de archivo** `multipart/form-data`, campo `file` (reporte INH o CSV plano, formato autodetectado) |
| DELETE | `/admin/races/{entry_id}` | Elimina una entrada (admin) |
| GET | `/admin/races/{race_number}/official-results` | Marcador oficial guardado (1°-5°) + previsualización de duelos activos (admin) |
| POST | `/admin/races/{race_number}/official-results` | **Registra/corrige las 5 posiciones oficiales** de la carrera (`{"positions": [{"position": 1, "horse_number": 4}, …]}`) y devuelve el ganador sugerido por duelo (admin) |

### Duelos
| Método | Ruta | Descripción |
|---|---|---|
| POST | `/duels/create` | Publica duelo reteniendo `stake` en escrow (201) |
| GET | `/duels/available` | Duelos `OPEN` de la comunidad (excluye los propios) |
| GET | `/duels/mine` | Duelos donde soy creador u oponente |
| GET | `/duels/{duel_id}` | Detalle de un duelo |
| POST | `/duels/{duel_id}/accept` | Acepta igualando el stake (escrow) |
| POST | `/duels/{duel_id}/cancel` | Cancela duelo `OPEN` con reembolso |
| GET | `/admin/duels?status=…` | Cola administrativa (`OPEN`/`ACTIVE`/`RESOLVED`) |
| POST | `/admin/duels/{duel_id}/resolve` | **Solo admin:** aplica la regla (usa/valida el marcador oficial 1°-5° si existe), paga 95 % y retiene 5 % |

### Banco, recargas y retiros
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/bank` | Datos bancarios para recargar |
| PUT | `/admin/bank` | Configura los datos bancarios (admin) |
| POST | `/payments/topup` | Reporta pago móvil → `PENDING` (201) |
| GET | `/payments/topups` | Mis recargas |
| POST | `/payments/withdraw` | Solicita retiro (descuenta y retiene) (201) |
| GET | `/payments/withdrawals` | Mis retiros |
| GET | `/admin/topups?status=` | Cola de recargas (admin) |
| POST | `/admin/topups/{id}/approve` | Aprueba y abona (admin) |
| POST | `/admin/topups/{id}/reject` | Rechaza (admin) |
| GET | `/admin/withdrawals?status=` | Cola de retiros (admin) |
| POST | `/admin/withdrawals/{id}/pay` | Marca como pagado (admin) |
| POST | `/admin/withdrawals/{id}/reject` | Rechaza y reembolsa (admin) |

### Auditoría y sistema
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/admin/audit` | Balances, volumen, comisiones 5 %, escrow y pagos |
| GET | `/admin/users` | Padrón de cuentas con balances |
| GET | `/health` | Sonda de estado |
| GET | `/docs` | Swagger UI (generado por FastAPI) |

## 7. Carga de cartelera — parser inteligente de doble formato

`POST /admin/races/upload` delega en el servicio **`backend/parsers.py`**
(`parse_cartelera(raw, filename)`), que decodifica, **detecta el formato
automáticamente** y parsea. Procesamiento **atómico**: ante cualquier error NO
se importa nada y se devuelve el detalle de los errores.

### 7.0 Tipos de archivo admitidos
- **Texto plano:** `.csv` / `.txt` (codificación `utf-8-sig` → `cp1252` →
  `latin-1`, ver §7.1).
- **Excel nativo:** `.xlsx` / `.xlsm` (leído en memoria con `openpyxl`) y
  `.xls` legado (leído en memoria con `xlrd`) — **no requieren conversión
  previa a CSV**. El archivo se detecta por extensión o, si falta, por firma
  binaria (`PK\x03\x04` para xlsx/zip, `D0 CF 11 E0` para xls/OLE2).
  Internamente la hoja activa se convierte a un texto CSV equivalente
  (delimitador `;`) mediante `_read_xlsx()` / `_read_xls()`, reutilizando sin
  duplicar código la misma lógica de detección de formato (A/B) y extracción
  de carreras/ejemplares que el texto plano. Si `openpyxl`/`xlrd` no están
  instalados, el endpoint responde `400` con un mensaje claro indicando cómo
  instalarlos (ambos están declarados en `backend/requirements.txt`).
- El endpoint valida la extensión contra `ALLOWED_RACE_EXTENSIONS` en
  `backend/routers/races.py` (`.csv`, `.txt`, `.xlsx`, `.xlsm`, `.xls`) y
  responde `400` con un mensaje explícito si el tipo no es admitido.

### 7.1 Codificación
Cadena de decodificación `utf-8-sig` → `cp1252` → `latin-1`:
- `latin-1` es el fallback final del reporte INH (decodifica cualquier byte,
  nunca falla); `cp1252` cubre los caracteres institucionales.
- `utf-8-sig` preserva la plantilla CSV plano existente.
- Se elimina el BOM (`\uFEFF` / `ï»¿`) antes de parsear.

### 7.2 Formato A · Reporte oficial INH (p. ej. «Ejemplares inscritos reunión 39.csv»)
Diseño de reporte institucional con metadatos por carrera y bloques tabulares:

```text
INSTITUTO NACIONAL DE HIPÓDROMOS
EJEMPLARES INSCRITOS - REUNIÓN 39

Carrera Nro: 1
Fecha: 06/10/2026
Hora: 14:30
Distancia: 1.200 m

N°;Ejemplar;Edad;Sexo;Peso;Jinete;Entrenador
1;Torpedo Relámpago;4;M;52;J. Pérez;L. Gómez
2;Caribe Dorado;5;H;51;M. Rojas;A. Díaz
```

**Detección (`detect_format`):** es INH si el archivo contiene líneas que
empiezan por `Carrera …`, o si menciona «ejemplar(es)» junto con una cabecera
`N°;`/`N°|` o la palabra «inscritos». En caso contrario usa el CSV plano.

**Parseo nativo con `csv.reader` (`parse_inh_report`):** el archivo completo se
lee con `csv.reader(io.StringIO(text), delimiter=";", quotechar='"')` (NO línea
a línea con `str.split`), de modo que reconoce correctamente campos **multilínea
entre comillas** (p. ej. `"Carrera Nro:\n1"` o nombres de ejemplares de reclamo
con precio en varias líneas) sin fragmentar los bloques. Cada celda se limpia
con `_clean_cell_text()` (saltos de línea internos → un solo espacio) antes de
usarse, tanto para detectar metadatos como para el nombre del ejemplar.

1. **Número de carrera:** regex anclada al inicio de línea — acepta
   `Carrera Nro: X`, `CARRERA 1`, `Nro. Carrera: 3`, `1) Carrera 2`, etc. Si la
   celda/línea trae la **etiqueta sin el número** (exportación de celdas
   combinadas de Excel a CSV, donde el valor queda en la fila siguiente), el
   parser activa un estado `pending_label="carrera"` y toma el número de la
   próxima línea no vacía; lo mismo aplica a `Fecha:` y `Hora:` sueltas.
2. **Fecha y hora:** se combinan `Fecha:` + `Hora:` del encabezado del bloque
   (variantes `14.30` y `14 h 30`, o en fila separada como se explica arriba);
   si el bloque no los trae, se usan los del encabezado del reporte (previos a
   la primera carrera).
3. **Ejemplares:** al detectar la cabecera de tabla se identifican las columnas
   `N°` (alias `Nro`, `Nº`, `N.°`, `N`, `Núm`…) y `Ejemplar` (alias `Caballo`,
   `Nombre`…), con delimitador autodetectado entre `;` `,` `|` y tabulación;
   las filas se leen hasta la línea en blanco o el siguiente bloque. El nombre
   del ejemplar se limpia de saltos de línea internos (reclamo/precio en varias
   líneas) antes de guardarse.
4. **Se ignoran:** títulos, metadatos (`Distancia: …`), líneas sin dígitos en
   `N°`, pies de página y secciones de **suplentes** (automáticamente).
5. **Validación por carrera:** fecha y hora obligatorias y válidas; errores
   claros, p. ej. `Carrera 3: falta la hora (línea 'Hora: HH:MM').`,
   `Carrera 2: no tiene ejemplares en su tabla.` o `Línea 14: tabla de
   ejemplares sin un bloque 'Carrera Nro: X' anterior.`

**Guardado:** upsert por `(race_number, horse_number)` — sin duplicados; si ya
existe, actualiza nombre y fecha/hora. Plantilla de prueba:
`frontend/ejemplares_inh_ejemplo.csv`.

### 7.3 Formato B · CSV/Excel plano (una fila por ejemplar)
Encabezados exactos esperados en la **fila 1** (orden indiferente):
`numero_carrera`, `numero_caballo`, `nombre_caballo`, `fecha`, `hora`.

```csv
numero_caballo,nombre_caballo,numero_carrera,fecha,hora
1,Torpedo Relámpago,1,2026-10-10,14:30
2,Caribe Dorado,1,2026-10-10,14:30
```

**Alias admitidos por columna** (normalizados a minúsculas, sin espacios;
ver `ALIASES` en `backend/parsers.py`):
| Campo | Encabezado estándar | Alias aceptados |
|---|---|---|
| N.º de caballo | `numero_caballo` | `num_caballo`, `caballo`, `horse_number`, `no_caballo` |
| Nombre del caballo | `nombre_caballo` | `nombre`, `horse_name`, `caballo_nombre` |
| N.º de carrera | `numero_carrera` | `num_carrera`, `carrera`, `race_number` |
| Fecha | `fecha` | `fecha_carrera`, `date`, `race_date` |
| Hora | `hora` | `hora_carrera`, `time`, `race_time` |

- Fecha: `AAAA-MM-DD` o `DD/MM/AAAA`; Hora: `HH:MM`.
- Si falta alguna columna obligatoria, el endpoint responde con
  `Faltan columnas: <lista>. Encabezado esperado: numero_caballo,nombre_caballo,numero_carrera,fecha,hora`.
- Si el archivo es Excel (`.xlsx`/`.xlsm`/`.xls`), la fila 1 de la hoja activa
  debe contener estos mismos encabezados; el resto de filas son los datos.
- Errores detectados: faltan columnas, filas incompletas o fechas inválidas.

### 7.4 Respuestas del endpoint

**Éxito (200):**
```json
{
  "detail": "Cartelera procesada correctamente (Reporte oficial INH).",
  "format": "INH",
  "format_label": "Reporte oficial INH",
  "encoding": "cp1252",
  "imported": 8,
  "updated": 0,
  "total_rows": 8,
  "race_numbers": [1, 2],
  "races": [
    {"race_number": 1, "datetime": "2026-10-06 14:30", "horses": 4},
    {"race_number": 2, "datetime": "2026-10-06 15:15", "horses": 4}
  ]
}
```

**Error (400):**
```json
{
  "message": "No se importó ningún ejemplar — Reporte oficial INH (codificación cp1252). Corrige los errores y reintenta.",
  "format": "INH",
  "errors": ["Carrera 3: falta la hora (línea 'Hora: HH:MM')."]
}
```

El panel de administración renderiza ambos estados en `#upload-result`
(tarjeta verde con el resumen de la importación masiva y carreras procesadas,
o tarjeta roja con la lista de errores, máx. 20 en pantalla) — ver
`uploadRaces()` en `frontend/js/admin.js`.

### 7.5 Reglas comunes
- **Upsert/idempotente:** si `(carrera, caballo)` ya existe, actualiza nombre
  y fecha/hora; nunca se duplican filas (hay además constraint único en la BD).
- **Atómico:** cualquier error impide la importación completa.
- Plantillas descargables: `frontend/ejemplares_inh_ejemplo.csv` (INH) y
  `frontend/cartelera_ejemplo.csv` (CSV plano).



---

## 8. Frontend móvil (`/frontend`)

SPA mobile-first con **Tailwind CDN** (sin paso de build) + `css/styles.css`.

- **Usuario:** Dashboard (balance), Crear Duelo (tipo → carrera → caballos en
  cascada → stake), Duelos Abiertos (aceptar con un toque), Mis Duelos
  (cancelar si `OPEN`), Recarga (datos bancarios + reporte de pago) y Retiro.
- **Administrador:** Tipos de Duelo (CRUD), Cartelera (subida de archivo),
  **Resultados oficiales** (selector de carrera + puestos 1°-5° con aviso de
  "fuera del top 5 = no clasificado", marcador guardado y duelos activos con
  sugerencia y botón de resolución), Resolver Duelos (muestra el marcador, el
  pozo, la comisión 5 % y el pago al ganador en pantalla),
  Aprobar Recargas/Retiros (con filtros), Configurar Banco y Auditoría
  (KPIs de volumen y comisiones).
- Navegación por barra inferior fija con píldoras desplazables; los ítems admin
  solo se renderizan para `role = "admin"`.
- Archivos: `js/api.js` (HTTP + sesión en `localStorage`), `js/app.js` (auth,
  ruteo de vistas y módulos de usuario), `js/admin.js` (módulos admin que se
  enlazan mediante `Admin.bind()` en el `DOMContentLoaded`).

---

## 9. Bitácora de desarrollo

| Fecha | Fase | Detalle |
|---|---|---|
| 2026-10-06 | **Fase 1 — Base** | Estructura `/backend` + `/frontend` + `CONTEXT.md`. Modelos SQLite completos, auth Bearer, CRUD de tipos de duelo, carga CSV de cartelera, duelos con escrow, resolución admin con comisión 5 %, banco/recargas/retiros, auditoría y SPA mobile-first. |
| 2026-10-06 | **Fase 2 — Parser INH** | Nuevo servicio `backend/parsers.py`: decodificación `utf-8-sig → cp1252 → latin-1`, parser por bloques del reporte oficial INH (`Carrera Nro` + `Fecha`/`Hora` + tablas `N° | Ejemplar`, delimitador autodetectado, sección de suplentes omitida), detección automática de formato, respuestas enriquecidas (`format`, `encoding`, resumen por carrera), tarjetas de estado de importación en la UI admin y plantilla `ejemplares_inh_ejemplo.csv`. |
| 2026-10-06 | **Fase 3 — Resultados oficiales (1°-5°)** | Tabla `official_results` + regla `OFFICIAL_FINISH`; endpoints `GET/POST /admin/races/{race_number}/official-results` con validación (5 puestos, caballos únicos y en cartelera) y previsualización de duelos activos; motor de resolución refactorizado (`resolve_duel_core`, `_resolve_payout`, `_resolve_refund`) con uso/validación del marcador; nueva vista admin "🏁 Resultados oficiales" y enriquecimiento de la vista Resolver (marcador, sugerencia y botón deshabilitado sin marcador). |
| 2026-10-06 | **Fase 4 — Parser INH multilínea** | Corrección de `parse_inh_report` (`backend/parsers.py`) para soportar la estructura semiestructurada real del reporte INH: lectura íntegra con `csv.reader(io.StringIO(text), delimiter=";", quotechar='"')` que respeta campos multilínea entre comillas (reclamo/precio en varias líneas); nueva `_clean_cell_text()` que une saltos de línea internos de cada celda; nuevo estado `pending_label` que resuelve el caso de etiquetas (`Carrera Nro:`/`Fecha:`/`Hora:`) y su valor en filas separadas (celdas combinadas de Excel exportadas a CSV), eliminando el falso error "tabla de ejemplares sin bloque". Verificado que `frontend/js/admin.js` ya exportaba `Admin.uploadRaces` en el `return` del IIFE y que `#upload-race-btn` ya disparaba `uploadRaces()` con manejo de éxito/error en `#upload-result` — sin cambios necesarios en el frontend. |
| 2026-10-06 | **Fase 5 — Soporte nativo de Excel (.xlsx/.xls)** | `backend/parsers.py`: importación segura (`try/except ImportError`) de `openpyxl` y `xlrd`; nuevas `_sniff_excel_extension()` (detección por firma binaria ZIP/OLE2), `_cell_to_str()` (normaliza fechas/horas nativas de Excel a texto `dd/mm/aaaa`/`HH:MM`), `_trim_blank_edges()` (descarta filas 100% vacías al inicio/final de la hoja — artefacto típico de Excel: fila 1 en blanco antes del encabezado real, o filas finales con formato heredado y una celda de fecha "fantasma"), `_rows_to_csv_text()`, `_read_xlsx()` y `_read_xls()` que convierten la hoja activa a un texto CSV equivalente (delimitador `;`) y REUTILIZAN sin duplicar lógica `parse_inh_report`/`parse_flat_csv`/`detect_format`; `parse_cartelera()` ahora acepta `filename` para decidir la ruta de lectura (texto vs Excel); `parse_flat_csv()` autodetecta el delimitador de la primera línea (soporta `;` generado desde Excel además de `,`) y ya NO exige `fecha` para considerar una fila "con datos" (evita falsos errores con filas fantasma que solo traían una fecha heredada). `backend/routers/races.py`: nueva constante `ALLOWED_RACE_EXTENSIONS` (`.csv`, `.txt`, `.xlsx`, `.xlsm`, `.xls`) con validación explícita y mensaje 400 claro; se reenvía `file.filename` al parser; docstrings actualizadas documentando ambos formatos (A/B) y tipos de archivo. `backend/requirements.txt`: añadidas dependencias `openpyxl` y `xlrd` — **instaladas y verificadas** en el entorno (`openpyxl 3.1.5` ya presente, `xlrd 2.0.2` instalado con `pip install openpyxl xlrd`). Frontend (`index.html`/`admin.js`): `input#race-file` ahora acepta `.xlsx`/`.xlsm`/`.xls` además de `.csv`/`.txt`; tarjeta informativa reescrita con los encabezados exactos y alias del Formato B y los tipos de archivo admitidos; mensaje del toast inicial actualizado. **Validado end-to-end** con el archivo real `Ejemplares inscritos reunión 39.xlsx` vía `POST /admin/races/upload` (`TestClient`): `200 OK`, 16 ejemplares importados en 2 carreras, 0 errores. |

| 2026-10-06 | **Fase 6 — Fix: encabezado B mal clasificado como INH** | Bug real detectado con el archivo `formato definitivo.xlsx` (encabezado `carrera,caballo_nro,nombre,fecha,hora`): `detect_format()` clasificaba como "INH" cualquier primera línea que EMPEZARA con la palabra "carrera" (incluido un encabezado de columna legítimo del Formato B), haciendo que `parse_inh_report` no encontrara bloques ni tabla y devolviera `rows=[]` sin errores → el endpoint respondía 400 con el mensaje genérico "El archivo no contiene ejemplares válidos" sin pista real. Corregido en `backend/parsers.py`: `detect_format()` ahora revisa PRIMERO si la primera línea no vacía es un encabezado de Formato B reconocido (usando el nuevo conjunto `ALL_HEADER_ALIASES` y comprobando que estén presentes `race_number` + `horse_number` + `horse_name`) y en ese caso devuelve `"CSV"` de inmediato, antes de evaluar `RE_INH_CARRERA`. Además se ampliaron los `ALIASES` (`caballo_nro`, `carrera_nro`, `ejemplar`, etc.) y se aplicó `_clean_cell_text()` también en `parse_flat_csv.pick()` (antes solo se limpiaban saltos de línea en el reporte INH, no en el Formato B) para que nombres con reclamo/precio multilínea también se normalicen correctamente. El mensaje de error "no contiene ejemplares válidos" ahora expone el formato/codificación detectados y la estructura esperada de ambos formatos, para que cualquier caso límite futuro sea diagnosticable desde el mensaje mismo. **Validado end-to-end** con `formato definitivo.xlsx` (encabezado `carrera,caballo_nro,nombre,fecha,hora`, 3 carreras, nombre con reclamo multilínea): `200 OK`, 24 ejemplares importados, 0 errores. |
| 2026-10-06 | **Dependencias instaladas** | `openpyxl 3.1.5` (ya presente) y `xlrd 2.0.2` (instalado con `pip install openpyxl xlrd`) verificados en el entorno Python 3.14.2 del sistema (no hay `.venv` en el proyecto); resto de `backend/requirements.txt` confirmado satisfecho con `pip install -r backend/requirements.txt`. |

### Posibles siguientes fases (pendientes)
- [ ] Pruebas unitarias de negocio (escrow, comisión, reglas lógicas).
- [ ] Exportación CSV de auditoría y moneda configurable.
- [ ] Cierre automático de duelos antes de la hora oficial de la carrera.
- [ ] Notificaciones/sonidos al aceptar y resolver duelos.
- [ ] Cambiar la contraseña admin inicial y endurecer el hashing (bcrypt/argon2).





## Fase 9: Implementación de estructuras dinámicas de duelos, soporte MOROCHA (2v2) y reglas de resolución (2026-10-09)

**Resumen:** Se completó la implementación de las 19 modalidades de duelo, incluyendo interfaz dinámica para duelos individuales (1 caballo), MARCAS (2 caballos - 1v1) y MOROCHA (4 caballos - 2v2). Se actualizó el backend y frontend para soportar campos opcionales de segundos caballos, validación de unicidad de caballos, lógica de resolución basada en mejor posición oficial y se actualizó la documentación.

**Cambios realizados:**

- **backend/database.py:** Añadido columnas `is_matchup` y `is_morocha` en tabla `duel_types`; campos opcionales `horse_creator_2`, `horse_opponent_2`, `horse_creator_2_name`, `horse_opponent_2_name` en tabla `duels`; se actualizó el seeder para incluir los 19 tipos de duelo con las banderas correspondientes; incluida función `official_outcome` para resolución basada en marcador oficial.

- **backend/models.py:** (En realidad los modelos están en database.py) se reflejaron los cambios arriba mencionados.

- **backend/schemas.py:** Modelos Pydantic `DuelTypeOut`, `DuelCreate` y `DuelOut` actualizados con soporte de campos opcionales para MOROCHA.

- **backend/routers/duels.py:** Endpoint POST `/duels/create` incluye validación de 4 caballos únicos para MOROCHA y persistencia de ejemplares secundarios.

- **backend/services/resolution.py:** Lógica de resolución para duelos estándar, MARCAS y MOROCHA (comparación por mejor posición oficial).

- **backend/database.py:** Inclusión de `official_outcome` y seeder actualizado de 19 tipos de duelo.

- **frontend/js/app.js:** Lógica dinámica `renderHorseSelects()` que renderiza 1, 2 o 4 selectores según la modalidad; `bindForms()` lectura adaptativa de payload y variables globales `globalDuelTypes` / `currentRaceEntries`.

- **frontend/index.html:** Presencia del contenedor `<div id=\"horses-select-container\">`.

- **Documentación:** Actualización de este archivo (CONTEXT.md) para reflejar los cambios.

Se han realizado pruebas manuales en el navegador verificando el correcto funcionamiento de todas las modalidades y la interacción entre frontend y backend.


## Fase 10: Adaptación visual y lógica para tarjetas de duelos (duelCard) y validaciones backend (2026-10-09)

**Resumen:** Se completó la adaptación del flujo de visualización y validación para las 19 modalidades hípicas P2P, asegurando que tanto el backend como el frontend presenten correctamente duelos individuales, MARCAS (1v1) y MOROCHA (2v2) en la vista de tarjetas de duelos (duelCard) y en el formulario de creación.

**Cambios realizados:**

- **Backend (backend/routers/duels.py):**
  - En el endpoint `POST /duels/create` la validación distingue tres casos:
    1. **Individuales:** `not is_matchup and not is_morocha` → se asigna `horse_opponent = horse_creator` para evitar errores de duplicidad y permitir la publicación con un solo ejemplar seleccionable.
    2. **MARCAS:** `is_matchup` → se requieren dos caballos distintos (horse_creator y horse_opponent).
    3. **MOROCHA:** `is_morocha` → se requieren cuatro caballos distintos (horse_creator, horse_creator_2, horse_opponent, horse_opponent_2).

- **Frontend Adaptativo (frontend/js/app.js):**
  - **Mapeo de Condiciones Inversas (INDIVIDUAL_CONDITIONS):** En duelos individuales de un solo caballo (ej. PELO a PELO, 2 PUESTOS, etc.), el creador ve la condición a favor del ejemplar mostrada como “A FAVOR”, mientras que el oponente que consulta el duelo en la pestaña de duelos abiertos observa automáticamente la condición opuesta/inversa, etiquetada como “CONDICIÓN DE VICTORIA SI ACEPTAS”.
  - La función `renderHorseSelects()` ya inyecta dinámicamente:
    - 1 selector para duelos individuales (tipos 1 al 17).
    - 2 selectores para MARCAS (`is_matchup`).
    - 4 selectores para MOROCHA (`is_morocha`).
  - Todos los selectores de caballos incluyen la opción por defecto **-- Selecciona un caballo --** (value vacío, deshabilitada) para forzar una elección explícita.
  - El payload del formulario `create-duel-form` envía `horse_opponent: 0` para duelos individuales, evitando colisiones de validación en el backend.

- **Estructura Adaptativa de duelCard (en el HTML generado por JavaScript):**
  - **MOROCHA (2v2):** Renderiza las dos parejas de caballos enfrentadas, resaltando visualmente el par que defenderá el contrincante.
  - **MARCAS (1v1):** Muestra el duelo directo de 1 contra 1 con un diseño claro de “VS”.
  - **INDIVIDUALES:** Elimina el diseño duplicado de “VS” y lo sustituye por un contenedor unificado que muestra el nombre del ejemplar y la regla de victoria correspondiente al usuario (según INDIVIDUAL_CONDITIONS).

Se han realizado pruebas manuales en el navegador verificando que:
- El formulario de creación se adapta correctamente según el tipo de duelo.
- El payload enviado al backend es válido para cada modalidad.
- Las tarjetas de duelo (`duelCard`) muestran la información esperada tanto para el creador como para el oponente.
- No hay errores de validación ni de renderizado en ninguna de las 19 modalidades.


## Fase 11: Calculadora de Retorno Neto y Exclusión Inteligente de Selecciones (2026-10-09)

**Resumen:** Se integraron mejoras de usabilidad en el formulario de creación de duelos: una calculadora de retorno neto en tiempo real y una lógica de exclusión inteligente que evita la selección de caballos duplicados en modalidades MARCAS y MOROCHA. Además, se aseguró la estabilidad de los eventos globales y la delegación para la navegación y acciones.

**Contenido a registrar:**

- **Calculadora de Retorno Neto (#payout-calculator):**
  - Inyectada en el DOM directamente debajo del campo `#stake-input`.
  - La función `updatePayoutCalculator()` se ejecuta en tiempo real (cuando cambia el stake) y muestra:
    - Pozo total: $2 \times \text{stake}$.
    - Comisión de la casa: 5 % del pozo.
    - Pago neto estimado para el ganador: pozo total menos comisión.

- **Exclusión Inteligente de Caballos (handleHorseSelectExclusion):**
  - Integrada dentro de `renderHorseSelects()` mediante un `change` listener en cada `<select>` generado.
  - En modalidades MARCAS (1v1) y MOROCHA (2v2), cuando el usuario selecciona un caballo en un slot propio o rival, esa opción se deshabilita automáticamente en los demás slots para impedir selecciones duplicadas.
  - La exclusión se aplica tanto entre caballos propios como entre caballos rivales, respetando la lógica de cada modalidad.

- **Estabilidad de Eventos y Delegación:**
  - Se verificó la presencia y correcta vinculaciación de las funciones globales:
    - `updatePayoutCalculator()`
    - `handleHorseSelectExclusion()`
    - `bindForms()`
    - `bindDelegation()`
  - Estas funciones están disponibles en el ámbito de `frontend/js/app.js` y son llamadas desde los listeners apropiados (por ejemplo, los `change` de los selects y el `submit` del formulario) para asegurar que la lógica de cálculo y exclusión se mantenga incluso tras actualizaciones dinámicas del DOM.
  - El sistema de navegación basada en atributos `data-nav` y el manejo de acciones mediante `data-action` continúan funcionando sin interferencias.

Se han realizado pruebas manuales en el navegador confirmando que:
- La calculadora se actualiza al modificar el stake y muestra valores correctos.
- Al seleccionar un caballo en un selector, dicha opción desaparece de los otros selectores en MARCAS y MOROCHA, evitando duplicados.
- Las funciones globales permanecen definidas tras recargas parciales de la vista y no generan errores en la consola.

## Fase 12: Modal de Confirmación de Aceptación y Flujo Operativo (2026-10-09)

**Resumen:** Se completó la integración del modal de confirmación para la acción de aceptar un duelo, mejorando la experiencia de usuario al presentar de forma clara las condiciones de victoria, el pozo neto y el saldo requerido. Además, se aseguró la estabilidad de la gestión de eventos y la delegación para evitar registros duplicados.

**Contenido a registrar:**

- **Estructura HTML (`frontend/index.html`):**
  - Se integró correctamente el contenedor del modal de confirmación (`#confirm-modal`) dentro del `<body>` (justo antes de la carga de scripts).
  - Se estructuraron los IDs clave:
    - `confirm-modal`: contenedor principal del modal.
    - `modal-summary-content`: área donde se renderiza dinámicamente el resumen del duelo.
    - `close-modal-btn`: botón para cerrar el modal (X).
    - `cancel-modal-btn`: botón para cancelar la aceptación.
    - `confirm-accept-btn`: botón que confirma la aceptación y envía la petición al backend.

- **Lógica de Aceptación y Modal (`frontend/js/app.js`):**
  - **`openAcceptModal(duel)`:**
    - Renderiza de forma dinámica las condiciones de victoria según el tipo de duelo:
      - *Morocha 2v2:* muestra las dos parejas de caballos y qué par representa al usuario vs. al oponente.
      - *Marcas 1v1:* muestra el enfrentamiento explícito con desglose de caballo propio vs. caballo rival.
      - *Individuales:* aplica las reglas inversas (INDIVIDUAL_CONDITIONS) de modo que el usuario ve la condición a favor de su caballo, mientras que el oponente vería la inversa (aunque aquí el usuario es quien acepta, se muestra la condición que le daría la victoria si acepta).
    - Valida el saldo del usuario contra el *stake* del duelo.
    - Calcula el pozo neto: pozo total = 2 × stake, comisión de la casa = 5 %, pago neto estimado = pozo total − comisión.
    - Bloquea el botón de confirmación si el saldo es insuficiente y muestra un mensaje con acceso directo a la sección de recarga.
  - **`bindDelegation()`:**
    - Maneja de forma unificada y segura (protegida contra múltiples registros con la bandera `_delegationBound`) los siguientes eventos:
      - Cierre del modal mediante `close-modal-btn` o clic fuera del contenido.
      - Confirmación de aceptación mediante llamada POST asíncrona a `/duels/{id}/accept` cuando se pulsa `confirm-accept-btn`.
      - Delegación global para acciones en tarjetas (`accept-duel`, `cancel-duel`) y navegación basada en atributos `data-nav`.
    - Evita que se adjunten listeners múltiples tras recargas parciales de la vista.

- **Flujos Operativos Verificados:**
  - Apertura de modal limpia y responsiva al hacer clic en el botón “Aceptar y retener” de una tarjeta de duelo disponible.
  - Sincronización automática de balances mediante `refreshMe()` después de una aceptación exitosa.
  - Actualización de la lista de duelos disponibles llamando a `loadAvailable()` para reflejar el duelo ya aceptado.
  - Gestión robusta de errores y estados de carga:
    - Los botones se desatribulan (`disabled`) durante las peticiones AJAX para evitar envíos duplicados.
    - Se muestran toast de éxito o error según la respuesta del backend.
    - En caso de saldo insuficiente, el modal indica claramente la cantidad necesaria y ofrece un botón que dirige a la vista de recarga.

Se han realizado pruebas manuales en el navegador confirmando que:
- El modal se abre con la información correcta según el tipo de duelo.
- El cálculo del pozo neto y la comisión se muestra con precisión.
- La exclusión de selección de caballos duplicados sigue funcionando dentro del modal (aunque el modal solo muestra información, no selecciones).
- La lógica de delegación no produce listeners duplicados tras cambiar de vista y volver.
- El flujo completo (abrir modal → aceptar → actualización de balances y listas) se ejecuta sin errores en la consola.

