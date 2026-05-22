# Agents.md - Guia operativa del proyecto

## Proposito del proyecto

Construir un extractor en Python para Tenable.sc que obtenga resultados de compliance y deje los datos listos para una futura ingesta en Splunk Enterprise.

El proyecto se desarrolla en laboratorio local antes de entregar al cliente. Cualquier decision debe poder parametrizarse y moverse a produccion sin depender de rutas, credenciales o artefactos locales.

## Fuente de verdad

Este fichero es la fuente de verdad del proyecto. No mantener otro fichero paralelo con fases, decisiones tecnicas o contexto operativo. README.md debe quedar como guia corta de uso.

## Entorno local de laboratorio

- Tenable.sc esta en Docker como `tenablesc-labbox-ol8`, publicado en `https://localhost:8443` hacia el puerto 443 del contenedor.
- Splunk esta en Docker como `splunk`, publicado en `http://localhost:8000` hacia el puerto 8000 del contenedor.
- En el `docker ps` validado no aparecia publicado el puerto HEC 8088 ni el puerto de gestion 8089 de Splunk. Fase 2 debera revisar esto antes de elegir el metodo de ingesta.

## Configuracion local

Las credenciales y URLs del laboratorio estan en `.env`. No duplicar secretos en documentacion ni codigo. Mantener `.env` fuera de git y usar `.env.example` para plantillas entregables.

Variables principales:

- `TENABLE_SC_URL`
- `TENABLE_SC_USERNAME`
- `TENABLE_SC_PASSWORD`
- `TENABLE_SC_VERIFY_SSL`
- `TENABLE_SC_AUTH_MODE`
- `TENABLE_SC_ACCESS_KEY`
- `TENABLE_SC_SECRET_KEY`
- `SPLUNK_WEB_URL`
- `SPLUNK_USERNAME`
- `SPLUNK_PASSWORD`
- `SPLUNK_HEC_URL`
- `SPLUNK_HEC_TOKEN`
- `SPLUNK_INDEX`
- `SPLUNK_SOURCETYPE_KPI`
- `SPLUNK_SOURCETYPE_DETAIL`
- `SPLUNK_LOOKUP_APP`

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
- Filtro audit: `auditFileID=<id>` si el dato esta disponible y valida en laboratorio/produccion.
- Tool elegida para el primer JSON: `vulndetails`, porque devuelve `pluginText` y permite extraer `actual value`.
- Tool candidata alternativa: `listvuln`, si resulta ser el equivalente mas cercano a "Vulnerability Detail List" de la GUI o reduce ruido.

Nota de investigacion:

En la GUI se identifica como "Vulnerability Detail List". En API se compararon `vulndetails` y `listvuln` sobre `compliance_example`. `listvuln` devuelve menos datos y no incluye `pluginText`; `vulndetails` incluye `pluginText`, `pluginName`, `ip` y `lastSeen`, por lo que queda como tool de Fase 1A para los campos minimos actuales.

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

Validacion de laboratorio:

- Asset List: `compliance_example`.
- Asset ID: `118`.
- IP definida en el asset: `192.168.128.30`.
- Registros extraidos: `77`.
- Fichero generado: `outputs/compliance_example_details.json`.
- La consulta directa por `assetID=118` falla por `Error loading uuid file into UUID list`; el extractor usa fallback por `ip` para este asset.

Decisiones pendientes de fase 1A:

- Confirmar si `pluginText` completo debe ir al JSON final o si se debe guardar version reducida/hash para controlar volumen.
- Confirmar como modelar el audit observado en `pluginText`, porque no siempre coincide con `/auditFile`.
- Confirmar estrategia ante Asset Lists dinamicas no preparadas.

Criterio de aceptacion:

- Un comando genera un JSON valido con detalles de compliance para al menos un Asset List y un audit file de laboratorio.
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

Decisiones pendientes de fase 1B:

- Confirmar si Tenable.sc permite buscar de forma fiable por audits especificos en todos los repositorios. En laboratorio `auditFileID=1000010` funciona para `assetID=0`, pero varios audits listados por `/auditFile` devuelven `AuditFile #<id> not found` al usarse como filtro de analysis.
- Confirmar si `severity.id=0` equivale siempre a superado y `severity.id>0` siempre a fallido.
- Confirmar si existen estados no binarios que deban quedar fuera del porcentaje.
- Definir exclusiones de Asset Lists tecnicas/default.

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

- Si se usa HEC, revisar publicacion/configuracion del puerto 8088 y token.
- Sourcetypes candidatos: `tenable:sc:compliance:detail` y `tenable:sc:compliance:kpi`.
- Indice de laboratorio candidato: `tenable_compliance`.
- Los lookups pueden subirse por Splunk REST/SDK, copiarse a una app Splunk o gestionarse como CSV en el filesystem del contenedor. La decision queda aplazada.

## Conocimiento tecnico Tenable.sc

API:

- Tenable.sc expone recursos REST bajo `/rest/<resource>`, con JSON como formato principal.
- Muchos recursos soportan `fields` para reducir la respuesta y `expand` para pedir datos relacionados.
- La API moderna recomienda API keys con cabecera `x-apikey` en formato `accesskey=<ACCESS_KEY>; secretkey=<SECRET_KEY>;`.
- Tambien existe login por usuario/password via `POST /rest/token`; el token devuelto se envia en `X-SecurityCenter` hasta hacer `DELETE /rest/token`.
- Para laboratorio se puede usar `TENABLE_SC_AUTH_MODE=session`. Para produccion, preferir API keys de un usuario tecnico con permisos minimos.

Analysis:

