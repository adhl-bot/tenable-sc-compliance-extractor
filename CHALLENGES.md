# CHALLENGES.md - Desafios del modelo de compliance

## Proposito

Este fichero registra los desafios de diseno del modelo de datos, identidad de
controles y metricas de compliance.

No sustituye a `hypotheses_to_validate.md`. Las hipotesis pendientes de
comportamiento de Tenable.sc, `.audit`, `/analysis` o correlacion de scans
viven solo en `hypotheses_to_validate.md`.

Aqui se documenta como afectan esas decisiones al extractor y a las metricas que
se quieren obtener.

Estados usados:

- `Superado`: el desafio tiene decision adoptada y evidencia o criterio
  operativo suficiente para seguir construyendo.
- `Pendiente`: el desafio afecta al modelo o a las metricas y requiere decision
  antes de cerrar contrato final.
- `No especificado`: todavia no hay regla funcional concreta.

## Contexto de metricas

### Fase 1A - Detalles de compliance

La salida de detalle debe representar resultados normalizados de compliance, no
KPIs agregados. La consulta funcional parte de `/rest/analysis` con:

- `sourceType=cumulative`.
- `type=vuln`.
- `pluginType=compliance`.
- Un Asset List concreto mediante `assetID`.
- `auditFileID` cuando se quiera acotar al estado actual de un audit registrado.
- `tool=vulndetails` para poder parsear tags `cm` desde `pluginText`.

Campos relevantes para el modelo:

- Asset List (`asset_id`, `asset_name`, `asset_ip_count`).
- Host/IP y, cuando este disponible, identificadores tecnicos del host.
- Audit registrado (`auditFileID`) y audit observado en `pluginText`.
- Control visible (`description` / `pluginName` / `control_name`).
- Identificadores tecnicos (`pluginID`, `vulnUUID`, `hostUUID`,
  `repository.id`, severidad).
- Resultado normalizado (`PASSED`, `FAILED`, `WARNING`, `ERROR`,
  `UNKNOWN`/sin parsear u otros estados observados).
- Valores observado y esperado.
- Referencias/metadatos desde `<cm:compliance-reference>`.
- Hash del `pluginText` original para trazabilidad.

### Fase 1B - KPIs

Los KPIs previstos se calculan por Asset List y `.audit`:

- Cantidad de equipos/IPs en el Asset List (`ipCount`).
- Controles superados.
- Controles fallidos.
- Total de controles evaluados.
- Porcentaje de compliance.
- Conteos por severidad cuando aplique.
- Conteos por estado de compliance (`PASSED`, `FAILED`, `WARNING`, `ERROR`,
  `UNKNOWN`/sin parsear u otros estados observados).

Decision ya tomada: `sumseverity` no basta como fuente unica para
`passed_controls` y `failed_controls`. La formula principal de Fase 1B agrupa
todo estado distinto de `PASSED` en `failed_controls`, conserva buckets
separados por estado concreto y calcula `compliance_percent` como
`passed_controls / total_controls`.

## Desafios superados

