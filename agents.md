# Agents.md - Guia operativa del proyecto

## Proposito del proyecto

Construir un extractor en Python para Tenable.sc que obtenga resultados de compliance y deje los datos listos para una futura ingesta en Splunk Enterprise.

El proyecto se desarrolla en laboratorio local antes de entregar al cliente. Cualquier decision debe poder parametrizarse y moverse a produccion sin depender de rutas, credenciales o artefactos locales.

## Fuente de verdad

Este fichero es la fuente de verdad del proyecto para fases, decisiones tecnicas cerradas y contexto operativo.

Excepcion controlada: las hipotesis pendientes de validar viven solo en
`hypotheses_to_validate.md`. Desde el 2026-05-23 el registro queda acotado al
comportamiento temporal de los `.audit`, sus controles y policies. No mantener
listados paralelos de hipotesis pendientes en otros
Markdown. Cuando una hipotesis se confirme o rechace, actualizar
`hypotheses_to_validate.md` y mover solo la decision confirmada a `agents.md` o
el patron tecnico a `ESTANDARES_ADOPTADOS.md`.

README.md debe quedar como guia corta de uso.

## Mapa de documentacion

- `agents.md`: fuente de verdad para fases, alcance, decisiones tecnicas cerradas y contexto operativo del proyecto.
- `hypotheses_to_validate.md`: registro canonico de hipotesis pendientes o en validacion.
- `CHALLENGES.md`: registro de desafios de modelo, identidad y metricas; no sustituye al registro canonico de hipotesis pendientes.
- `VALIDACIONES_TENABLE.md`: registro de evidencias funcionales, resultados de API, scan results y pruebas Tenable.sc.
- `laboratorio/README.md`: guia canonica de configuracion, operacion, salud, incidencias y comandos para comprobar que el laboratorio esta listo.
- `ESTANDARES_ADOPTADOS.md`: patrones tecnicos reutilizables y reglas ya adoptadas para implementar utilidades.
- `HARNESS_DESARROLLO.md`: protocolo de trabajo controlado; no recoge estandares tecnicos ni configuraciones de laboratorio.
- `README.md`: guia corta de uso del proyecto.

## Laboratorio

La configuracion operativa del laboratorio vive en `laboratorio/README.md`. Leer ese README antes de levantar, diagnosticar, reparar, validar que esta listo, migrar, consultar salud o modificar el laboratorio.

Ese README centraliza puertos, contenedores, Docker Compose, comandos
`setup`/`package-status`/`doctor`/`repair`/`validate`, modo portable desde
imagen sin backups de datos, incidencias conocidas y preparacion del
laboratorio.
No usarlo para registrar resultados de llamadas API, scan results, consultas
`/analysis` ni evidencias funcionales una vez el laboratorio esta levantado y
sano; esas evidencias viven en `VALIDACIONES_TENABLE.md`.

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
- La unidad minima de alcance, agrupacion y salida es siempre el Asset List de Tenable.sc. Usar `id`, `name` e `ipCount`; no agrupar por el campo `tags`.
- Las consultas funcionales deben usar filtro de Asset List (`assetID` o asset math cuando aplique). El filtro directo por `ip` solo es una contingencia tecnica para Asset Lists estaticas no preparadas y la salida debe seguir quedando asociada al Asset List original.
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
- Filtro de agrupacion: Asset List mediante `assetID=<id>`.
- Fallback tecnico para Asset Lists estaticas no preparadas: leer `definedIPs` desde `/asset/{id}` y consultar con filtro `ip` solo para salvar el error interno de Asset Lists. Este fallback no cambia el modelo: el resultado se sigue agrupando bajo el Asset List original.
- Filtro audit: `auditFileID=<id>` si el dato esta disponible y validado para el entorno objetivo.
- Tool elegida para el primer JSON: `vulndetails`, porque devuelve `pluginText` y permite extraer `actual value`.
- Tool candidata alternativa: `listvuln`, si resulta ser el equivalente mas cercano a "Vulnerability Detail List" de la GUI o reduce ruido.

Nota de investigacion:

En la GUI se identifica como "Vulnerability Detail List". En API se compararon `vulndetails` y `listvuln`. `listvuln` devuelve menos datos y no incluye `pluginText`; `vulndetails` incluye `pluginText`, `pluginName`, `ip` y `lastSeen`, por lo que queda como tool de Fase 1A para los campos minimos actuales.

