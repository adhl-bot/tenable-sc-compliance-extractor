# Laboratorio Tenable.sc + Nessus

Este directorio es la carpeta portable del laboratorio. Contiene los recursos
versionables para levantar, diagnosticar, reparar y validar el laboratorio local,
y puede contener tambien artefactos locales sensibles ignorados por git:
`labbox-docker.zip`, `.env` y `labbox-utils/`.

La fuente de verdad funcional del proyecto sigue siendo `../agents.md`. Este
README es la guia operativa y de configuracion del laboratorio. Cualquier tarea
que levante, diagnostique, repare, valide, migre o consulte el laboratorio debe
leer primero este fichero.

## Objetivo

Mantener un laboratorio reproducible con:

- Tenable.sc en Docker: `tenablesc-labbox-ol8`, publicado en `https://localhost:8443`.
- Nessus Scanner en Docker: `nessus_8835`, publicado en `https://localhost:8835`.
- Splunk en Docker: `splunk`, publicado en `http://localhost:8000`.
- Tenable IO como laboratorio secundario en `https://cloud.tenable.com/`, solo
  para pruebas de `Vulnerability Management` que no se puedan reproducir bien
  en el Docker local.
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
- `TENABLE_SC_USERNAME`
- `TENABLE_SC_PASSWORD`
- `TENABLE_SC_VERIFY_SSL`
- `TENABLE_SC_AUTH_MODE`
- `TENABLE_SC_ACCESS_KEY`
- `TENABLE_SC_SECRET_KEY`
- `TENABLE_IO_URL`
- `TENABLE_IO_ACCESS_KEY`
- `TENABLE_IO_SECRET_KEY`
- `SPLUNK_WEB_URL`
- `SPLUNK_USERNAME`
- `SPLUNK_PASSWORD`
- `SPLUNK_HEC_URL`
- `SPLUNK_HEC_TOKEN`
- `SPLUNK_INDEX`
- `SPLUNK_SOURCETYPE_KPI`
- `SPLUNK_SOURCETYPE_DETAIL`
- `SPLUNK_LOOKUP_APP`

En el `docker ps` validado el 2026-05-23 no aparecia publicado el puerto HEC
`8088` ni el puerto de gestion `8089` de Splunk. La Fase 2 debe revisar esta
configuracion antes de elegir el metodo de ingesta.

## Requisitos

- Windows con Docker Desktop y backend Linux/WSL2 operativo.
- Docker Compose v2 (`docker compose`) o Docker Compose clasico (`docker-compose`).
- Python 3.10 o superior.
- Puertos libres en el host: `8443` para Tenable.sc y `8835` para Nessus.
- RAM suficiente para Tenable.sc; se recomienda 8 GB o mas para Docker Desktop.
- `shm_size` de Tenable.sc en `1gb`. Esto es necesario para PostgreSQL e importacion de scans.
- Imagen local `tenablesc-labbox-image-ol8` disponible. Si no existe, se carga desde `laboratorio/labbox-docker.zip`.
- Imagen `tenable/nessus:latest-ubuntu` disponible localmente o descargable.
- Fichero `laboratorio/.env` con credenciales del laboratorio.

Conocimientos Docker minimos para operar este laboratorio:

- Una imagen Docker es la plantilla del contenedor. El YAML no la incluye.
- Un contenedor es una instancia arrancada desde una imagen.
- Este laboratorio no usa backups de datos para moverse entre maquinas.
- Si se borra un contenedor, se recrea desde la imagen.

## Estado Validado

Estado Docker validado el 2026-05-23 para Fase 1:

- Contenedores corriendo para simular Tenable.sc y scanner vinculado:
  `tenablesc-labbox-ol8` y `nessus_8835`.
- Tenable.sc recreado con `shm_size=1gb`.
- `doctor --json` sin incidencias criticas y con warning de logs historicos.
- `validate` completo correctamente y genero
  `../outputs/compliance_example_details.json`.
- Nessus validado en version `10.12.0` con puerto host `8835`.

El doctor debe diagnosticar Docker, red, imagenes, contenedores, `shm_size`,
usuario `tns`, locale, supervisor, PostgreSQL, Redis, WebSocket,
`sc-asset-svc`, artefactos de Asset Lists, API Tenable.sc, recursos API
principales (`repository`, `policy`, `scan`, `scanResult`, `scanner` cuando
haya permisos), filtros `/analysis`, procesos/puerto de Nessus y logs recientes.

## Artefactos

