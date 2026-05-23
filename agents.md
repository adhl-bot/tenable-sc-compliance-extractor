# Agents.md - Guia operativa del proyecto

## Proposito del proyecto

Construir un extractor en Python para Tenable.sc que obtenga resultados de compliance y deje los datos listos para una futura ingesta en Splunk Enterprise.

El proyecto se desarrolla en laboratorio local antes de entregar al cliente. Cualquier decision debe poder parametrizarse y moverse a produccion sin depender de rutas, credenciales o artefactos locales.

## Fuente de verdad

Este fichero es la fuente de verdad del proyecto para fases, decisiones tecnicas cerradas y contexto operativo.

Excepcion controlada: las hipotesis pendientes de validar, especialmente las referentes al comportamiento de Tenable.sc, Tenable IO, Nessus, `.audit`, `/analysis`, identidad de controles, estados de compliance, Asset Lists o correlacion de scans, viven solo en `hypotheses_to_validate.md`. No mantener listados paralelos de hipotesis pendientes en otros Markdown. Cuando una hipotesis se confirme o rechace, actualizar `hypotheses_to_validate.md` y mover solo la decision confirmada a `agents.md` o el patron tecnico a `ESTANDARES_ADOPTADOS.md`.

README.md debe quedar como guia corta de uso.

## Mapa de documentacion

- `agents.md`: fuente de verdad para fases, alcance, decisiones tecnicas cerradas y contexto operativo del proyecto.
- `hypotheses_to_validate.md`: registro canonico de hipotesis pendientes o en validacion.
- `laboratorio/README.md`: guia canonica de configuracion, operacion, evidencias, incidencias y comandos del laboratorio.
- `ESTANDARES_ADOPTADOS.md`: patrones tecnicos reutilizables y reglas ya adoptadas para implementar utilidades.
- `HARNESS_DESARROLLO.md`: protocolo de trabajo controlado; no recoge estandares tecnicos ni configuraciones de laboratorio.
- `README.md`: guia corta de uso del proyecto.

## Laboratorio

La configuracion operativa del laboratorio vive en `laboratorio/README.md`. Leer ese README antes de levantar, diagnosticar, reparar, validar, migrar, consultar o modificar el laboratorio.

Ese README centraliza puertos, contenedores, Docker Compose, comandos `setup`/`package-status`/`doctor`/`repair`/`validate`, modo portable desde imagen sin backups de datos, incidencias conocidas, Splunk de laboratorio, Tenable IO secundario y evidencias obtenidas en laboratorio. No duplicar esos detalles en ficheros Markdown de raiz ni mantener ficheros-puntero paralelos.

Para uso por personas no tecnicas, la guia canonica es `laboratorio/GUIA_USUARIO.md`.

## Configuracion local

Las credenciales y URLs locales estan en `.env`. No duplicar secretos en documentacion ni codigo. Mantener `.env` fuera de git y usar `.env.example` para plantillas entregables.

Las variables y configuraciones especificas del laboratorio se documentan en `laboratorio/README.md`.

## Principios de trabajo

- Mantener `.env` fuera de git. Usar `.env.example` para documentar variables.
- No guardar credenciales reales en codigo, README, tests ni ejemplos versionables.
- Priorizar consultas Tenable.sc reproducibles y documentadas.
- Trabajar primero con JSON estable; Splunk se aborda despues.
- Evitar ingesta innecesaria: detalles completos solo cuando sean necesarios para fase 1A; KPIs agregados para fase 1B.
- Agrupar por Asset Lists de Tenable.sc usando `id`, `name` y `ipCount`. No agrupar por el campo `tags`.
- Usar siempre `sourceType=cumulative` para trabajar contra el acumulado/latest de Tenable.sc.
- Mantener campos de salida estables para que Splunk pueda consumirlos luego sin rehacer el extractor.

## Regla de avance entre fases

No se pasa a una fase, subfase o funcionalidad nueva hasta que la fase, subfase o funcionalidad actual este validada, comprobada y cerrada.

Para considerar algo cerrado debe cumplirse:

- La funcionalidad se ha probado contra el laboratorio o con tests representativos.
- Los resultados se han revisado y tienen sentido funcional.
- Los errores conocidos quedan documentados.
- La documentacion de uso queda actualizada.
- El usuario confirma que se da por validado o acepta avanzar explicitamente.

Si aparece una duda que pueda cambiar el modelo de datos, la query de Tenable.sc o el futuro formato de ingesta, se bloquea el avance y se resuelve antes de construir encima.

Cuando la validacion use el laboratorio, seguir la configuracion y el protocolo de `laboratorio/README.md`.

## Fases del proyecto

### Fase 1 - Tenable.sc

La fase 1 cubre solo extraccion y normalizacion de datos desde Tenable.sc. No incluye ingesta en Splunk.

#### Fase 1A - Extraccion de detalles de compliance

Objetivo:

Extraer detalles de resultados de compliance desde Tenable.sc y escribirlos en un fichero JSON que posteriormente pueda ser ingerido por Splunk.

Contrato funcional:

- El script recibe parametros de entrada que representan la intencion de consulta.
- Con esos parametros construye un query compatible con `/rest/analysis`.
- Ejecuta la consulta contra Tenable.sc.
- Normaliza la respuesta a JSON.
- Guarda un fichero JSON en disco.

Inputs previstos:

- Asset List por `asset_id` o filtro por nombre.
- Audit file por `audit_file_id` o filtro por nombre, si se confirma que aplica.
- Repositorio, si necesitamos acotar por `repositoryIDs`.
- Ventana o paginacion: `offset`, `limit`, `pages`.
- Filtros opcionales de compliance: severidad, plugin, policy, benchmark, xref.

Query Tenable.sc validado inicialmente:

- Endpoint: `POST /rest/analysis`.
- `type`: `vuln`.
- `sourceType`: `cumulative`.
- Filtro fijo: `pluginType=compliance`.
- Filtro de agrupacion: Asset List mediante `assetID=<id>` inicialmente.
- Fallback para Asset Lists estaticas no preparadas: leer `definedIPs` desde `/asset/{id}` y consultar con filtro `ip`.
- Filtro audit: `auditFileID=<id>` si el dato esta disponible y validado para el entorno objetivo.
- Tool elegida para el primer JSON: `vulndetails`, porque devuelve `pluginText` y permite extraer `actual value`.
- Tool candidata alternativa: `listvuln`, si resulta ser el equivalente mas cercano a "Vulnerability Detail List" de la GUI o reduce ruido.

Nota de investigacion:

En la GUI se identifica como "Vulnerability Detail List". En API se compararon `vulndetails` y `listvuln`. `listvuln` devuelve menos datos y no incluye `pluginText`; `vulndetails` incluye `pluginText`, `pluginName`, `ip` y `lastSeen`, por lo que queda como tool de Fase 1A para los campos minimos actuales.

Salida JSON objetivo:

Cada registro debe representar un resultado de compliance normalizado, no un KPI agregado.

Campos minimos actuales:

- `asset`
- `ip`
- `control_name`
- `actual_value`
- `last_observed`
- `last_observed_epoch`

Reglas de salida:

- El JSON se agrupa por Asset List.
- Dentro de cada Asset List, los registros se ordenan por IP.
- El campo `actual_value` se extrae desde `<cm:compliance-actual-value>` dentro de `pluginText`.
- El campo `control_name` se extrae desde `<cm:compliance-check-name>` y, si no existe, se usa `pluginName`.
- El campo `last_observed` se deriva de `lastSeen`.

Validacion:

- La evidencia de validacion en laboratorio de Fase 1A vive en `laboratorio/README.md`.

Hipotesis pendientes de fase 1A:

- Las hipotesis pendientes sobre volumen de `pluginText`, audit observado y Asset Lists dinamicas/no preparadas viven en `hypotheses_to_validate.md`.

Criterio de aceptacion:

- Un comando genera un JSON valido con detalles de compliance para al menos un Asset List y un audit file del entorno validado.
- El JSON conserva suficiente informacion para reconstruir host, control, resultado, audit y asset.
- La paginacion funciona sin perder resultados.
- Se documenta que tool API se usara definitivamente.