Decision validada el 2026-05-23: usar `vulndetails` para parsear los tags `cm`,
pero no incluir `pluginText` completo en la salida final por defecto. La salida
debe conservar campos parseados, identificadores tecnicos y un hash del
`pluginText` original para trazabilidad. El `pluginText` completo solo debe
quedar como opcion de diagnostico si se implementa.

Salida JSON objetivo:

Cada registro debe representar un resultado de compliance normalizado, no un KPI agregado.

Campos minimos actuales:

- `asset`
- `ip`
- `control_name`
- `actual_value`
- `last_observed`
- `last_observed_epoch`

Campos a incorporar antes de cerrar el contrato final de Fase 1A:

- Resultado normalizado desde `<cm:compliance-result>`.
- Audit observado desde `<cm:compliance-audit-file>`.
- Valor esperado/policy desde `<cm:compliance-policy-value>`.
- Referencias/metadatos desde `<cm:compliance-reference>`.
- Identificadores tecnicos: `pluginID`, `vulnUUID`, `hostUUID`,
  `repository.id`, severidad y `plugin_text_sha256`.

Reglas de salida:

- El JSON se agrupa por Asset List.
- Dentro de cada Asset List, los registros se ordenan por IP.
- El campo `actual_value` se extrae desde `<cm:compliance-actual-value>` dentro de `pluginText`.
- El campo `control_name` se extrae desde `<cm:compliance-check-name>` y, si no existe, se usa `pluginName`.
- El campo `last_observed` se deriva de `lastSeen`.

Validacion:

- La evidencia funcional de validacion de Fase 1A vive en
  `VALIDACIONES_TENABLE.md`.

Validaciones pendientes de Fase 1A:

- El registro de hipotesis queda centrado en el comportamiento temporal del
  `.audit` y sus controles. No mantener aqui hipotesis paralelas sobre
  `pluginText`, KPIs, Asset Lists o despliegue.

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

Decision de validacion del 2026-05-23:

El prototipo `sumseverity` no es valido como fuente unica para calcular
`passed_controls` y `failed_controls`. En Tenable.sc se observaron estados
`WARNING` (`severity.id=2`) y registros `pluginType=compliance` sin tags `cm`
parseables. La Fase 1B debe calcular buckets de estado desde
`<cm:compliance-result>` cuando este disponible y mantener buckets separados
para `WARNING`, `ERROR`, `UNKNOWN`/sin parsear u otros estados. `sumseverity`
puede seguir usandose como apoyo para conteos de severidad, no como mapeo
binario definitivo.

Decision de diseno de Fase 1B:

Para la metrica principal, todo resultado distinto de `PASSED` se agrupa en
`failed_controls`. Esto incluye `FAILED`, `WARNING`, `ERROR`, `UNKNOWN`,
registros `pluginType=compliance` sin tags `cm` parseables y cualquier otro
estado no superado. Ademas se conservan metricas separadas por estado concreto
para diagnostico y dashboards. Los controles de aplicabilidad/report y controles
con `if` anidados cuentan como un unico control principal cuando Tenable devuelve
un unico resultado final con subresultados anidados en el `pluginText`.

KPIs previstos:

- Cantidad de equipos/IPs en el asset (`ipCount`).
- Cantidad de controles superados.
- Cantidad de controles fallidos.
- Total de controles evaluados.
- Porcentaje de compliance: `passed_controls / total_controls`, donde
  `total_controls = passed_controls + failed_controls`.
- Conteos por severidad cuando aplique.
- Conteos por estado de compliance (`PASSED`, `FAILED`, `WARNING`, `ERROR`,
  `UNKNOWN`/sin parsear u otros estados observados).
- Conteo de registros sin tags `cm` parseables (`unparsed_controls`), incluidos
  tambien dentro de `failed_controls`.

Query Tenable.sc actual:

- Endpoint: `POST /rest/analysis`.
- `type`: `vuln`.
- `sourceType`: `cumulative`.
- `tool`: `sumseverity`.
- Filtros: `pluginType=compliance`, `assetID`, opcional `auditFileID`.