- `build_lab.py`: CLI principal para `setup`, `package-status`, `status`, `up`, `doctor`, `repair`, `load-images`, `prepare-assets`, `validate` e `incidents`.
- `docker-compose.yml`: receta Docker canonica del laboratorio.
- `.env.example`: plantilla sin secretos para crear `.env`.
- `GUIA_USUARIO.md`: guia corta para levantar y validar el laboratorio sin conocer Docker.
- `PREPARAR_LABORATORIO.ps1`, `ARRANCAR_LABORATORIO.ps1`, `VALIDAR_LABORATORIO.ps1`: scripts de uso diario para Windows.
- `labbox-docker.zip`: paquete local privado con la imagen Tenable.sc y utilidades. Ignorado por git.
- `labbox-utils/`: utilidades extraidas del ZIP. Ignorado por git.
- `tenablesc_internals/`: mapa interno e inspector profundo read-only de Tenable.sc.
- `../scripts/lab_docker.py`: wrapper de compatibilidad que llama a `build_lab.py`.

## Portabilidad

El laboratorio portable vive dentro de `laboratorio/`. No basta con copiar el
YAML: `docker-compose.yml` describe como arrancar contenedores. La imagen
privada de Tenable.sc viaja en `laboratorio/labbox-docker.zip`; no se transportan
backups de datos ni volumenes persistentes.

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

## Probes Y Consultas De Laboratorio

Probar API Tenable IO / Vulnerability Management:

```powershell
python scripts\tenable_io_probe.py --sample-size 5 --max-text-len 160
```

Probar reemplazo in-place de un `.audit` temporal en Tenable.sc:

```powershell
python scripts\tenable_sc_auditfile_patch_probe.py --mode api
python scripts\tenable_sc_auditfile_patch_probe.py --mode filesystem
```

Extraer el JSON de validacion usado por `validate`:

```powershell
python extract_compliance.py details --asset-name compliance_example --output outputs\compliance_example_details.json --pretty
```

Extraer KPI prototipo contra el audit de prueba:

```powershell
python extract_compliance.py extract --asset-id 0 --audit-file-id 1000010 --pretty
```

## Diagnostico

El doctor revisa Docker, red externa, imagenes, contenedores, configuracion de
Tenable.sc, servicios internos, artefactos de Asset Lists, API y Nessus.

```powershell
python laboratorio\build_lab.py doctor
python laboratorio\build_lab.py doctor --json
```

El modo JSON incluye salida completa para revisar procesos, logs recientes,
filesystem, resultados de `/rest/asset`, `/rest/auditFile` y pruebas de
`/rest/analysis`.

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
| `nessus_service_down` | critical | `nessus-service` o `nessusd` no corre | nessus |
| `nessus_port_closed` | critical | Puerto host `8835` cerrado | nessus |
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
python laboratorio\build_lab.py repair --case nessus
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
- Nessus escucha en `https://localhost:8835`.
- `/analysis` acepta filtros `assetID` en los assets de prueba.
- `assetID=118` devuelve `77` registros de compliance con `vulndetails`.
- Se genera `../outputs/compliance_example_details.json`.

## Evidencias Funcionales Del Laboratorio

### Fase 1A

Validacion de laboratorio para `compliance_example`:

- Asset List: `compliance_example`.
- Asset ID: `118`.
- IP definida en el asset: `192.168.128.30`.
- Registros extraidos: `77`.
- Fichero generado: `../outputs/compliance_example_details.json`.
- La consulta directa por `assetID=118` fallo historicamente por
  `Error loading uuid file into UUID list`; el extractor usa fallback por `ip`
  para este asset cuando corresponde.

### Scans, Scanners Y Policies

- La policy `[COMPLIANCE] CIS_Microsoft_Windows_10_Stand-alone_v4.0.0_L1_v1`
  tiene `policy.id=1000007`,
  `uuid=B6BD270D-F85A-4478-AE3B-E8698DAEECEE`, descripcion `Usar de plantilla`,
  y contiene el audit file `id=1000018`,
  `uuid=FE62386B-43FD-4A79-A945-25D79991601C`.
- El audit file `1000018` tiene `filename=scfile_3xqt7e`,
  `originalFilename=win_10_MODIFICADO.audit`, `type=windows`, `status=1`,
  `version=2` y `auditFileTemplate.id=-1`.
- El scan `win_10_MODIFICADO` tiene `scan.id=10`, usa la policy `1000007`,
  repositorio `Default` `id=9`, objetivo `192.168.1.138`,
  `schedule.type=template` y `timeoutAction=rollover`.