#### Fase 1B - Extraccion de KPIs

Objetivo:

Extraer KPIs de compliance agrupados por Asset List y por fichero `.audit`.

Estado:

Hay un prototipo inicial implementado con `tool=sumseverity`.

KPIs previstos:

- Cantidad de equipos/IPs en el asset (`ipCount`).
- Cantidad de controles superados.
- Cantidad de controles fallidos.
- Total de controles evaluados.
- Porcentaje de compliance: `controles_superados / total_controles`.
- Conteos por severidad cuando aplique.

Query Tenable.sc actual:

- Endpoint: `POST /rest/analysis`.
- `type`: `vuln`.
- `sourceType`: `cumulative`.
- `tool`: `sumseverity`.
- Filtros: `pluginType=compliance`, `assetID`, opcional `auditFileID`.

Hipotesis pendientes de fase 1B:

- Las hipotesis pendientes sobre fiabilidad de `auditFileID`, mapeo de severidad, estados no binarios y exclusiones de Asset Lists viven en `hypotheses_to_validate.md`.

Criterio de aceptacion:

- Un comando genera JSON/CSV con KPIs por Asset List y audit file.
- Los resultados cuadran con consultas manuales de la GUI.
- Los errores de assets/audits sin datos se registran sin romper la ejecucion completa.

### Fase 2 - Splunk

Declarada, no activa todavia.

Objetivo futuro:

- Ingesta de datos generados por fase 1.
- Definicion de sourcetypes, indice, HEC o metodo alternativo.
- Lookups para enriquecer datos y minimizar ingesta.
- Dashboards y busquedas.

No hacer en esta fase aun:

- No configurar HEC.
- No crear dashboards.
- No crear apps Splunk definitivas.
- No optimizar volumen hasta validar primero el JSON de Tenable.sc.

Notas futuras:

- Si se usa HEC, revisar primero la configuracion del Splunk de laboratorio en `laboratorio/README.md`.
- Sourcetypes candidatos: `tenable:sc:compliance:detail` y `tenable:sc:compliance:kpi`.
- El indice final se definira en Fase 2.
- Los lookups pueden subirse por Splunk REST/SDK, copiarse a una app Splunk o gestionarse como CSV en el filesystem del contenedor. La decision queda aplazada.

## Conocimiento tecnico Tenable.sc

Recursos locales:

- `NessusComplianceChecksReference.pdf` queda como fuente local de consulta cuando haya que revisar la estructura, campos y sintaxis de ficheros `.audit`. Usarlo especialmente para confirmar el significado de campos como `description`, `reference`, `check_type`, valores esperados y formato de checks antes de tomar decisiones de modelo.
- Los recursos, mapa interno, inspector y evidencias del laboratorio Tenable.sc viven bajo `laboratorio/` y se documentan desde `laboratorio/README.md`.
- No automatizar el extractor contra rutas internas de `/opt/sc`; la extraccion funcional debe seguir usando la API REST documentada de Tenable.sc.

API:

- Tenable.sc expone recursos REST bajo `/rest/<resource>`, con JSON como formato principal.
- Muchos recursos soportan `fields` para reducir la respuesta y `expand` para pedir datos relacionados.
- La API moderna recomienda API keys con cabecera `x-apikey` en formato `accesskey=<ACCESS_KEY>; secretkey=<SECRET_KEY>;`.
- Tambien existe login por usuario/password via `POST /rest/token`; el token devuelto se envia en `X-SecurityCenter` hasta hacer `DELETE /rest/token`.
- Para produccion, preferir API keys de un usuario tecnico con permisos minimos. Los modos locales se documentan en `laboratorio/README.md`.

Analysis:

- `/analysis` es el endpoint central para consultar vulnerabilidades y compliance.
- Para vulnerabilidades/compliance se usa `type=vuln`.
- Para este proyecto se usa siempre `sourceType=cumulative` para trabajar contra el acumulado/latest de Tenable.sc.
- Herramientas relevantes: `vulndetails`, `listvuln`, `sumseverity`, `sumasset`, `sumip`, `sumid`, `vulnipdetail`, `vulnipsummary`.
- Filtros relevantes: `pluginType=compliance`, `assetID`, `auditFileID`, `repositoryIDs`, `severity`, `pluginID`, `pluginName`, `pluginText`, `xref`, `firstSeen`, `lastSeen`, `hostUUID`, `uuid`, `dnsName`, `netbiosName`.

