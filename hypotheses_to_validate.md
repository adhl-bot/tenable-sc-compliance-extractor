# Hipotesis por validar

Este fichero es el registro canonico de hipotesis pendientes de validacion.

Alcance activo: comportamiento temporal de los `.audit`, sus controles y los
scan results de compliance en Tenable.sc.

Quedan descartadas de este registro las hipotesis generales sobre volumen de
`pluginText`, KPIs, severidad, Asset Lists, despliegue o seleccion de alcance.
Si alguna decision confirmada de esas areas sigue siendo util, debe vivir en
`agents.md` o `ESTANDARES_ADOPTADOS.md`, no aqui.

## Decisiones ya comprobadas

Estas decisiones no son hipotesis activas:

- Cambiar el nombre de un control en el campo `description` del `.audit` crea
  un control nuevo visible en Tenable.sc.
- Modificar otros campos funcionales del control no crea un control nuevo en
  `cumulative`; el resultado se actualiza tras ejecutar de nuevo el scan.
- Si el mismo control existe dos veces dentro de un `.audit`, Tenable.sc agrupa
  ambas ejecuciones en un unico control visible en `cumulative` y muestra los
  dos resultados dentro del output del registro.
- Si un control se comenta en el `.audit` para que no se ejecute, desaparece
  de la vista `cumulative` acotada por el `auditFileID` actual tras el nuevo
  scan. En una consulta amplia por Asset List y `pluginType=compliance`, puede
  seguir apareciendo el resultado anterior con un `lastSeen` antiguo. Si se
  anade una ventana temporal `lastSeen` suficientemente reciente, el resultado
  antiguo queda fuera y solo se ven los controles observados en esa ventana.
- Ejecutar el mismo Asset List con el mismo `auditFileID` desde una policy
  distinta no crea una separacion visible por policy en `cumulative`; los
  controles mantienen continuidad y se actualiza `lastSeen`.
- El campo `reference` es el lugar preferente para enriquecer controles con
  metadatos propios: esta pensado como pares `clave|valor`, aparece en
  `<cm:compliance-reference>` y puede consultarse desde API y GUI.
- Para trazabilidad se debe conservar tanto el audit registrado cuando exista
  (`auditFileID`) como el audit observado en el resultado
  (`<cm:compliance-audit-file>` o valor equivalente del scan result).
- Para seguir el audit ejecutado en el modelo funcional basta distinguir:
  `auditFileID` como identificador registrado/filtro de `cumulative`, el prefijo
  estable del audit observado como trazabilidad del audit ejecutado, y el valor
  completo observado `...-scfile_*` como copia concreta de una ejecucion.
- Si controles de distintos `.audit` tienen exactamente el mismo `description`,
  Tenable puede generar/reutilizar el mismo `pluginID`; ese solape puede hacer
  que un control aparezca incluso al filtrar por un `auditFileID` concreto.
- Para evitar colisiones en audits custom de produccion desde cero, el
  `description` debe seguir el patron
  `[control_id][OS][OS_VERSION][ROLE][BENCHMARK_VERSION][LEVEL] <titulo original>`.
  Todos los campos de identidad van entre corchetes, sin separador entre bloques,
  y el titulo se conserva como lo da Tenable.
- `reference` debe incluir como minimo `CONTROL_IG|IGx` y
  `CONTROL_INTERNAL_VERSION|x`. La version interna del control queda en
  `reference` para trazabilidad evolutiva, pero no modifica el identificador
  unico del control.
- Los campos propios de enriquecimiento en `reference` deben empezar por
  `CONTROL_`. En audits Microsoft Server, `CONTROL_MS_ONLY|true|false` y
  `CONTROL_DC_ONLY|true|false` indican aplicabilidad exclusiva a Member Server o
  Domain Controller; fuera de audits Microsoft Server no aplican.
- Si dos versiones vivas del mismo control deben coexistir, anadir un campo
  visible `[CVx]` al `description`; usarlo solo para coexistencia real, no para
  cada cambio interno.
- Cambiar el `type` tecnico de un control manteniendo exactamente el mismo
  `description` no separa la identidad del control en `cumulative`; Tenable.sc
  mantiene `pluginID` y `vulnUUID` y actualiza el resultado del control
  existente.
- Si dos bloques vivos del mismo `.audit` tienen exactamente el mismo
  `description`, incluso con tipos tecnicos distintos, Tenable.sc los colapsa
  en un unico control visible en `cumulative` y puede incluir varios resultados
  dentro del mismo `pluginText`.