Nota: esta query solo queda como prototipo historico para severidades. El
calculo funcional final de KPIs no debe deducir `passed/failed` solo desde
`severity.id`.

Validaciones pendientes de Fase 1B:

- No hay hipotesis activas de Fase 1B en el registro canonico. Las dudas
  abiertas actuales viven alrededor del comportamiento temporal del `.audit`.

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
- Los recursos, mapa interno e inspector del laboratorio Tenable.sc viven bajo
  `laboratorio/` y se documentan desde `laboratorio/README.md`. Las evidencias
  funcionales y resultados de consultas viven en `VALIDACIONES_TENABLE.md`.
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
- `sourceType=individual` y los `scanResult` descargados se usan solo como evidencia de validacion o diagnostico puntual, por ejemplo para confirmar consistencia del `.audit`; no son la vista funcional por defecto del extractor.
- Herramientas relevantes: `vulndetails`, `listvuln`, `sumseverity`, `sumasset`, `sumip`, `sumid`, `vulnipdetail`, `vulnipsummary`.
- Filtros relevantes: `pluginType=compliance`, `assetID`, `auditFileID`, `repositoryIDs`, `severity`, `pluginID`, `pluginName`, `pluginText`, `xref`, `firstSeen`, `lastSeen`, `hostUUID`, `uuid`, `dnsName`, `netbiosName`.

Asset Lists:

- En Tenable.sc los "Assets" de la UI corresponden a Asset Lists.
- En este proyecto no agrupamos por el campo `tags`; agrupamos por cada Asset List y los equipos/IPs que agrupa.
- Un host/IP puede pertenecer a varios Asset Lists; por tanto, los KPIs y detalles se calculan por Asset List, no por IP suelta.
- La consulta normal contra `/analysis` debe anclarse en `assetID`. El uso de `ip` queda reservado a fallback tecnico documentado cuando el Asset List estatico falle por artefactos internos no preparados.
- Decision validada el 2026-05-23: las Asset Lists dinamicas preparadas se
  consultan por `assetID`. Si una Asset List dinamica o de combinacion falla por
  artefactos internos no preparados, se debe reparar/preparar assets o bloquear
  la extraccion de ese alcance; el fallback por `ip` solo aplica a Asset Lists
  estaticas con `definedIPs`.
- Las incidencias y repairs de Asset Lists del laboratorio viven en `laboratorio/README.md`.

Scans, scanners y policies:

- `/policy/{id}` permite recuperar la Scan Policy y sus `auditFiles`.
- Las evidencias de scans, scanners y policies viven en
  `VALIDACIONES_TENABLE.md`. Las incidencias y repairs del laboratorio viven en
  `laboratorio/README.md`.

Audit files:

- `/auditFile` lista y gestiona los `.audit` registrados en Tenable.sc.
- Campos utiles de `/auditFile`: `id`, `uuid`, `name`, `type`, `status`, `version`, `filename`, `originalFilename`, `modifiedTime`, `lastRefreshedTime`, `auditFileTemplate`, `typeFields`.
- Para modificar el contenido de un `.audit` ya registrado en Tenable.sc, la via validada es subir el nuevo fichero con `POST /file/upload` y aplicar `PATCH /auditFile/{id}` usando el `filename` devuelto por la subida. Esto conserva el `auditFile.id`, aunque cambia el `filename` interno `scfile_*`.
- Decision: para filtrar o agrupar por audit registrado, usar `auditFileID` cuando sea valido; para trazabilidad del resultado, conservar tambien el audit observado en `pluginText` como campo separado, sin asumir que es clave de union contra `/auditFile`.
- Decision validada en laboratorio: mantener el mismo `auditFile.id` permite conservar una identidad registrada estable del audit entre scans, aunque Tenable.sc guarde en cada resultado un audit observado distinto como copia `...-scfile_*`.
- Decision validada en laboratorio: para seguir el audit ejecutado basta separar
  tres niveles: `auditFileID` como identificador registrado y filtro de latest
  en `cumulative`, el prefijo estable del audit observado como trazabilidad del
  audit ejecutado, y el valor completo observado `...-scfile_*` como copia
  concreta de una ejecucion.