Asset Lists:

- En Tenable.sc los "Assets" de la UI corresponden a Asset Lists.
- En este proyecto no agrupamos por el campo `tags`; agrupamos por el nombre de cada Asset List y los equipos/IPs que agrupa.
- Las incidencias y repairs de Asset Lists del laboratorio viven en `laboratorio/README.md`.

Scans, scanners y policies:

- `/policy/{id}` permite recuperar la Scan Policy y sus `auditFiles`.
- `/scanResult/import` importa resultados de scan desde un fichero previamente subido, identificado por `filename`, contra un repositorio destino. La documentacion de Tenable.sc permite subir resultados activos o de agentes en `.nessus` o `.zip` con un unico `.nessus`.
- Para resultados importados desde Nessus externo o agentes, el repositorio debe ser compatible con el tipo de resultado. Tenable advierte que importar resultados de agente en repositorios no-agent puede omitir vulnerabilidades sin IP, e importar resultados no-agent en repositorios agent puede omitir vulnerabilidades sin Agent ID.
- Las evidencias de scans, scanners, policies, repairs e importaciones del laboratorio viven en `laboratorio/README.md`.
- Decision provisional para scans ejecutados fuera de Tenable.sc e importados despues: no asumir que el resultado queda enlazado de forma fiable al `policy.id` o `auditFile.id` registrado en Tenable.sc. Mantener en la salida tanto el audit registrado cuando exista (`auditFileID`) como el audit observado en el resultado (`<cm:compliance-audit-file>` / nombre del `.nessus`), y validar por repositorio/tipo de resultado antes de usar `auditFileID` como clave unica.

Audit files:

- `/auditFile` lista y gestiona los `.audit` registrados en Tenable.sc.
- Campos utiles de `/auditFile`: `id`, `uuid`, `name`, `type`, `status`, `version`, `filename`, `originalFilename`, `modifiedTime`, `lastRefreshedTime`, `auditFileTemplate`, `typeFields`.
- Para modificar el contenido de un `.audit` ya registrado en Tenable.sc, la via validada es subir el nuevo fichero con `POST /file/upload` y aplicar `PATCH /auditFile/{id}` usando el `filename` devuelto por la subida. Esto conserva el `auditFile.id`, aunque cambia el `filename` interno `scfile_*`.
- Decision provisional: para filtrar o agrupar por audit registrado, usar `auditFileID` cuando sea valido; para trazabilidad del resultado, conservar tambien el audit observado en `pluginText` como campo separado, sin asumir que es clave de union contra `/auditFile`.
- Las hipotesis pendientes sobre fiabilidad de `auditFileID` y correlacion con el audit observado viven en `hypotheses_to_validate.md`.
- Decision operativa: editar directamente en filesystem por SSH/Docker queda documentado como contingencia de laboratorio en `laboratorio/README.md`. No debe ser la via por defecto en produccion porque evita validaciones de API y puede dejar sin actualizar metadatos como `modifiedTime`, caches, checksums internos o estados usados por Tenable.sc. Usarlo solo como contingencia controlada, con export posterior por API y scan de validacion.
- Implicacion para agentes: mantener el mismo `auditFile.id` evita tener que crear un nuevo fichero de compliance y actualizar referencias por ID. Aun asi, los resultados de compliance no se reescriben historicamente; los cambios del `.audit` se reflejaran tras nuevos scans/resultados.

Identidad de controles de compliance:

- Las hipotesis pendientes sobre identidad de controles, cambios de `.audit`, duplicados/colapso y uso de `reference` como metadato viven en `hypotheses_to_validate.md`.
- Decision: para extraer metricas latest por audit registrado, usar `assetID`/IP + `auditFileID` + `sourceType=cumulative` cuando el audit este registrado en Tenable.sc.
- Decision: si hay varios audits sobre el mismo host, filtrar por `auditFileID` y conservar tambien el audit observado en `<cm:compliance-audit-file>`.
- Decision: usar `<cm:compliance-reference>` como fuente principal de metadatos de negocio.
- Decision: mantener todos los metadatos de negocio en un unico campo `reference`; no usar una segunda linea `reference` separada para metadatos del cliente.
- Decision: no usar `check_id`, `full_id` ni `functional_id` como clave historica unica si el contenido funcional del control puede cambiar entre versiones.
- Decision: no meter metadatos de negocio en `description` si se quiere mantener continuidad historica; usar `reference`.

## Conocimiento tecnico Tenable IO

El alcance, configuracion y evidencias del laboratorio secundario Tenable IO viven en `laboratorio/README.md`.

Reglas de uso:

- No guardar API keys reales en documentacion, codigo, tests ni ejemplos versionables.
- No mezclar resultados de Tenable IO con resultados de Tenable.sc sin campo de procedencia claro.
- Las conclusiones obtenidas en Tenable IO sobre `.audit`, scans o identidad de controles deben registrarse como evidencia de Tenable IO hasta confirmar si aplican tambien a Tenable.sc.
- Las hipotesis pendientes sobre `reference` e identidad de controles en Tenable IO viven en `hypotheses_to_validate.md`.

## Comandos actuales

Listar Asset Lists:

```bash
python extract_compliance.py assets --pretty
```

Listar audit files:

```bash
python extract_compliance.py audit-files --pretty
```

Extraer KPI prototipo:

```bash
python extract_compliance.py extract --asset-id <asset_id> --audit-file-id <audit_file_id> --pretty
```

Extraer detalles Fase 1A:

```bash
python extract_compliance.py details --asset-name <asset_name> --output outputs/compliance_details.json --pretty
```

Los comandos y probes relacionados con laboratorio viven en `laboratorio/README.md`.

## Recursos oficiales

- Recurso local para estructura de `.audit`: `NessusComplianceChecksReference.pdf`
- Tenable Developer API Explorer: https://developer.tenable.com/reference/navigate
- pyTenable: https://pytenable.readthedocs.io/en/stable/
- pyTenable Tenable.sc wrapper: https://pytenable.readthedocs.io/en/stable/api/sc/index.html
- pyTenable Analysis: https://pytenable.readthedocs.io/en/stable/api/sc/analysis.html
- pyTenable Asset Lists: https://pytenable.readthedocs.io/en/stable/api/sc/asset_lists.html
- Tenable.sc API: https://docs.tenable.com/security-center/api/index.htm
- Tenable.sc Analysis: https://docs.tenable.com/security-center/api/Analysis.htm
- Tenable.sc Query: https://docs.tenable.com/security-center/api/Query.htm
- Tenable.sc Asset: https://docs.tenable.com/security-center/api/Asset.htm
- Tenable.sc AuditFile: https://docs.tenable.com/security-center/api/AuditFile.htm
- Tenable.sc Scan Result: https://docs.tenable.com/security-center/api/Scan-Result.htm
- Tenable.sc Token: https://docs.tenable.com/security-center/api/Token.htm
- Splunk HEC setup: https://help.splunk.com/en/splunk-enterprise/get-data-in/get-started-with-getting-data-in/9.3/get-data-with-http-event-collector/set-up-and-use-http-event-collector-in-splunk-web
- Splunk HEC event format: https://help.splunk.com/en/splunk-enterprise/get-data-in/get-started-with-getting-data-in/9.1/get-data-with-http-event-collector/format-events-for-http-event-collector
- Splunk HEC endpoints: https://help.splunk.com/en/data-management/get-data-in/get-data-into-splunk-enterprise/9.0/get-data-with-http-event-collector/http-event-collector-rest-api-endpoints

## Hipotesis y preguntas abiertas

Las hipotesis pendientes de validar viven en `hypotheses_to_validate.md`. No mantener aqui otro listado paralelo.

Las preguntas abiertas que no sean hipotesis de comportamiento deben documentarse en la fase o seccion operativa correspondiente cuando se conviertan en una decision accionable.