## Filtros estandar de validacion

Toda validacion de comportamiento temporal debe consultar `sourceType=cumulative`
con, como minimo:

- Un Asset List concreto mediante `assetID=<id>`.
- `pluginType=compliance`.

Filtros adicionales como `auditFileID`, `repositoryIDs`, `pluginID` o
`scanResultID` pueden anadirse segun la prueba, pero no sustituyen a esos dos
filtros base. Si se usa fallback por `ip` para una Asset List estatica, debe
quedar documentado como contingencia y la evidencia debe seguir asociada al
Asset List original.

Cuando la prueba busque el estado actual de un audit registrado, usar tambien
`auditFileID=<id>`; sin ese filtro, `cumulative` puede mezclar resultados
actuales del audit con resultados anteriores de controles que ya no se ejecutan.

## Estados permitidos

- `Pendiente`: aun no hay prueba suficiente.
- `En validacion`: hay pruebas parciales, pero falta cerrar la conclusion.
- `Confirmada`: probada en laboratorio Tenable.sc o fuente oficial aplicable.
- `Rechazada`: probada y descartada.

## H01 - Identificador temporal del audit ejecutado

- Estado: `Confirmada`.
- Alcance: Tenable.sc / Asset List / `.audit` / `cumulative`.
- Conclusion: para el extractor no se necesita una unica clave historica global.
  El modelo funcional queda cubierto con tres campos:
  `auditFileID` como identificador registrado y filtro de estado latest en
  `cumulative`, el prefijo estable del audit observado como trazabilidad del
  audit ejecutado, y el valor completo observado `...-scfile_*` como copia
  concreta de la ejecucion.
- Regla de consulta: cuando se busca estado actual en `cumulative`, usar
  `assetID`, `pluginType=compliance` y `auditFileID`. Esto es especialmente
  importante para descartar controles que ya no pertenecen al audit actual,
  porque sin `auditFileID` pueden seguir apareciendo resultados antiguos del
  mismo Asset List.
- Evidencia: en las ejecuciones revisadas de `auditFileID=1000018`, el audit
  observado mantuvo el prefijo estable
  `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3`, mientras cambiaron las copias
  concretas observadas, por ejemplo
  `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-710000-scfile_mNLUhm`,
  `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-710148-scfile_NuLiaJ`,
  `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-712797-scfile_YbCvtM` y
  `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-712839-scfile_YbCvtM`.

## H02 - Mismo asset y mismo audit con distinta policy

- Estado: `Confirmada`.
- Alcance: Tenable.sc / policy / `.audit` / `cumulative`.
- Conclusion: al escanear el mismo Asset List con el mismo `auditFileID` desde
  una policy distinta, Tenable.sc no crea una separacion visible por policy en
  `sourceType=cumulative`; mantiene continuidad de los controles por
  `pluginID`/`vulnUUID` y actualiza `lastSeen` con el scan mas reciente.
- Evidencia: validacion del 2026-05-23 con Asset List `compliance_example`
  (`assetID=118`). El scan `win_10_MODIFICADO` (`scan.id=10`) usa policy
  `1000007` y el scan `SEGUNDA POLICY win_10_MODIFICADO` (`scan.id=11`) usa
  policy `1000008`; ambas policies referencian el mismo `auditFileID=1000018`.
  El scanResult nuevo `25106` termino `Completed`, `importStatus=Finished`,
  `finishTime=1779572409` e `importFinish=1779572414`.
- Resultado `cumulative`: con `assetID=118`, `pluginType=compliance` y
  `auditFileID=1000018`, `/analysis` devolvio `totalRecords=2`, los mismos
  `pluginID=1000200` y `pluginID=1003713`. Ambos conservaron `firstSeen`
  `1779529623` y los mismos `vulnUUID`
  (`8786418d-e666-40b6-988a-1cc385145696` y
  `c5238ddc-5366-4f6d-9e9b-30cbfef26136`), mientras `lastSeen` avanzo a
  `1779572412` y el audit observado cambio a
  `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-712839-scfile_YbCvtM`.
- Matiz: los registros devueltos por `/analysis` no exponen la policy como
  dimension directa en esta prueba; la relacion con policy se confirmo mediante
  `/scan` y `/policy`.

## H03 - Control comentado/eliminado del audit