- Decision validada en laboratorio: `auditFileID` ayuda a filtrar/agrupar, pero no debe usarse como unica prueba de audit ejecutado porque pueden existir matches parciales por solape de plugins/checks; contrastar tambien policy y audit observado cuando haya dudas.
- Decision operativa: editar directamente en filesystem por SSH/Docker queda documentado como contingencia de laboratorio en `laboratorio/README.md`. No debe ser la via por defecto en produccion porque evita validaciones de API y puede dejar sin actualizar metadatos como `modifiedTime`, caches, checksums internos o estados usados por Tenable.sc. Usarlo solo como contingencia controlada, con export posterior por API y scan de validacion.
- Implicacion para agentes: mantener el mismo `auditFile.id` evita tener que crear un nuevo fichero de compliance y actualizar referencias por ID. Aun asi, los resultados de compliance no se reescriben historicamente; los cambios del `.audit` se reflejaran tras nuevos scans/resultados.
- Catalogo de simulacion multi-OS/rol preparado el 2026-05-24:
  `REAL_win10` (`auditFileID=1000018`, windows),
  `SIMULATE_MS_SRV_DM` (`auditFileID=1000026`, windows),
  `SIMULATE_MS_SRV_DC` (`auditFileID=1000027`, windows) y
  `OL_8` (`auditFileID=1000028`, unix). Estos audits usan la naming convention
  acordada y sirven para montar scans de simulacion con workstation, server
  Domain Member, server Domain Controller y Oracle Linux 8.
- Catalogo ligero de retest preparado el 2026-05-24:
  `light_check_win_10` (`auditFileID=1000029`, windows) y `light_check_ol_8`
  (`auditFileID=1000030`, unix). Cada audit tiene solo dos controles poco
  intensivos y sirve para relanzar pruebas rapidas de comportamiento ya
  validado.

Escenario Tenable.sc de simulacion:

- Asset Lists de alcance:
  - `compliance_windows` (`assetID=118`): Asset List para equipos Windows.
  - `compliance_linux` (`assetID=122`): Asset List para equipos Linux.
  - `compliance_devices_mix` (`assetID=121`): Asset List mixto con equipos
    Windows y Linux.
- Repositorios activos del escenario:
  - `compliance_ws` (`repositoryID=14`): resultados del audit `REAL_win10` para
    workstation Windows.
  - `compliance_srv` (`repositoryID=13`): resultados de `SIMULATE_MS_SRV_DM`,
    `SIMULATE_MS_SRV_DC` y `OL_8`; agrupa simulacion de servidores Windows y
    Linux.
  - `compliance_test` (`repositoryID=16`): resultados de pruebas rapidas y
    retests ligeros, especialmente con `light_check_win_10` y
    `light_check_ol_8`.
- Los repositorios antiguos del laboratorio quedan fuera del escenario de
  queries funcionales salvo como evidencia historica ya documentada.
- Nota de lectura: referencias anteriores a `naming_convention_win10_fullaudit`,
  `compliance_example` o repositorio `Default` (`9`) pertenecen a evidencias historicas previas al
  renombrado/catalogo actual. Para queries nuevas usar esta matriz de assets,
  repositorios y audits.
- Para KPIs y detalle, las queries deben cruzar siempre un Asset List de alcance
  con el audit registrado correspondiente y, cuando se quiera aislar origen,
  anadir `repositoryIDs` del repositorio del escenario.

Identidad de controles de compliance:

- Las hipotesis pendientes sobre comportamiento temporal del `.audit` y
  policies viven en `hypotheses_to_validate.md`.
- Decision: para extraer metricas latest por audit registrado, usar `assetID` + `auditFileID` + `sourceType=cumulative` cuando el audit este registrado en Tenable.sc. El filtro por `ip` solo puede usarse como fallback tecnico manteniendo la identidad del Asset List en la salida.
- Decision: si hay varios audits sobre el mismo host, filtrar por `auditFileID` y conservar tambien el audit observado en `<cm:compliance-audit-file>`.
- Decision validada: cambiar el nombre de un control en el campo `description`
  del `.audit` crea un control nuevo visible en Tenable.sc.
- Decision validada: modificar otros campos del control no crea un control
  nuevo en `cumulative`; actualiza el resultado del control existente tras
  ejecutar de nuevo el scan.
