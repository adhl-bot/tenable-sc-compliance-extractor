# Laboratorio Tenable.sc

Este directorio es la carpeta portable del laboratorio. Contiene los recursos
versionables para levantar, diagnosticar, reparar y comprobar que el laboratorio
local esta sano y listo para trabajar, y puede contener tambien artefactos
locales sensibles ignorados por git:
`labbox-docker.zip`, `.env` y `labbox-utils/`.

La fuente de verdad funcional del proyecto sigue siendo `../agents.md`. Este
README es la guia operativa y de configuracion del laboratorio. Cualquier tarea
que levante, diagnostique, repare, valide que esta listo, migre o consulte la
salud del laboratorio debe leer primero este fichero.

Los resultados de llamadas API, scan results, consultas `/analysis` y
validaciones funcionales no se documentan aqui; viven en
`../VALIDACIONES_TENABLE.md`.

## Objetivo

Mantener un laboratorio reproducible con:

- Tenable.sc en Docker: `tenablesc-labbox-ol8`, publicado en `https://localhost:8443`.
- El alcance Docker del laboratorio queda limitado a Tenable.sc.
- Estado recreable desde las imagenes, sin backups de datos ni restauracion de volumenes.
- Doctor completo para detectar incidencias conocidas y nuevas.
- Repairs separados por tipo de fallo para no aplicar acciones innecesarias.
- Validacion minima del extractor contra datos reales de compliance.

## Configuracion Local

Las credenciales y URLs del laboratorio portable estan preferentemente en
`laboratorio/.env`. Si no existe, el harness usa `../.env` como compatibilidad
y finalmente `laboratorio/.env.example`. No duplicar secretos en documentacion
ni codigo. Mantener `.env` fuera de git y usar `.env.example` como plantilla.

Variables principales del laboratorio y pruebas asociadas:

- `TENABLE_SC_URL`
- `TENABLE_SC_SECURITY_MANAGER_USERNAME`
- `TENABLE_SC_SECURITY_MANAGER_PASSWORD`
- `TENABLE_SC_VERIFY_SSL`
- `TENABLE_SC_AUTH_MODE`
- `TENABLE_SC_ACCESS_KEY`
- `TENABLE_SC_SECRET_KEY`
- `TENABLE_SC_GLOBAL_ADMIN_USERNAME`
- `TENABLE_SC_GLOBAL_ADMIN_PASSWORD`

Los comandos de extraccion usan el usuario Security Manager configurado en
`TENABLE_SC_SECURITY_MANAGER_USERNAME` y
`TENABLE_SC_SECURITY_MANAGER_PASSWORD`. Las tareas globales de administracion,
como configuraciones globales de Tenable.sc, usan
`TENABLE_SC_GLOBAL_ADMIN_USERNAME` y `TENABLE_SC_GLOBAL_ADMIN_PASSWORD` solo en
herramientas operativas puntuales.

## Requisitos

- Windows con Docker Desktop y backend Linux/WSL2 operativo.
- Docker Compose v2 (`docker compose`) o Docker Compose clasico (`docker-compose`).
- Python 3.10 o superior.
- Puerto libre en el host: `8443` para Tenable.sc.
- RAM suficiente para Tenable.sc; se recomienda 8 GB o mas para Docker Desktop.
- `shm_size` de Tenable.sc en `1gb`. Esto es necesario para PostgreSQL e importacion de scans.
- Imagen local `tenablesc-labbox-image-ol8` disponible. Si no existe, se carga desde `laboratorio/labbox-docker.zip`.
- Fichero `laboratorio/.env` con credenciales del laboratorio.

Conocimientos Docker minimos para operar este laboratorio:

- Una imagen Docker es la plantilla del contenedor. El YAML no la incluye.
- Un contenedor es una instancia arrancada desde una imagen.
- Este laboratorio no usa backups de datos para moverse entre maquinas.
- Si se borra un contenedor, se recrea desde la imagen.

## Estado Validado

Estado Docker validado el 2026-05-23 para Fase 1:

- Contenedor Tenable.sc corriendo: `tenablesc-labbox-ol8`.
- Tenable.sc recreado con `shm_size=1gb`.
- `doctor --json` sin incidencias criticas y con warning de logs historicos.
- `validate` completo correctamente y genero
  `../outputs/compliance_example_details.json`.

El doctor debe diagnosticar Docker, red, imagenes, contenedores, `shm_size`,
usuario `tns`, locale, supervisor, PostgreSQL, Redis, WebSocket,
`sc-asset-svc`, artefactos de Asset Lists, API Tenable.sc, recursos API
principales (`repository`, `policy`, `scan`, `scanResult`, `scanner` cuando
haya permisos), filtros `/analysis` y logs recientes.