| ID | Desafio | Decision / criterio adoptado | Impacto en metricas |
| --- | --- | --- | --- |
| CH-S01 | Fuente funcional de consulta | Usar `sourceType=cumulative` como base funcional. `individual` y scan results descargados quedan para evidencia o diagnostico. | Las metricas reflejan estado latest/acumulado, no un scan result puntual. |
| CH-S02 | Unidad minima de alcance | Agrupar siempre por Asset List. No agrupar por `tags`; el filtro por `ip` solo es fallback tecnico manteniendo el Asset List original en salida. | Los KPIs se calculan por Asset List aunque una IP pertenezca a varios Asset Lists. |
| CH-S03 | Filtros base de compliance | Toda validacion o extraccion funcional usa como minimo `assetID` y `pluginType=compliance`; `auditFileID` acota al audit actual cuando aplica. | Reduce ruido y evita mezclar controles de otros audits o ejecuciones antiguas. |
| CH-S04 | Tool de detalle | `vulndetails` es la base de Fase 1A porque expone `pluginText` y campos necesarios para parsear tags `cm`. | Permite derivar estado, valores, referencias y audit observado. |
| CH-S05 | `sumseverity` como KPI | `sumseverity` puede apoyar conteos de severidad, pero no decide passed/failed. | Los KPIs deben calcular estados desde `<cm:compliance-result>` y separar estados no binarios. |
| CH-S06 | Audit registrado vs audit observado | Usar `auditFileID` como identificador registrado/filtro de latest y conservar audit observado como trazabilidad de ejecucion. | Permite metricas por audit registrado sin perder evidencia del audit observado/copia ejecutada. |
| CH-S07 | Control eliminado/comentado | En `.audit`, "eliminar" significa comentar. Con `auditFileID`, el control comentado desaparece del latest; sin `auditFileID`, puede seguir visible en cumulative amplio. | Las metricas de estado actual deben filtrar por `auditFileID` para no contar controles retirados. |
| CH-S08 | Misma policy vs distinta policy | Cambiar de policy manteniendo Asset List y `auditFileID` no crea separacion visible en `cumulative`; actualiza continuidad del control. | Policy no debe asumirse como dimension directa del KPI latest salvo contraste adicional. |
| CH-S09 | Duplicados dentro del mismo `.audit` | Dos controles con el mismo `description` se agrupan como un solo control visible y muestran varias ejecuciones en el output. | Para contar versiones coexistentes como controles separados, el `description` debe diferenciarse. |
| CH-S10 | Colisiones entre audits | El mismo `description` en distintos `.audit` puede provocar solape de `pluginID` incluso filtrando por `auditFileID`. | El namespace visible en `description` es necesario para KPIs por audit sin contaminacion visual/API. |
| CH-S11 | Namespace de control | Patron base: `[control_id][OS][OS_VERSION][ROLE][BENCHMARK_VERSION][LEVEL] <titulo original>`. Todos los campos de identidad visible van entre corchetes y sin separador entre bloques. | Permite derivar dimensiones estables: control, OS, version de OS, rol, version benchmark y level. |
| CH-S12 | Version interna vs coexistencia | `CONTROL_INTERNAL_VERSION|0` vive en `reference` y no cambia identidad. Si dos versiones deben coexistir, se anade `[CVx]` al `description`. | Evita romper continuidad por cambios internos y permite separar controles solo cuando conviven. |
| CH-S13 | Enriquecimiento de negocio | `reference` es el campo preferente para metadatos `clave|valor`; los campos propios de enriquecimiento deben empezar por `CONTROL_`. | Los metadatos del cliente enriquecen busquedas y dashboards sin alterar identidad Tenable ni contaminar `description`. |
| CH-S14 | Taxonomia OS/version y ROLE | OS/version usa pares cerrados iniciales: `[MS][W10]`, `[MS][W11]`, `[MS][2016]`, `[MS][2019]`, `[MS][2022]`, `[OL][8]`. Role: `[DM]`, `[DC]`, `[N/A]`. | Evita variantes libres que rompan agregaciones por plataforma, version o rol. |
| CH-S15 | Multi-audit con OS no compatible | En la prueba Windows 10 + audit Windows 11, Tenable no ignoro el audit incompatible; genero `WARNING` de aplicabilidad. | Las metricas deben prever warnings de aplicabilidad, no solo passed/failed. |
| CH-S16 | Formula principal de compliance | `compliance_percent = passed_controls / total_controls`. Todo estado distinto de `PASSED`, incluidos `FAILED`, `WARNING`, `ERROR`, `UNKNOWN` y registros sin `cm` parseable, suma en `failed_controls`. | El KPI principal es binario para reporting ejecutivo, pero conserva metricas separadas por estado concreto. |
| CH-S17 | Unidad de conteo de controles compuestos | Los checks de aplicabilidad/report y controles con `if` anidados cuentan como un unico control principal cuando Tenable devuelve un unico resultado final con subresultados anidados. | Evita inflar totales por subchecks tecnicos dentro del mismo `pluginText`. |

## Desafios pendientes