- El usuario/API actual no puede listar `/scanner` ni consultar `scanner/4`,
  pero `scanResult.id=25096` registra en `progress.scanners` el scanner `id=4`,
  `name=192.168.1.134`, con `completedChecks=27820`.
- `scanResult.id=25096` llego a figurar como `status=Completed`, pero
  `importStatus=Error`; el error indicaba falta de match del host
  `192.168.1.138` con assets existentes y fallo de PostgreSQL. La conclusion
  operativa es que un scan `Completed` no implica datos explotables en
  `cumulative`; hay que revisar tambien `importStatus` y/o confirmar datos en
  `/analysis`.
- Tras reparar PostgreSQL y reimportar `scanResult.id=25096`, el resultado paso
  a `importStatus=Finished` y `/analysis` con `repositoryIDs=9`,
  `ip=192.168.1.138` y `auditFileID=1000018` devolvio datos.
- La revision de los ultimos scan results queda en salidas ignoradas por git
  bajo `../outputs/revision_scanresults_20260523/`.

### Asset Lists

- Incidencia del 2026-05-23: `/analysis` con `assetID=14` fallaba por fichero
  UUID inexistente en `/opt/sc/orgs/1/assets`.
- Se detectaron errores de Redis, WebSocket y `sc-asset-svc`; se arrancaron los
  servicios y se recalcularon assets con `prepareassetsWrapper.php` para
  repositorios `6,8,9,10`.
- Despues de `prepare-assets --repositories 6,8,9,10`, `/analysis` con
  `assetID=14` y `assetID=24` dejo de devolver error 143; `assetID=118`
  devolvio resultados (`sumip=1`, `vulndetails=77`).

### Audit Files Y `.audit`

- `/auditFile` devolvio 14 audit files usables en la investigacion inicial.
- `assetID=0` con `auditFileID=1000010` devolvio 30 controles por
  `sumseverity` y `vulndetails`: 11 con severidad 0 y 19 con severidad 3.
- En `vulndetails`, `<cm:compliance-audit-file>` no siempre coincide con
  `/auditFile.name`, `/auditFile.filename` u `/auditFile.originalFilename`.
- Se valido que `scripts/tenable_sc_auditfile_patch_probe.py --mode api`
  conserva `auditFile.id` al parchear un audit temporal por API, aunque cambia
  el `filename` interno `scfile_*`.
- Se valido que `scripts/tenable_sc_auditfile_patch_probe.py --mode filesystem`
  conserva `auditFile.id` y `filename` al sobrescribir directamente el upload
  dentro del contenedor, manteniendo permisos `tns:tns 600`.
- Editar directamente en filesystem funciona en laboratorio como contingencia
  controlada, pero no debe ser la via por defecto en produccion porque evita
  validaciones de API y puede dejar metadatos o caches sin actualizar.

### Tenable IO Secundario

Alcance del laboratorio secundario:

- URL: `https://cloud.tenable.com/`.
- Aplicacion en alcance: `Vulnerability Management`.
- Autenticacion mediante `TENABLE_IO_ACCESS_KEY` y `TENABLE_IO_SECRET_KEY`.
- Recurso API principal: `https://developer.tenable.com/reference/navigate`.

Reglas:

- No guardar API keys reales en documentacion, codigo, tests ni ejemplos.
- No mezclar resultados Tenable IO con Tenable.sc sin campo de procedencia.
- La evidencia obtenida en Tenable IO debe marcarse como tal y no extrapolarse
  automaticamente a Tenable.sc.

Validacion del 2026-05-23:

- Autenticacion con API keys validada.
- Pruebas reproducibles con `../scripts/tenable_io_probe.py`.
- Tag dinamico recuperado: `Operating_System:Windows Workstation`, UUID
  `969a4db5-ad14-41e0-97f8-0087960b8f19`.
- Asset de laboratorio: UUID `b174d8b6-fc65-426e-a94b-cb20271a7c4c`, IP
  `192.168.1.138`, sistema operativo `Microsoft Windows 10 Pro Build 19045`.
- `GET /workbenches/assets/{asset_id}/info?all_fields=full` devolvio contadores
  de audits: total `5`, con `2 Passed`, `1 Error`, `2 Failed`.
- `POST /compliance/export` genero un export finalizado con un chunk y `5`
  findings de compliance.
- Campos utiles observados: `asset_uuid`, `plugin_id`, `plugin_name`,
  `check_name`, `status`, `state`, `audit_file`, `actual_value`,
  `expected_value`, `reference`, `compliance_full_id`,
  `compliance_functional_id`, `compliance_informational_id`, `last_observed`
  y `last_seen`.

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