- Decision validada: cambiar el `type` tecnico de un control manteniendo
  exactamente el mismo `description` no crea un control nuevo en `cumulative`;
  Tenable.sc mantiene `pluginID`/`vulnUUID` y actualiza el resultado del control
  existente.
- Decision validada: si el mismo control existe dos veces en un `.audit`,
  incluso con tipos tecnicos distintos, Tenable.sc agrupa ambas ejecuciones en
  un unico control visible en `cumulative` y muestra varios resultados dentro
  del output del registro.
- Decision validada: si un control se comenta en el `.audit` para que no se
  ejecute y despues se lanza un nuevo scan, desaparece de la vista `cumulative`
  acotada por el `auditFileID` actual. En una consulta amplia por Asset List y
  `pluginType=compliance`, el resultado anterior puede seguir visible con un
  `lastSeen` antiguo; para estado latest del audit registrado, acotar tambien
  por `auditFileID`. Si se anade una ventana temporal `lastSeen`
  suficientemente reciente, el resultado antiguo queda fuera de la vista amplia
  y solo se ven los controles observados en esa ventana.
- Decision validada: comentar controles o desregistrar/borrar un `.audit`
  registrado no convierte los resultados historicos asociados en registros
  `pluginType=compliance` sin tags `cm`. Los registros compliance sin
  `<cm:compliance-result>` o `<cm:compliance-audit-file>` deben tratarse como
  registros especiales/no parseables, no como evidencia automatica de que el
  audit custom haya sido eliminado.
- Decision validada: ejecutar el mismo Asset List con el mismo `auditFileID`
  desde una policy distinta no crea una separacion visible por policy en
  `sourceType=cumulative`. Los controles mantienen continuidad por
  `pluginID`/`vulnUUID` y se actualiza `lastSeen`; `/analysis` no debe tratarse
  como una vista historica separada por policy salvo que se use otra evidencia
  o dimension confirmada.
- Comportamiento relevante: si controles de distintos ficheros `.audit` tienen
  exactamente el mismo `description`, Tenable puede generar o reutilizar el
  mismo `pluginID`. Esto puede hacer que un control aparezca aunque se este
  filtrando por un `auditFileID` concreto, por solape de plugins/checks entre
  audits, y genera confusion funcional en GUI y API.
- Decision de diseno para produccion desde cero: todos los controles custom de
  `.audit` deben llevar en `description` un namespace visible, estable y
  suficientemente unico para evitar colisiones entre audits. Patron base:
  `[<control_id>][<OS>][<OS_VERSION>][<ROLE>][<BENCHMARK_VERSION>][<LEVEL>] <titulo original>`.
  Todos los campos que forman el identificador visible van entre corchetes y no
  hay separador entre los bloques de identidad.
- `control_id` es el numero inicial del control dentro del benchmark. `OS` y
  `OS_VERSION` usan una taxonomia cerrada y reducida. Valores iniciales:
  `[MS][W10]`, `[MS][W11]`, `[MS][2016]`, `[MS][2019]`, `[MS][2022]` y
  `[OL][8]` para Oracle Linux 8. Ejemplos de uso: `[MS][2019]` y `[MS][W11]`.
  Para anadir un nuevo sistema operativo o version, definir primero el par de
  tokens y adaptar cualquier parser/validador que consuma el prefijo. No
  introducir valores libres en los `.audit`.
- `BENCHMARK_VERSION` es la version simplificada del benchmark, por ejemplo
  `[v4.0.0]` o `[v5.0.0]`. `LEVEL` es el layer/nivel de cumplimiento, por
  ejemplo `[L1]` o `[L2]`. El titulo original se conserva sin modificar respecto
  al titulo original de Tenable/CIS, incluidos sufijos como `(MS only)` cuando
  formen parte del titulo.
- `ROLE` solo tiene semantica especifica cuando aplique. Para Microsoft Server:
  `[DM]` significa domain member/member server y `[DC]` significa domain
  controller. Para OS, workstation o Linux donde el rol no aplique o no este
  definido, usar `[N/A]`; no usar placeholders como `[role]`.
- Decision: usar `<cm:compliance-reference>` como fuente principal de metadatos de negocio.
- Decision: mantener todos los metadatos de negocio en un unico campo
  `reference`; no usar una segunda linea `reference` separada para metadatos del
  cliente.