## Artefactos

- `build_lab.py`: CLI principal para `setup`, `package-status`, `status`, `up`, `doctor`, `repair`, `load-images`, `prepare-assets`, `validate` e `incidents`.
- `docker-compose.yml`: receta Docker canonica del laboratorio.
- `tenablesc-entrypoint.sh`: wrapper de arranque de Tenable.sc que mantiene el
  flujo original de Labbox e instala la configuracion local de supervisor.
- `tenablesc-supervisord.conf`: configuracion local de supervisor para levantar
  automaticamente PostgreSQL, Redis, WebSocket y `sc-asset-svc` junto con
  Apache y Jobd.
- `.env.example`: plantilla sin secretos para crear `.env`.
- `GUIA_USUARIO.md`: guia corta para levantar y validar el laboratorio sin conocer Docker.
- `PREPARAR_LABORATORIO.ps1`, `ARRANCAR_LABORATORIO.ps1`, `VALIDAR_LABORATORIO.ps1`: scripts de uso diario para Windows.
- `labbox-docker.zip`: paquete local privado con la imagen Tenable.sc y utilidades. Ignorado por git.
- `labbox-utils/`: utilidades extraidas del ZIP. Ignorado por git.
- `tenablesc_internals/`: mapa interno e inspector profundo read-only de Tenable.sc.
- `../scripts/lab_docker.py`: wrapper de compatibilidad que llama a `build_lab.py`.

## Arranque Interno Tenable.sc

El servicio `tenablesc` usa `restart: unless-stopped` y un entrypoint local que
ejecuta primero el update original de Labbox. Despues instala
`tenablesc-supervisord.conf` dentro del contenedor antes de arrancar
`/running.sh`.

La configuracion local de supervisor mantiene el grupo `TenableSC` original
para Apache y Jobd, y anade arranque automatico de PostgreSQL, Redis,
WebSocket y `microservice-supervisor.sh`/`sc-asset-svc`. Esto evita que, tras
apagar y encender Docker, un scan pueda quedar `Completed` pero con
`importStatus=Error` por PostgreSQL apagado.

`doctor` sigue siendo el verificador canonico; si un servicio interno no queda
levantado, debe aparecer como incidencia y `repair --case auto` queda como
contingencia.

## Portabilidad

El laboratorio portable vive dentro de `laboratorio/`. No basta con copiar el
YAML: `docker-compose.yml` describe como arrancar contenedores. La imagen
privada de Tenable.sc viaja en `laboratorio/labbox-docker.zip`; no se transportan
backups de datos ni volumenes persistentes.

El compose declara los volumenes Docker externos `tenablescdata-ol8` y
`tenablednfcache-ol8` para que una recreacion del contenedor no pierda ni
desenganche `/opt/sc`. `build_lab.py up` los crea si no existen antes de llamar
a Docker Compose.

Paquete portable esperado:

```text
laboratorio/
  labbox-docker.zip
  .env
  labbox-utils/
```

`build_lab.py` autodetecta `laboratorio/labbox-docker.zip`. Ese ZIP contiene:

- `labbox-docker/tenablesc-labbox-image-ol8.image`
- `labbox-docker/utils/`

Para comprobar si la carpeta portable esta completa:

```powershell
python laboratorio\build_lab.py package-status
```

Para preparar un PC nuevo con el paquete portable completo:

```powershell
powershell -ExecutionPolicy Bypass -File .\laboratorio\PREPARAR_LABORATORIO.ps1
```

### Preparar Paquete En Origen

Desde el equipo donde el laboratorio funciona:

```powershell
python laboratorio\build_lab.py doctor
python laboratorio\build_lab.py validate
python laboratorio\build_lab.py package-status
```

Despues copiar la carpeta `laboratorio/` completa por el canal autorizado. Esa
carpeta puede contener licencia y credenciales locales, pero no debe contener
backups de datos.

### Preparar En Equipo Destino

Secuencia canonica en un equipo nuevo:

```powershell
powershell -ExecutionPolicy Bypass -File .\laboratorio\PREPARAR_LABORATORIO.ps1
```

## Arranque