- Estado: `Confirmada`.
- Alcance: Tenable.sc / `.audit` / `cumulative`.
- Conclusion: cuando un control se comenta en el `.audit` y se ejecuta un nuevo
  scan, el control desaparece de la vista `cumulative` acotada por el
  `auditFileID` actual. Sin acotar por `auditFileID`, el control puede seguir
  visible en `cumulative` por Asset List como resultado anterior con `lastSeen`
  antiguo. Si se usa un filtro temporal `lastSeen` posterior al ultimo scan en
  que se observo el control, tambien desaparece de la vista amplia sin
  `auditFileID`.
- Caso de prueba activo: comentar el control
  `1.1.1 [IG1](L1) Ensure 'Enforce password history' is set to '24 or more password(s)'`
  (`pluginID=1003368`) del audit usado por `compliance_example [118]`.
- Evidencia: validacion del 2026-05-23 contra `sourceType=cumulative`,
  `assetID=118`, `pluginType=compliance` y `auditFileID=1000018`.
  La consulta acotada al audit devolvio `totalRecords=2`
  (`pluginID=1000200` y `pluginID=1003713`) y la consulta adicional con
  `pluginID=1003368` devolvio `totalRecords=0`. La consulta amplia por
  `assetID=118` y `pluginType=compliance` siguio devolviendo `pluginID=1003368`,
  pero con `lastSeen=1779569492` y audit observado anterior
  `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-712756-scfile_36ejBo`; los controles
  del nuevo scan quedaron con `lastSeen=1779571204` y audit observado
  `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-712797-scfile_YbCvtM`.
- Evidencia adicional del 2026-05-24: tras comentar el control
  `[1.1.2][MS][W10][N/A][v4.0.0][L1] Ensure 'Maximum password age' is set to '365 or fewer days, but not 0'`
  y ejecutar `scan.id=10` (`scanResult=25125`), el filtro amplio
  `assetID=118` + `pluginType=compliance` seguia mostrando el control antiguo
  con `lastSeen=1779636188` y `1779635112`. Al anadir la ventana temporal
  `lastSeen=1779641000-1779642000`, posterior al nuevo scan, el control
  `pluginID=1005137` dejo de aparecer incluso sin `auditFileID`.

## H06 - Policy con varios audits y OS no compatible

- Estado: `Confirmada`.
- Alcance: Tenable.sc / policy / varios `.audit` / OS del host /
  `cumulative`.
- Conclusion: en la prueba con una policy multi-audit contra un host Windows 10,
  Tenable.sc ejecuto/importo la policy correctamente y el audit de OS no
  compatible no se ignoro silenciosamente: dejo un resultado de aplicabilidad
  `WARNING` en `cumulative` bajo su propio `auditFileID`.
- Evidencia: el 2026-05-24 el scan `win_10_MODIFICADO` (`scan.id=10`) uso la
  policy `[COMPLIANCE] multiple_audits` con `auditFileID=1000018` Windows 10 y
  `auditFileID=1000022` Windows 11 contra `assetID=118`
  (`192.168.1.138`, Windows 10). El `scanResult=25109` termino `Completed` e
  `importStatus=Finished`.
- Resultado `cumulative`: con `assetID=118`, `pluginType=compliance` y
  `auditFileID=1000018` se obtuvieron `3` registros del audit Windows 10. Con
  `auditFileID=1000022` se obtuvo `1` registro `WARNING` (`pluginID=1003953`)
  por fallo de aplicabilidad de Windows 11 sobre el host Windows 10.
- Matiz: esta confirmacion aplica al caso probado Windows 10 + Windows 11. Para
  otras familias de OS o audits sin checks de aplicabilidad equivalentes, repetir
  la validacion antes de extrapolar.

## H07 - Registros compliance sin `cm` por audit no resoluble

- Estado: `Rechazada`.
- Alcance: Tenable.sc / `.audit` / `cumulative` / registros
  `pluginType=compliance` sin tags `cm` parseables.
- Hipotesis rechazada: algunos registros `pluginType=compliance` sin
  `<cm:compliance-result>` ni `<cm:compliance-audit-file>` podrian proceder de
  resultados huerfanos cuyo audit registrado ya no existe o ya no es resoluble
  desde `/auditFile`.
- Evidencia que la hace plausible: en
  `outputs/compliance_hypotheses_validation_asset2_allaudits_20260523.json`,
  generado el `2026-05-23T20:42:32Z`, la consulta amplia
  `assetID=2`, `pluginType=compliance`, `sourceType=cumulative` y
  `auditFileID=null` devolvio `3:<missing> = 2`. Ambos registros eran
  `pluginID=33929` (`PCI DSS compliance`), `severity.id=3`, IP
  `52.41.100.107`, repositorio `9`, `lastSeen=1762463548`
  (`2025-11-06T21:12:28Z`), sin `compliance_results`, sin `audit_files` y sin
  referencias parseadas.