- Decision validada: `reference` es el campo preferente para enriquecer con
  datos propios porque esta pensado como pares `clave|valor`, se refleja en
  `<cm:compliance-reference>` y puede consultarse desde API y GUI.
- Decision de diseno: usar `reference` para IDs formales y trazabilidad maquina,
  no para sustituir el namespace visible cuando deban evitarse colisiones de
  `pluginID`. Los campos propios usados para enriquecer el control en
  `reference` deben empezar por `CONTROL_`. Como minimo debe incluir
  `CONTROL_IG|IGx` y `CONTROL_INTERNAL_VERSION|x`. `CONTROL_IG` conserva el IG
  heredado del benchmark; `CONTROL_INTERNAL_VERSION` registra cambios internos
  del control sin cambiar su ID funcional. El valor inicial es
  `CONTROL_INTERNAL_VERSION|0`.
- Decision de diseno: los metadatos adicionales del cliente o del proyecto se
  anaden como nuevos pares `CONTROL_<NOMBRE>|<valor>` en `reference`;
  enriquecen el control, pero no modifican su identificador unico. Las
  referencias originales de frameworks externos pueden conservar su nombre
  original, por ejemplo `800-53|...`.
- Para audits Microsoft Server, los campos enriquecidos
  `CONTROL_MS_ONLY|true|false` y `CONTROL_DC_ONLY|true|false` indican si el
  control aplica solo a Member Server o solo a Domain Controller. Estos campos
  solo aplican a audits Windows Server; si el `.audit` no es de Microsoft
  Server, no deben anadirse.
- Ejemplo Microsoft Server:
  `description : "[1.2.3][MS][2022][DM][v5.0.0][L1] Ensure 'Allow Administrator account lockout' is set to 'Enabled' (MS only)"`
  y
  `reference : "...,CONTROL_IG|IG3,CONTROL_INTERNAL_VERSION|0,CONTROL_MS_ONLY|true,CONTROL_DC_ONLY|false"`.
- Consecuencia importante: `CONTROL_INTERNAL_VERSION` no separa `pluginID`
  porque no esta en `description`. Si dos implementaciones del mismo control
  deben coexistir como controles distintos, anadir un campo visible de version
  de coexistencia en el `description`, por ejemplo `[CV1]` y `[CV2]`:
  `[<control_id>][<OS>][<OS_VERSION>][<ROLE>][<BENCHMARK_VERSION>][<LEVEL>][CVx] <titulo original>`.
  Este campo solo se usa cuando sea necesario ejecutar varias versiones vivas
  del mismo control.
- Decision: no usar `check_id`, `full_id` ni `functional_id` como clave historica unica si el contenido funcional del control puede cambiar entre versiones.
- Decision: no meter metadatos de negocio libres en `description`; usar
  `description` solo para el namespace visible de identidad funcional y el
  nombre humano del control. Para metadatos consultables de negocio, usar
  `reference`.

Preguntas activas de comportamiento temporal:

- El registro canonico de hipotesis pendientes vive en
  `hypotheses_to_validate.md`; no mantener aqui un listado paralelo.

Filtros estandar para validar comportamiento temporal:

- Usar siempre `sourceType=cumulative`.
- Usar siempre al menos un Asset List concreto (`assetID=<id>`).
- Usar siempre `pluginType=compliance`.
- Anadir `auditFileID`, `repositoryIDs`, `pluginID` u otros filtros solo como
  acotacion adicional, no como sustitutos del Asset List y `pluginType`.
- Para validar el estado actual de un audit registrado, anadir tambien
  `auditFileID=<id>`; sin ese filtro, `cumulative` puede devolver controles
  antiguos que ya no se ejecutan en el audit actual.

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

Los comandos de montaje, diagnostico, reparacion y validacion minima del
laboratorio viven en `laboratorio/README.md`. Los probes funcionales y
evidencias de API viven en `VALIDACIONES_TENABLE.md`.

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

Los desafios de modelo, identidad y metricas viven en `CHALLENGES.md`. Ese
fichero puede listar desafios superados, pendientes y aspectos no especificados,
pero no debe duplicar hipotesis tecnicas pendientes de validacion.