| ID | Desafio | Por que importa | Estado actual |
| --- | --- | --- | --- |
| CH-P01 | Identidad historica fina vs familia de control | El token `[BENCHMARK_VERSION]`, por ejemplo `[v5.0.0]`, identifica una instancia concreta de benchmark, pero no resuelve por si solo la continuidad historica entre versiones CIS. | Pendiente definir claves derivadas, por ejemplo `control_instance_id` y `control_family_id`. |
| CH-P04 | Multiples resultados dentro de un mismo `pluginText` | Un control duplicado puede aparecer como un unico registro con varios resultados en el output. | Pendiente decidir si Fase 1A explota subresultados como detalle adicional; Fase 1B ya cuenta un unico control principal. |
| CH-P05 | Uso de `[CVx]` en agregados | `[CVx]` separa controles coexistentes, pero las metricas pueden necesitar verlos separados o agrupados por familia. | Pendiente definir si `CVx` entra siempre en la clave de KPI o solo como dimension opcional. |
| CH-P06 | Ciclo de vida de `[CVx]` | No esta definido si `[CVx]` se mantiene tras desaparecer la version antigua o si se retira cuando deja de haber coexistencia. | No especificado. |
| CH-P07 | Versiones de benchmark y comparabilidad | Si el benchmark sube de `v4.0.0` a `v5.0.0`, el ID visible cambia aunque el `control_id` parezca equivalente. | Pendiente decidir si habra mapping entre versiones para tendencias historicas. |
| CH-P08 | Cambios de titulo de Tenable/CIS | El titulo se conserva como lo da Tenable, pero cambios menores pueden cambiar el `description` completo. | Pendiente confirmar que los parsers y metricas usaran los tokens, no el texto completo, como identidad logica. |
| CH-P10 | Confianza del `auditFileID` | Se han visto matches parciales por solape de plugins/checks. `auditFileID` filtra, pero no siempre prueba por si solo el audit ejecutado. | Pendiente automatizar nivel de confianza usando policy o audit observado cuando haya dudas. |
| CH-P11 | Repositorios | La salida contempla `repository.id`, pero no esta cerrada la semantica si un mismo Asset List/audit aparece en varios repositorios. | No especificado si repository sera dimension obligatoria de KPI. |
| CH-P12 | Hosts esperados vs hosts con resultado | `ipCount` del Asset List no siempre equivale a equipos escaneados con compliance efectivo. | Pendiente definir metricas de cobertura: hosts esperados, hosts escaneados, hosts con compliance y hosts sin resultado. |
| CH-P13 | Agregacion entre Asset Lists | Un host puede pertenecer a varios Asset Lists. Esto es correcto por alcance, pero puede duplicar conteos en agregados globales. | No especificado como calcular metricas globales sin doble conteo. |
| CH-P14 | Gobierno de `reference` cliente | Se acepta anadir campos de cliente en `reference` con prefijo `CONTROL_`, pero falta taxonomia detallada de nombres, obligatoriedad, valores vacios o colisiones mas alla de los campos ya definidos. | Parcialmente especificado. |
| CH-P15 | Validacion automatica del prefijo | El estandar esta definido, pero aun no hay parser/validador que rechace `.audit` con OS, OS_VERSION, ROLE, BENCHMARK_VERSION, LEVEL o `reference` mal formados. | Pendiente implementar si se convierte en requisito de calidad. |
| CH-P16 | Salida Splunk final | El proyecto prepara JSON para Splunk, pero Fase 2 no esta activa. | No especificado sourcetype final, indice, lookups, dashboards ni busquedas agregadas. |

## Escenarios donde el planteamiento funciona

- Produccion empieza desde cero y no hace falta conservar continuidad con
  controles antiguos sin namespace.
- Las metricas principales son latest por Asset List y audit registrado.
- Se quiere comparar compliance por OS, rol, version de benchmark, level, IG y
  estado del control.
- Los cambios internos del control no deben crear un nuevo control visible.
- Dos versiones del mismo control solo conviven excepcionalmente y se separan
  con `[CVx]`.
- Los metadatos del cliente enriquecen el analisis, pero no forman parte del ID
  unico del control.

## Escenarios donde el planteamiento no basta por si solo

- Tendencias historicas largas entre versiones de benchmark distintas sin un
  mapping de familias de control.
- Comparativas globales entre Asset Lists con hosts compartidos, si se requiere
  evitar doble conteo.
- Dashboards que necesiten decidir formulas adicionales al KPI principal, por
  ejemplo vistas estrictas o diagnosticas por estado concreto.
- Situaciones donde dos variantes del mismo control conviven pero no se usa
  `[CVx]` en el `description`.
- Cambios upstream de titulo que alteren el `description` completo si el parser
  no separa tokens de identidad y texto humano.

## No queda especificado

- Como explotar varios subresultados `cm` dentro de un unico `pluginText` en la
  salida de detalle de Fase 1A.
- Clave final de continuidad historica entre benchmarks: `control_instance_id`,
  `control_family_id` u otra.
- Reglas de lifecycle de `[CVx]`.
- Taxonomia formal completa de campos cliente en `reference`, mas alla del
  prefijo obligatorio `CONTROL_` y los campos ya definidos.
- Proceso de alta de nuevos tokens OS/ROLE mas alla de la lista inicial.
- Reglas de agregacion global evitando doble conteo entre Asset Lists.
- Contrato final de salida para Splunk y lookups necesarios.