- Evidencia que la limita: los tests confirmados hasta ahora solo demuestran que
  un control comentado/eliminado puede seguir apareciendo en `cumulative` amplio
  si no se filtra por `auditFileID`; no demuestran que borrar o perder el audit
  registrado elimine los tags `cm` del resultado. En la prueba H03, el resultado
  antiguo seguia teniendo audit observado anterior. Ademas, `pluginID=33929`
  aparece en artefactos de scan result revisados como plugin de familia
  `Policy Compliance`, no necesariamente como control de un `.audit` custom.
- Evidencia adicional del 2026-05-24: se comento el control
  `[1.1.2][MS][W10][N/A][v4.0.0][L1] Ensure 'Maximum password age' is set to '365 or fewer days, but not 0'`
  en `naming_convention_win10_fullaudit.audit`, se aplico sobre
  `auditFileID=1000018` y se lanzo `scan.id=10`, generando
  `scanResult=25125` con `status=Completed` e `importStatus=Finished`. Tras el
  scan, `assetID=118` + `auditFileID=1000018` acotado al repositorio `Default`
  (`9`) paso de `332` a `331` registros y el control `pluginID=1005137` dejo
  de aparecer con ese filtro. Sin `auditFileID`, el mismo control siguio
  visible como resultado antiguo en el repositorio `Default` (`9`), conservando
  `<cm:compliance-result>` y
  `<cm:compliance-audit-file>`. En las consultas revisadas de `assetID=118` no
  aparecieron registros sin ambos tags `cm`.
- Evidencia final del 2026-05-24: se desregistro el audit temporal
  `auditFileID=1000023` (`win_10_MODIFICADO_v2_segundo_compliance`,
  `filename=scfile_UZrH6U`), que tenia resultados historicos para
  `assetID=118`. Antes del borrado, `assetID=118` +
  `auditFileID=1000023` devolvia `5` registros (`pluginID=1003714`,
  `1004311` y `1004312`), todos con `<cm:compliance-result>` y
  `<cm:compliance-audit-file>`. Tras `DELETE /auditFile/1000023`,
  `GET /auditFile/1000023` fallo con `error_code=145`, `/analysis` filtrando
  por `auditFileID=1000023` fallo con `error_code=143`, y la policy
  `1000009` dejo de listar ese audit. Sin embargo, la consulta amplia
  `assetID=118` + `pluginType=compliance` siguio devolviendo esos `5`
  resultados historicos, conservando sus tags `cm` parseables.
- Conclusion: ni comentar controles ni desregistrar un audit file registrado
  convierte los resultados historicos en registros sin tags `cm`. Los registros
  `pluginType=compliance` sin tags `cm` observados en otros datos, por ejemplo
  `pluginID=33929` (`PCI DSS compliance`), deben tratarse como registros
  especiales/no parseables de familia compliance, no como evidencia de que un
  audit custom borrado pierda los tags `cm`.

## H08 - Cambio de tipo tecnico manteniendo `description`

- Estado: `Confirmada`.
- Alcance: Tenable.sc / `.audit` / identidad de control / `cumulative`.
- Hipotesis confirmada: cambiar el `type` tecnico de un control sin cambiar su
  `description` no crea un control nuevo visible en `cumulative`; la identidad
  del control queda asociada al mismo `pluginID`/`vulnUUID`.
- Evidencia: el 2026-05-24 se modifico el control
  `[1.1.1][MS][W10][N/A][v4.0.0][L1][CV1] Ensure 'Enforce password history' is set to '24 or more password(s)'`
  en `naming_convention_win10_fullaudit.audit`. El bloque paso de
  `type: PASSWORD_POLICY` con `password_policy: ENFORCE_PASSWORD_HISTORY` a
  `type: AUDIT_POWERSHELL`, usando `powershell_args:
  "get-wmiobject win32_operatingsystem"` y `check_type: CHECK_REGEX`. La
  sintaxis se contrasto con `NessusComplianceChecksReference.pdf`, seccion
  Windows `AUDIT_POWERSHELL`, usando un cmdlet `get-` y evitando aliases.