- `/analysis` es el endpoint central para consultar vulnerabilidades y compliance.
- Para vulnerabilidades/compliance se usa `type=vuln`.
- Para este proyecto se usa siempre `sourceType=cumulative` para trabajar contra el acumulado/latest de Tenable.sc.
- Herramientas relevantes: `vulndetails`, `listvuln`, `sumseverity`, `sumasset`, `sumip`, `sumid`, `vulnipdetail`, `vulnipsummary`.
- Filtros relevantes: `pluginType=compliance`, `assetID`, `auditFileID`, `repositoryIDs`, `severity`, `pluginID`, `pluginName`, `pluginText`, `xref`, `firstSeen`, `lastSeen`, `hostUUID`, `uuid`, `dnsName`, `netbiosName`.

Asset Lists:

- En Tenable.sc los "Assets" de la UI corresponden a Asset Lists.
- En este proyecto no agrupamos por el campo `tags`; agrupamos por el nombre de cada Asset List y los equipos/IPs que agrupa.
- En laboratorio el filtro `assetID=<id>` funciona para algunos assets, pero `compliance_example` requiere fallback por `ip` porque Tenable.sc no tiene preparado el fichero interno de UUIDs.

Audit files:

- `/auditFile` lista y gestiona los `.audit` registrados en Tenable.sc.
- Campos utiles de `/auditFile`: `id`, `uuid`, `name`, `type`, `status`, `version`, `filename`, `originalFilename`, `modifiedTime`, `lastRefreshedTime`, `auditFileTemplate`, `typeFields`.
- Investigacion de laboratorio 2026-05-22: `/auditFile` devuelve 14 audit files usables.
- Investigacion de laboratorio 2026-05-22: `assetID=0` con `auditFileID=1000010` devuelve 30 controles por `sumseverity` y `vulndetails`; los resultados son 11 `severity.id=0` y 19 `severity.id=3`.
- Investigacion de laboratorio 2026-05-22: en `vulndetails`, `pluginText` incluye `<cm:compliance-audit-file>`, pero ese valor no siempre coincide con `/auditFile.name` ni con `/auditFile.originalFilename`. Para `auditFileID=1000010`, el tag observado es `auditFile.zCvfBQ` aunque `/auditFile/1000010` indica `originalFilename=CAS Group 1 - 10-22-20.audit`. Para `compliance_example`, el tag observado es `CIS_Docker_Community_Edition_L1_Docker_v1.1.0.audit`, que no aparece en los audit files usables del laboratorio.
- Decision provisional: para filtrar o agrupar por audit registrado, usar `auditFileID` cuando sea valido; para trazabilidad del resultado, conservar tambien el audit observado en `pluginText` como campo separado, sin asumir que es clave de union contra `/auditFile`.
- En Fase 1B queda confirmar si `auditFileID` permite agrupar de forma fiable por audit en todos los repositorios de produccion.

Identidad de controles de compliance:

- Conversacion externa con Exa de Tenable VM 2026-05-22, no confirmada para Tenable.sc: en Tenable VM, cambiar solo el valor esperado de un control mantendria el mismo control y cambiaria el resultado; cambiar solo el nombre/descripcion del control haria que aparezca como un control nuevo; sin filtrar por audit file podrian verse dos controles logicamente equivalentes.
- Estado para Tenable.sc: pendiente de confirmar. No usar estas afirmaciones como base de implementacion hasta validarlas en laboratorio Tenable.sc o con documentacion oficial aplicable.
- Evidencia oficial relacionada pero no concluyente: la referencia de compliance checks de Nessus indica en varios tipos de checks que `description` debe ser unico y que Tenable puede usarlo para generar un plugin ID unico. Esto sugiere riesgo de que renombrar controles afecte identidad, pero no confirma la deduplicacion en Tenable.sc cumulative.
- Validacion pendiente: ejecutar contra el mismo host dos audits donde solo cambie el valor esperado de un control y comparar `pluginID`, `pluginName`, `vulnUUID`, `xref`, `severity`, `firstSeen`, `lastSeen`, `<cm:compliance-check-name>`, `<cm:compliance-result>`, `<cm:compliance-actual-value>` y `<cm:compliance-policy-value>`.
- Validacion pendiente: ejecutar contra el mismo host dos audits donde solo cambie el nombre/descripcion de un control y comprobar si cumulative muestra dos registros, reemplaza el registro o marca el anterior como mitigado.

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
python extract_compliance.py extract --asset-id 0 --audit-file-id 1000010 --pretty
```

Extraer detalles Fase 1A:

```bash
python extract_compliance.py details --asset-name compliance_example --output outputs/compliance_example_details.json --pretty
```

## Recursos oficiales

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

## Preguntas abiertas

1. Que Asset Lists de produccion son de negocio y cuales son listas tecnicas/default que debemos excluir?
2. Confirmar si `pluginText` completo debe quedar en el JSON de Fase 1A o si bastara con campos parseados y hashes para controlar volumen.
3. Definir el modelo final para representar audit registrado (`auditFileID`/`/auditFile`) y audit observado en `pluginText`, ya que no siempre coinciden.
4. Confirmar si `severity.id=0` cubre todos los PASSED y `severity.id>0` todos los FAILED, o si aparecen estados adicionales.
5. Confirmar que identidad de host necesitaremos despues: `hostUUID`, `uuid`, `ip`, `dnsName`, `netbiosName`, o combinacion por repositorio.
6. Definir donde correra el extractor final: host, contenedor dedicado, Splunk modular input o tarea programada.
7. Para Fase 2, definir presupuesto de ingesta diario o limite de licencia.
8. Para Fase 2, decidir si los lookups se mantendran en CSV dentro de una Splunk app, KV Store o carga por API.
9. Confirmar en Tenable.sc como se identifica un control de compliance cuando cambia el `.audit`: cambio de valor esperado, cambio de nombre/descripcion y ejecucion de dos audits con controles equivalentes sobre el mismo host.