Desde la raiz del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\laboratorio\ARRANCAR_LABORATORIO.ps1
```

Equivalente manual:

```powershell
python laboratorio\build_lab.py setup
```

Si `python` no esta en PATH dentro de Codex, usar el runtime bundled:

```powershell
& 'C:\Users\Alberto\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' laboratorio\build_lab.py doctor
```

## Diagnostico

El doctor revisa Docker, red externa, imagenes, contenedores, configuracion de
Tenable.sc, servicios internos, artefactos de Asset Lists y API Tenable.sc.

```powershell
python laboratorio\build_lab.py doctor
python laboratorio\build_lab.py doctor --json
```

El modo JSON incluye salida completa para revisar procesos, logs recientes,
filesystem, checks de `/rest/asset`, `/rest/auditFile` y pruebas de preparacion
de `/rest/analysis`.

## Tabla De Incidencias

La tabla viva esta en el comando:

```powershell
python laboratorio\build_lab.py incidents
```

Casos actuales:

| Codigo | Severidad | Sintoma | Repair |
| --- | --- | --- | --- |
| `docker_unavailable` | critical | Docker no responde | manual |
| `network_missing` | critical | Falta `docker_labbox_default-ol8` | up |
| `image_missing` | critical | Falta una imagen requerida | load-images |
| `container_missing` | critical | Falta un contenedor | up |
| `container_stopped` | critical | Contenedor parado | up |
| `tenablesc_shm_small` | critical | `/dev/shm` menor de 1 GB | recreate-with-compose |
| `tenablesc_user_invalid` | critical | Usuario `tns` no existe o no es UID/GID 250 | runtime |
| `tenablesc_locale_missing` | critical | Falta `en_US.UTF-8` | runtime |
| `tenablesc_supervisor_bad` | critical | Apache/Jobd no estan en RUNNING | runtime |
| `tenablesc_postgres_down` | critical | PostgreSQL no responde | postgres |
| `tenablesc_redis_down` | critical | Redis interno no responde | runtime |
| `tenablesc_websocket_down` | warning | WebSocket interno no esta levantado | runtime |
| `tenablesc_asset_service_down` | critical | `sc-asset-svc` no corre | runtime |
| `tenablesc_asset_artifacts_missing` | critical | Faltan `*.uuidd` de Asset Lists | assets |
| `tenablesc_api_unavailable` | critical | API no responde o no autentica | runtime |
| `tenablesc_analysis_asset_filter_bad` | critical | `/analysis` falla con `assetID` | assets |
| `tenablesc_scan_import_errors` | warning | Scan results con errores de importacion | inspect |
| `recent_known_errors` | warning | Logs recientes contienen errores conocidos | inspect |

Cuando aparezca una incidencia nueva se debe anadir al catalogo de
`build_lab.py`, documentar el sintoma aqui y crear una validacion minima.

## Reparacion

Repair automatico segun incidencias criticas detectadas:

```powershell
python laboratorio\build_lab.py repair --case auto
```

Repairs concretos:

```powershell
python laboratorio\build_lab.py repair --case runtime
python laboratorio\build_lab.py repair --case postgres
python laboratorio\build_lab.py repair --case assets --repositories 6,8,9,10
python laboratorio\build_lab.py repair --case all
```

`runtime` repara usuario `tns`, locale, supervisor, PostgreSQL, Apache, Jobd,
Redis, WebSocket y microservicios internos. `assets` ejecuta
`prepareassetsWrapper.php` para regenerar artefactos internos de Asset Lists.

## Validacion Minima

La validacion minima ejecuta doctor y despues genera el JSON de Fase 1A para
`compliance_example`.

```powershell
python laboratorio\build_lab.py validate
```

Criterios esperados:

- `doctor` sin incidencias criticas.
- Tenable.sc responde por API.
- `/analysis` acepta filtros `assetID` en los assets de prueba.
- `assetID=118` devuelve registros de compliance con `vulndetails`.
- Se genera `../outputs/compliance_example_details.json`.

## Cierre Operativo

Antes de dar el laboratorio por entregable o moverlo a otro equipo, ejecutar:

```powershell
python laboratorio\build_lab.py doctor
python laboratorio\build_lab.py validate
```

El cierre se considera correcto si `doctor` no muestra incidencias criticas y
`validate` genera `outputs/compliance_example_details.json` con registros.
Un warning `recent_known_errors` puede aceptarse si los servicios actuales estan
en OK y las lineas corresponden a errores historicos ya reparados.

## Troubleshooting

- Si `tenablesc_shm_small` aparece, recrear el contenedor con este compose; no
  basta con reiniciar servicios.
- Si `tenablesc_postgres_down` aparece tras recrear, ejecutar `repair --case postgres`.
- Si la GUI muestra Asset Lists en `Calculating` o `/analysis` falla con
  `Error loading uuid file`, ejecutar `repair --case assets`.
- Si `recent_known_errors` aparece como warning, revisar si son lineas
  historicas o errores actuales antes de tocar servicios.