- Resultado: tras aplicar el fichero sobre `auditFileID=1000018` y lanzar
  `scan.id=17`, `scanResult=25127` termino `Completed` e
  `importStatus=Finished`. En `/analysis` con `assetID=118`,
  `repositoryIDs=9`, `pluginType=compliance` y `auditFileID=1000018`, el
  control mantuvo `pluginID=1005136`, `vulnUUID=d05adfed-812a-4618-9284-0a679183dd10`
  y `firstSeen=1779635112`; solo avanzo `lastSeen=1779647247`. El resultado
  cambio a `ERROR` y el `policy_value` observado paso a
  `AUDIT_POWERSHELL value_data: '.*Windows.*'`.
- Conclusion: para el modelo funcional del extractor, el `type` tecnico del
  check no debe usarse como separador de identidad historica cuando el
  `description` se mantiene exactamente igual. La identidad visible del control
  depende del `description` en este caso probado.

## H09 - Duplicado vivo con mismo `description` en el mismo `.audit`

- Estado: `Confirmada`.
- Alcance: Tenable.sc / `.audit` / duplicados / `cumulative`.
- Hipotesis confirmada: si el mismo `.audit` contiene dos bloques vivos con
  exactamente el mismo `description`, Tenable.sc no crea dos controles visibles
  separados en `cumulative`; agrupa ambos bajo el mismo control.
- Evidencia: despues de H08 se copio de nuevo el bloque original
  `PASSWORD_POLICY` del control `[1.1.1]` sin cambiar su `description`, dejando
  en `naming_convention_win10_fullaudit.audit` dos bloques vivos con la misma
  identidad visible: uno `AUDIT_POWERSHELL` y otro `PASSWORD_POLICY`. El fichero
  se aplico sobre `auditFileID=1000018` y se lanzo `scan.id=17`, generando
  `scanResult=25128` con `status=Completed`, `importStatus=Finished`,
  `completedChecks=27822`, `finishTime=1779647815` e
  `importFinish=1779647822`.
- Resultado: `/analysis` con `assetID=118`, `repositoryIDs=9`,
  `pluginType=compliance` y `auditFileID=1000018` mantuvo
  `totalRecords=331` y devolvio un unico registro para esa `description`, no
  dos. El registro mantuvo `pluginID=1005136`,
  `vulnUUID=d05adfed-812a-4618-9284-0a679183dd10` y
  `firstSeen=1779635112`, con `lastSeen=1779647819`. Dentro del mismo
  `pluginText` aparecieron dos resultados: `ERROR` para el bloque
  `AUDIT_POWERSHELL` y `FAILED` para el bloque `PASSWORD_POLICY`; tambien se
  observaron dos `actual_value`, vacio y `0`.
- Conclusion: dos controles con la misma `description` dentro del mismo `.audit`
  comparten un unico ID logico visible en Tenable.sc. El extractor debe tratar
  ese caso como un unico registro de control con posible output compuesto, no
  como dos controles independientes. Para coexistencia real de dos versiones,
  hay que diferenciar la `description`, por ejemplo con `[CV1]` y `[CV2]`.

## Hipotesis valorativas no funcionales

Estas hipotesis no forman parte del contrato funcional actual del extractor y
no deben implementarse como comportamiento final salvo decision explicita
posterior. Sirven para razonar sobre trazabilidad fina y posibles diagnosticos.

### HV01 - Segunda parte del audit observado desde cumulative

- Tipo: valorativa / no implementar en funcionamiento final.
- Idea: desde `sourceType=cumulative` con `tool=vulndetails`, el campo
  `<cm:compliance-audit-file>` permite parsear el audit observado completo, por
  ejemplo `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-712839-scfile_YbCvtM`. De ese
  valor se podria separar el prefijo estable, la segunda parte numerica
  (`712839`) y el sufijo interno `scfile_*`.
- Valor potencial: podria servir como trazabilidad diagnostica mas fina de la
  copia observada del audit en el estado latest que devuelve `cumulative`.
- Cuestionamiento: `cumulative` no es historico de ejecuciones. Solo permite
  ver la copia observada asociada a los controles vivos en esa vista; no permite
  reconstruir todas las versiones/copias anteriores si no se guardan snapshots o
  se consultan scanResults historicos.
- Riesgo de interpretacion: la segunda parte numerica puede ser un identificador
  interno de copia/ejecucion y no una version funcional del `.audit`. No debe
  usarse como clave de negocio ni como prueba unica de modificacion del fichero.
- Regla actual: conservar el audit observado completo como trazabilidad cuando
  se extraiga de `cumulative`, pero no anadir la segunda parte como campo
  funcional ni usarla para filtrar, agrupar o decidir continuidad del control.
