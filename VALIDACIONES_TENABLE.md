# VALIDACIONES_TENABLE.md - Evidencias Tenable

## Proposito

Este fichero registra resultados de llamadas API, scan results, consultas
`/analysis`, pruebas contra `.audit` y evidencias funcionales obtenidas durante
la investigacion.

No es la guia del laboratorio. La guia para montar, diagnosticar, reparar y
validar que el laboratorio esta listo vive en `laboratorio/README.md`.

No sustituye a `hypotheses_to_validate.md`. Las hipotesis pendientes o en
validacion viven alli. Este documento conserva evidencias y resultados que
soportan decisiones ya adoptadas o pruebas concretas.

## Reglas

- Registrar aqui resultados de API, scan results, consultas `/analysis`,
  comparativas GUI/API y salidas de validacion funcional de Tenable.sc.
- No documentar aqui como levantar o reparar el laboratorio; eso vive en
  `laboratorio/README.md`.
- No guardar credenciales reales.
- Si una evidencia cierra una hipotesis, actualizar tambien
  `hypotheses_to_validate.md` y mover la decision confirmada a `agents.md` o
  `ESTANDARES_ADOPTADOS.md` cuando corresponda.
- Si una evidencia afecta a desafios de modelo o metricas, actualizar
  `CHALLENGES.md`.

## Comandos de validacion funcional

Probar reemplazo in-place de un `.audit` temporal en Tenable.sc:

```powershell
python scripts\tenable_sc_auditfile_patch_probe.py --mode api
python scripts\tenable_sc_auditfile_patch_probe.py --mode filesystem
```

Extraer el JSON de validacion funcional usado por `validate`:

```powershell
python extract_compliance.py details --asset-name compliance_example --output outputs\compliance_example_details.json --pretty
```

Extraer KPI prototipo contra el audit de prueba:

```powershell
python extract_compliance.py extract --asset-id 0 --audit-file-id 1000010 --pretty
```

## Fase 1A - Detalles de compliance

Validacion funcional para `compliance_example`:

- Asset List: `compliance_example`.
- Asset ID: `118`.
- IP definida en el asset en la revision indicada: `192.168.1.138`.
- Vista funcional por defecto: `/analysis` con `sourceType=cumulative` y filtro
  `assetID=118`.
- Revision cumulative del 2026-05-23 con `auditFileID=1000018`: `3` registros
  (`2` fallidos/High y `1` pasado/Info), todos bajo el audit observado mas
  reciente `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-710148-scfile_NuLiaJ`.
- Fichero generado: `outputs/compliance_example_details.json`.
- La consulta directa por `assetID=118` fallo historicamente por
  `Error loading uuid file into UUID list`; el extractor usa fallback por `ip`
  solo como contingencia tecnica y mantiene la salida agrupada por el Asset
  List original.

## Scans, scanners y policies

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
- El usuario/API usado no podia listar `/scanner` ni consultar `scanner/4`, pero
  `scanResult.id=25096` registro en `progress.scanners` el scanner `id=4`,
  `name=192.168.1.134`, con `completedChecks=27820`.
- `scanResult.id=25096` llego a figurar como `status=Completed`, pero
  `importStatus=Error`; el error indicaba falta de match del host
  `192.168.1.138` con assets existentes y fallo de PostgreSQL. Conclusion:
  un scan `Completed` no implica datos explotables en `cumulative`; hay que
  revisar tambien `importStatus` y/o confirmar datos en `/analysis`.
- Tras reparar PostgreSQL y reimportar `scanResult.id=25096`, el resultado paso
  a `importStatus=Finished` y `/analysis` con `repositoryIDs=9`,
  `ip=192.168.1.138` y `auditFileID=1000018` devolvio datos como diagnostico.
  La consulta funcional del extractor debe hacerse por Asset List, por ejemplo
  `assetID=118` cuando el host este incluido en `compliance_example`.
- La revision de los ultimos scan results quedo en salidas ignoradas por git
  bajo `outputs/revision_scanresults_20260523/`.

## Asset Lists

- Incidencia del 2026-05-23: `/analysis` con `assetID=14` fallaba por fichero
  UUID inexistente en `/opt/sc/orgs/1/assets`.
- Se detectaron errores de Redis, WebSocket y `sc-asset-svc`; se arrancaron los
  servicios y se recalcularon assets con `prepareassetsWrapper.php` para
  repositorios `6,8,9,10`.
- Despues de `prepare-assets --repositories 6,8,9,10`, `/analysis` con
  `assetID=14` y `assetID=24` dejo de devolver error 143; `assetID=118`
  devolvio resultados (`sumip=1`; en la revision cumulative con
  `auditFileID=1000018`, `vulndetails=3`).

## Audit files y `.audit`

- `/auditFile` devolvio 14 audit files usables en la investigacion inicial.
- `assetID=0` con `auditFileID=1000010` devolvio 30 controles por
  `sumseverity` y `vulndetails`: 11 con severidad 0 y 19 con severidad 3.
- En las evidencias locales actuales si existen registros `pluginType=compliance`
  sin `<cm:compliance-result>` parseable. En
  `outputs/compliance_hypotheses_validation_asset2_allaudits_20260523.json`,
  la matriz `severity_to_compliance_result` contiene `3:<missing> = 2`; ambos
  registros corresponden a `pluginID=33929` (`PCI DSS compliance`) con
  `compliance_results` vacio. Tambien aparecen 3 casos en
  `outputs/validation_hypotheses_details_20260523.json`.
- En `vulndetails`, `<cm:compliance-audit-file>` no siempre coincide con
  `/auditFile.name`, `/auditFile.filename` u `/auditFile.originalFilename`.

### Duplicado de control en `.audit`

Validacion del 2026-05-23:

- Consulta: `/analysis` con `sourceType=cumulative`, `tool=vulndetails`,
  `assetID=118` (`compliance_example`) y `pluginType=compliance`.
- Resultado: `totalRecords=3`.
- El control `pluginID=1000200` aparecio como un unico registro con
  `vulnUUID=8786418d-e666-40b6-988a-1cc385145696`.
- Dentro de `pluginText` contenia dos `<cm:compliance-result>` (`PASSED` y
  `FAILED`) y dos `<cm:compliance-actual-value>` (`0` y `0`).
- Conclusion: si el mismo control existe dos veces dentro del `.audit`,
  Tenable.sc lo agrupa en un solo control visible en `cumulative` y muestra las
  dos ejecuciones en el output.

### Control comentado/eliminado en `.audit`

Validacion del 2026-05-23:

- Se comento el control
  `1.1.1 [IG1](L1) Ensure 'Enforce password history' is set to '24 or more password(s)'`
  (`pluginID=1003368`) y se ejecuto un nuevo scan.
- `/analysis` con `sourceType=cumulative`, `tool=vulndetails`, `assetID=118`,
  `pluginType=compliance` y `auditFileID=1000018` devolvio `totalRecords=2`
  (`pluginID=1000200` y `pluginID=1003713`).
- La misma consulta acotada ademas por `pluginID=1003368` devolvio
  `totalRecords=0`.
- Sin filtro `auditFileID`, `pluginID=1003368` seguia apareciendo en el Asset
  List, pero con `lastSeen=1779569492` y audit observado anterior
  `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-712756-scfile_36ejBo`.
- Los controles del nuevo scan tenian `lastSeen=1779571204` y audit observado
  `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-712797-scfile_YbCvtM`.
- Conclusion: para validar el estado actual de un audit registrado hay que
  anadir `auditFileID`; el cumulative amplio puede conservar resultados
  anteriores de controles que ya no se ejecutan.

### Mismo Asset List y audit con distinta policy

Validacion del 2026-05-23:

- El scan `win_10_MODIFICADO` (`scan.id=10`) usa la policy `1000007`
  (`[COMPLIANCE] CIS_Microsoft_Windows_10_Stand-alone_v4.0.0_L1_v1`).
- El scan `SEGUNDA POLICY win_10_MODIFICADO` (`scan.id=11`) usa la policy
  `1000008` (`SEGUNDA_POLICY_MISMO_AUDIT`).
- Ambas policies referencian el mismo `auditFileID=1000018` y el mismo Asset
  List `compliance_example` (`assetID=118`).
- El scanResult nuevo `25106` termino `Completed`, `importStatus=Finished`,
  `finishTime=1779572409` e `importFinish=1779572414`.
- En `/analysis` `sourceType=cumulative` con `assetID=118`,
  `pluginType=compliance` y `auditFileID=1000018` se obtuvieron
  `totalRecords=2`, los mismos `pluginID=1000200` y `pluginID=1003713`.
- Ambos mantuvieron `firstSeen=1779529623` y los mismos `vulnUUID`
  (`8786418d-e666-40b6-988a-1cc385145696` y
  `c5238ddc-5366-4f6d-9e9b-30cbfef26136`), mientras `lastSeen` avanzo a
  `1779572412` y el audit observado cambio a
  `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-712839-scfile_YbCvtM`.
- Conclusion: cambiar de policy manteniendo Asset List y `auditFileID` no crea
  separacion visible por policy en `cumulative`; actualiza la continuidad del
  control. Los registros de `/analysis` no expusieron policy como dimension
  directa en esta prueba, por lo que la relacion con policy se verifico mediante
  `/scan` y `/policy`.

### Namespace unico en `description`

Validacion del 2026-05-24:

- Se actualizo `win_10_MODIFICADO_v2.audit` y se aplico por API sobre
  `auditFileID=1000018`, conservando el ID registrado y cambiando el filename
  interno a `scfile_nBNift`.
- El scan `win_10_MODIFICADO` (`scan.id=10`) genero `scanResult=25109`,
  `status=Completed`, `importStatus=Finished`, `completedChecks=27822`,
  `finishTime=1779583817` e `importFinish=1779583824`.
- En `cumulative`, con `assetID=118`, `pluginType=compliance` y
  `auditFileID=1000018`, se obtuvieron `totalRecords=3`.
- Registros observados:
  - Report `0.0.0 [WIN_10][4.0.0][ALL][IG1][L1]...`
    (`pluginID=1003962`).
  - Control `1.1.1 [WIN_10][4.0.0][STANDALONE][I1][IG1][L1]...`
    (`pluginID=1003960`, `PASSED`).
  - Control `1.1.1 [WIN_10][4.0.0][STANDALONE][I2][IG1][L1]...`
    (`pluginID=1003961`, `FAILED`).
- Conclusion: incluir el namespace visible y un diferenciador en `description`
  evita el colapso de dos controles activos que antes compartian nombre y
  genera `pluginID`/`vulnUUID` separados.
- Nota: esta validacion uso el formato anterior al estandar final adoptado. El
  estandar vigente queda en `ESTANDARES_ADOPTADOS.md`.

### Policy con varios `.audit` y OS no compatible

Validacion del 2026-05-24:

- En la misma ejecucion, la policy `[COMPLIANCE] multiple_audits` incluia el
  audit Windows 10 `auditFileID=1000018` y el audit Windows 11
  `auditFileID=1000022`.
- Contra el host Windows 10, `cumulative` con `assetID=118`,
  `pluginType=compliance` y `auditFileID=1000022` devolvio `totalRecords=1`.
- El registro fue un resultado `WARNING` (`pluginID=1003953`) indicando que
  Windows 11 no aplica (`Windows 11 is installed` fallo contra el build
  `19045`).
- Conclusion: en esta prueba, un audit de OS no compatible dentro de una policy
  multi-audit no se ignoro silenciosamente; dejo un resultado de aplicabilidad
  en `cumulative`.

### Revision de scan results y audit observado

Revision del 2026-05-23:

- Ultimos scanResults revisados: `25099`, `25100`, `25101`, `25102` y `25103`.
- Los scanResults Windows con datos de compliance (`25099`, `25100`, `25101` y
  `25103`) mantuvieron `auditFileID=1000018` como audit registrado/ejecutado.
- El audit observado en `pluginText` cambio en cada ejecucion como copia
  `...-scfile_*`.
- El scanResult `25102` era WAS `Partial/No Results` y no tenia audit file
  aplicable.
- En esas ejecuciones, el audit observado de `auditFileID=1000018` mantuvo el
  prefijo estable `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3`, mientras cambiaron el
  token numerico y el sufijo `scfile_*`, por ejemplo
  `...-710000-scfile_mNLUhm`, `...-710148-scfile_NuLiaJ`,
  `...-712797-scfile_YbCvtM` y `...-712839-scfile_YbCvtM`.
- Conclusion: para el modelo funcional usar `auditFileID` como filtro de latest
  en `cumulative`, conservar el prefijo observado como trazabilidad del audit
  ejecutado y conservar el valor completo `...-scfile_*` como evidencia de la
  ejecucion concreta.
- En esa revision, `/analysis` individual tuvo full match con
  `auditFileID=1000018`. En `25101` y `25103` tambien aparecio match parcial
  con `auditFileID=1000015`, atribuible a solape de plugins/checks y no a audit
  ejecutado.
- Conclusion: `auditFileID` sirve para filtrar/agrupar cuando el audit
  registrado es resoluble, pero la prueba de audit ejecutado debe contrastarse
  con policy y/o audit observado cuando haya dudas.

### Parcheo de audit files

- Se valido que `scripts/tenable_sc_auditfile_patch_probe.py --mode api`
  conserva `auditFile.id` al parchear un audit temporal por API, aunque cambia
  el `filename` interno `scfile_*`.
- Se valido que `scripts/tenable_sc_auditfile_patch_probe.py --mode filesystem`
  conserva `auditFile.id` y `filename` al sobrescribir directamente el upload
  dentro del contenedor, manteniendo permisos `tns:tns 600`.
- Editar directamente en filesystem funciona en laboratorio como contingencia
  controlada, pero no debe ser la via por defecto en produccion porque evita
  validaciones de API y puede dejar metadatos o caches sin actualizar.

### Prueba `win10_fullaudit.audit` + segundo audit CV2

Validacion del 2026-05-24:

- Se reemplazo por API el contenido de `auditFileID=1000018` con
  `win10_fullaudit.audit`, conservando el ID registrado. El audit file quedo
  con `name=win10_fullaudit.audit`, `originalFilename=win10_fullaudit.audit` y
  `filename=scfile_xkqXyD`.
- El segundo audit de la prueba se mantuvo como `auditFileID=1000023`
  (`win_10_MODIFICADO_v2_segundo_compliance`, `filename=scfile_UZrH6U`).
- La policy `[COMPLIANCE] multiple_audits` (`policyID=1000009`) quedo asociada
  a `auditFileID=1000018` y `auditFileID=1000023`.
- Se lanzo el scan `win_10_MODIFICADO` (`scan.id=10`) y genero
  `scanResult=25110`, `status=Completed`, `importStatus=Finished`,
  `completedChecks=27822`, `finishTime=1779591447` e
  `importFinish=1779591475`.
- En `cumulative`, contra `assetID=118`, `pluginType=compliance` y
  `auditFileID=1000018`, `/analysis` con `vulndetails` devolvio
  `totalRecords=332`. El control `[1.1.1] ... [CV1]` quedo como
  `pluginID=1003966`, `severity.id=3`, `lastSeen=1779591450` y
  `vulnUUID=04176d51-7000-49e6-99ef-076b339b29eb`.
- En `cumulative`, contra el mismo Asset List y `auditFileID=1000023`,
  `/analysis` con `vulndetails` devolvio `totalRecords=2`. El control
  `[1.1.1] ... [CV2]` quedo como `pluginID=1004311`, `severity.id=0`,
  `lastSeen=1779591450` y
  `vulnUUID=029615da-a8ba-47e3-8c34-e1fca4e260e5`.
- Durante la ejecucion se observo un scan concurrente creado desde GUI
  (`Fullsafe_scan`, `scan.id=12`, `scanResult=25111`). No se uso para la
  evidencia de esta validacion.

### Incidencia importacion vulnerabilidades con PostgreSQL caido

Validacion del 2026-05-24:

- El scan `Fullsafe_scan` genero `scanResult=25113`, `status=Completed` e
  `importStatus=Error`.
- El error de importacion avanzo hasta escribir/exportar bases `cumulative` y
  `patched`, pero fallo al abrir PostgreSQL interno:
  `Error opening postgres DB ... 127.0.0.1:5432 ... Connection refused`.
- El scan `cred_check` genero `scanResult=25114` con el mismo patron de
  `importStatus=Error`. En ese caso tambien se observo que
  `192.168.1.135` no hizo match con assets existentes antes del fallo de
  PostgreSQL.
- Tras arrancar PostgreSQL interno, la validacion minima del laboratorio quedo
  sin incidencias criticas.
- Estado validado posterior: PostgreSQL respondio `select 1`, Tenable.sc quedo
  `running`, `/analysis` devolvio `343` registros con
  `vulndetails` para `assetID=118` y se genero
  `outputs/compliance_example_details.json` con `record_count=343`.
- Tras recrear Tenable.sc con arranque automatico de servicios internos y
  ejecutar `validate`, los scan results `25113` y `25114` aparecieron con
  `importStatus=Finished` y `scan_result_import_error_sample` quedo vacio.
- Conclusion: un `scanResult` en `status=Completed` no garantiza resultados
  explotables; para vulnerabilidades y compliance hay que revisar
  `importStatus=Finished` o confirmar los datos via `/analysis`.

### H07 - Control comentado en `naming_convention_win10_fullaudit`

Validacion del 2026-05-24:

- Se comento el control
  `[1.1.2][MS][W10][N/A][v4.0.0][L1] Ensure 'Maximum password age' is set to '365 or fewer days, but not 0'`
  en `naming_convention_win10_fullaudit.audit`.
- Se aplico el fichero por API sobre `auditFileID=1000018`, conservando el ID
  registrado y cambiando el `filename` interno de `scfile_TfGRAr` a
  `scfile_njK36B`.
- Se lanzo el mismo scan `win_10_MODIFICADO` (`scan.id=10`) y genero
  `scanResult=25125`, `status=Completed`, `importStatus=Finished`,
  `completedChecks=27822`, `finishTime=1779641657` e
  `importFinish=1779641663`, sin `importErrorDetails`.
- Antes del cambio, `assetID=118` + `auditFileID=1000018` acotado al
  repositorio `Default` (`9`) devolvia `332` registros. El control comentado
  aparecia con `pluginID=1005137`.
- Despues del scan, `assetID=118` + `auditFileID=1000018` acotado al
  repositorio `Default` (`9`) devolvio `331` registros. El control
  `pluginID=1005137` no aparecio con ese filtro.
- Al consultar `assetID=118` + `pluginType=compliance` sin `auditFileID`,
  acotado al repositorio `Default` (`9`), el control `pluginID=1005137` siguio
  visible como resultado antiguo con `lastSeen=1779635112` y tags `cm`
  parseables:
  `<cm:compliance-result>PASSED</cm:...>` y
  `<cm:compliance-audit-file>...</cm:...>`.
- En las consultas revisadas de `assetID=118` no aparecieron registros
  `pluginType=compliance` sin `<cm:compliance-result>` y sin
  `<cm:compliance-audit-file>`.
- El filtro temporal `lastSeen` acepta formato epoch `inicio-fin`. La ventana
  anterior `1779635000-1779637000` devolvio `335` registros sin `auditFileID`,
  incluyendo el control eliminado `pluginID=1005137` en el repositorio
  `Default` (`9`) con `lastSeen=1779635112`.
- La ventana actual `1779641000-1779642000`, posterior al scan que ya tenia el
  control comentado, devolvio `335` registros sin `auditFileID` y `0`
  apariciones de `pluginID=1005137`. Acotando ademas por
  `auditFileID=1000018`, la misma ventana devolvio `331` registros y tambien
  `0` apariciones del control eliminado.
- Esto valida que una ventana temporal suficientemente reciente sobre
  `lastSeen` elimina de la vista amplia los controles que no se volvieron a
  observar. Sin filtro temporal, esos controles pueden seguir visibles como
  resultados antiguos.
- Conclusion: comentar/eliminar un control del `.audit` no genera por si solo
  registros sin tags `cm`. El control desaparece de la vista acotada por el
  `auditFileID` actual, pero puede permanecer en la consulta amplia como
  resultado antiguo con sus tags `cm` originales. Esta prueba no confirma la
  hipotesis H07; la duda solo seguiria abierta para casos de audit registrado
  no resoluble o borrado/desregistrado.

### H07 - Audit desregistrado con resultados historicos

Validacion del 2026-05-24:

- Audit usado como prueba controlada: `auditFileID=1000023`,
  `name=win_10_MODIFICADO_v2_segundo_compliance`,
  `filename=scfile_UZrH6U`, `uuid=AA6DB420-8AFF-4FE8-8298-8392A05359D9`,
  descripcion `Temporary Codex probe; safe to delete`.
- Antes del borrado, `/policy/1000009` referenciaba `auditFileID=1000018` y
  `auditFileID=1000023`.
- Antes del borrado, `/analysis` con `assetID=118`,
  `pluginType=compliance` y `auditFileID=1000023` devolvio `5` registros:
  `3` en repositorio `10` (`compliance`) y `2` en repositorio `9` (`Default`).
- Registros asociados antes del borrado:
  `pluginID=1003714`, `pluginID=1004311` y `pluginID=1004312`. Todos tenian
  `<cm:compliance-result>PASSED</cm:...>` y
  `<cm:compliance-audit-file>...</cm:...>`.
- Se desregistro el audit con `DELETE /auditFile/1000023`. La llamada devolvio
  `error_code=0`.
- Despues del borrado, `GET /auditFile/1000023` fallo con
  `error_code=145` (`Unable to retrieve AuditFile #1000023`) y `/auditFile`
  ya no listo el ID. La policy `1000009` quedo referenciando solo
  `auditFileID=1000018`.
- Despues del borrado, `/analysis` con `assetID=118`,
  `pluginType=compliance` y `auditFileID=1000023` fallo con `error_code=143`
  (`Permission denied for filtering on Audit File #1000023`).
- Despues del borrado, la consulta amplia `assetID=118` +
  `pluginType=compliance` siguio devolviendo los `5` registros historicos de
  `pluginID=1003714`, `pluginID=1004311` y `pluginID=1004312`.
- Esos `5` registros historicos conservaron sus tags `cm` parseables:
  `<cm:compliance-result>` y `<cm:compliance-audit-file>`. En la consulta
  amplia de `assetID=118` no aparecieron registros sin ambos tags `cm`.
- Conclusion: borrar/desregistrar un audit file registrado no convierte los
  resultados historicos asociados en registros sin tags `cm`; simplemente deja
  de poder usarse el `auditFileID` eliminado como filtro. La hipotesis H07 queda
  rechazada para el comportamiento controlado de controles custom/audits
  desregistrados en este laboratorio.

### H08/H09 - Cambio de tipo y duplicado con mismo `description`

Validacion del 2026-05-24:

- Fuente de sintaxis: `NessusComplianceChecksReference.pdf`, seccion Windows
  `AUDIT_POWERSHELL`. La prueba uso `powershell_args:
  "get-wmiobject win32_operatingsystem"`, un cmdlet `get-` explicito y sin
  aliases, con `value_type: POLICY_TEXT`, `value_data: ".*Windows.*"` y
  `check_type: CHECK_REGEX`.
- Control probado:
  `[1.1.1][MS][W10][N/A][v4.0.0][L1][CV1] Ensure 'Enforce password history' is set to '24 or more password(s)'`.
- Baseline antes de la prueba: en `assetID=118`, `repositoryIDs=9`,
  `pluginType=compliance` y `auditFileID=1000018`, el control aparecia una sola
  vez con `pluginID=1005136`,
  `vulnUUID=d05adfed-812a-4618-9284-0a679183dd10`, `firstSeen=1779635112`,
  `lastSeen=1779641660`, resultado `FAILED`, `policy_value=[24..4294967295]`
  y `actual_value=0`.
- Variante 1: se sustituyo el bloque original `type: PASSWORD_POLICY` por un
  bloque `type: AUDIT_POWERSHELL`, manteniendo exactamente la misma
  `description`. Se aplico por API sobre `auditFileID=1000018`, cambiando el
  `filename` interno de `scfile_njK36B` a `scfile_SQy46P`.
- El scan usado fue `scan.id=17` (`naming_convention_win10_fullaudit`), porque
  `scan.id=10` estaba deshabilitado. El scan 17 usa `assetID=118`,
  repositorio `9` y una policy cuyo unico audit file es `auditFileID=1000018`.
- La variante 1 genero `scanResult=25127`, `status=Completed`,
  `importStatus=Finished`, `completedChecks=27822`, `finishTime=1779647244` e
  `importFinish=1779647254`.
- Resultado de variante 1: el control mantuvo `pluginID=1005136`,
  `vulnUUID=d05adfed-812a-4618-9284-0a679183dd10` y `firstSeen=1779635112`; el
  `lastSeen` avanzo a `1779647247`. El resultado cambio a `ERROR`, con
  `policy_value` observado `AUDIT_POWERSHELL value_data: '.*Windows.*'` y audit
  observado `60fcd0ae-b5fd-5261-8a4b-39a17ce439e3-730538-scfile_SQy46P`.
- Variante 2: se mantuvo el bloque `AUDIT_POWERSHELL` y se anadio de nuevo,
  sin cambios, la copia exacta del bloque original `PASSWORD_POLICY`, dejando
  dos bloques vivos con la misma `description` dentro del mismo `.audit`. Se
  aplico por API sobre `auditFileID=1000018`, cambiando el `filename` interno a
  `scfile_FayJp5`.
- La variante 2 genero `scanResult=25128`, `status=Completed`,
  `importStatus=Finished`, `completedChecks=27822`, `finishTime=1779647815` e
  `importFinish=1779647822`.
- Resultado de variante 2: `/analysis` mantuvo `totalRecords=331` para
  `assetID=118`, `repositoryIDs=9`, `pluginType=compliance` y
  `auditFileID=1000018`. Para la `description` duplicada devolvio un unico
  registro, no dos, con `pluginID=1005136`,
  `vulnUUID=d05adfed-812a-4618-9284-0a679183dd10` y `lastSeen=1779647819`.
- En ese unico registro, `pluginText` incluyo resultados compuestos: dos
  `<cm:compliance-result>` (`ERROR` y `FAILED`) y dos
  `<cm:compliance-actual-value>` (vacio y `0`). La severidad visible quedo en
  `severity.id=3`.
- Conclusiones:
  - Cambiar el tipo tecnico del control manteniendo exactamente la misma
    `description` no cambio el `pluginID` ni el `vulnUUID`; Tenable.sc actualizo
    el resultado del control existente.
  - Dos bloques vivos con la misma `description` dentro del mismo `.audit`,
    incluso con tipos distintos, colapsan en un unico control visible en
    `cumulative` y pueden acumular varios resultados dentro del mismo
    `pluginText`.
  - Si dos versiones deben coexistir como controles diferentes, hay que
    diferenciarlas en la `description`, por ejemplo con `[CV1]` y `[CV2]`.

### Catalogo simulado multi-OS y roles

Validacion del 2026-05-24:

- Se preparo un catalogo base para montar scans de simulacion por OS y rol:
  `REAL_win10.audit`, `SIMULATE_MS_SRV_DM.audit`,
  `SIMULATE_MS_SRV_DC.audit` y `OL_8.audit`.
- `REAL_win10.audit` parte de `naming_convention_win10_fullaudit.audit`, sin el
  duplicado de prueba del control `[1.1.1]`, sin sufijo `[CV1]` y con el
  control `[1.1.2]` activo de nuevo.
- `SIMULATE_MS_SRV_DM.audit` y `SIMULATE_MS_SRV_DC.audit` son copias simuladas
  de Windows Server 2016 con roles `[DM]` y `[DC]` en la naming convention:
  `[<control_id>][MS][2016][DM|DC][v4.0.0][L1] <titulo>`.
- `OL_8.audit` parte de `CIS_Oracle_Linux_8_v4.0.0_L1_Server.audit` y aplica la
  naming convention `[<control_id>][OL][8][N/A][v4.0.0][L1] <titulo>` a las
  descripciones de controles CIS que empiezan por identificador numerico.
- En los cuatro ficheros se asignaron valores reproducibles de `CONTROL_IG|IGx`
  y exactamente cuatro controles por fichero quedaron con
  `CONTROL_INTERNAL_VERSION|1`; el resto quedo con
  `CONTROL_INTERNAL_VERSION|0`.
- En los audits Windows Server se anadieron `CONTROL_MS_ONLY|true|false` y
  `CONTROL_DC_ONLY|true|false`. En `SIMULATE_MS_SRV_DM` hay 5 controles con
  `CONTROL_MS_ONLY|true`; en `SIMULATE_MS_SRV_DC` hay 5 controles con
  `CONTROL_DC_ONLY|true`.
- Subida a Tenable.sc:
  - `REAL_win10`: `auditFileID=1000018`, `uuid=FE62386B-43FD-4A79-A945-25D79991601C`,
    `filename=scfile_aZlohn`, `type=windows`.
  - `SIMULATE_MS_SRV_DM`: `auditFileID=1000026`,
    `uuid=5B573F25-61A3-428A-B867-A332F7E4E1F2`, `filename=scfile_4vtwLw`,
    `type=windows`.
  - `SIMULATE_MS_SRV_DC`: `auditFileID=1000027`,
    `uuid=579BB3D4-76BD-466F-8D66-0B51B22F55F5`, `filename=scfile_es4Gu5`,
    `type=windows`.
  - `OL_8`: `auditFileID=1000028`,
    `uuid=AA7E0DB9-328C-4EB5-BDBC-D9747FD872D9`, `filename=scfile_JM4CC2`,
    `type=unix`.
- Verificacion: para los cuatro audit files, el export de Tenable.sc coincide
  byte a byte normalizado con el fichero local (`local_export_same_normalized =
  true`). La evidencia tecnica queda en
  `outputs/catalog_audit_generation_summary.json`,
  `outputs/catalog_audit_create_remaining_results.json` y
  `outputs/catalog_audit_upload_verification.json`.

### Audits ligeros para retest de hipotesis

Contexto operativo definido el 2026-05-24:

- Se crearon dos `.audit` minimos para relanzar pruebas de comportamiento sin
  ejecutar el catalogo completo:
  - `light_check_win_10.audit`: `auditFileID=1000029`, `uuid=532741DA-6D80-414D-9A13-654E7BAD37C5`,
    `type=windows`, `filename=scfile_89zOsm`.
  - `light_check_ol_8.audit`: `auditFileID=1000030`, `uuid=8D274181-831C-45CE-A0CD-5C89C436B58F`,
    `type=unix`, `filename=scfile_crEUjF`.
- Los controles elegidos son deliberadamente baratos:
  - Windows: `[18.10.15.1]` y `[18.10.15.2]`, ambos `REGISTRY_SETTING` de una
    sola lectura.
  - Oracle Linux 8: `[7.1.1]` y `[7.1.3]`, ambos `FILE_CHECK` sobre ficheros
    pequenos (`/etc/passwd` y `/etc/group`).
- Los dos exports posteriores a la subida contenian los dos controles
  esperados y coincidian con el cuerpo local exacto. Evidencia local:
  `outputs/light_check_audit_uploads_latest.json`.

### Escenario Tenable.sc para queries KPI

Contexto operativo definido el 2026-05-24:

- Asset Lists de alcance:
  - `compliance_windows` (`assetID=118`): scope Windows.
  - `compliance_linux` (`assetID=122`): scope Linux.
  - `compliance_devices_mix` (`assetID=121`): scope mixto Windows + Linux.
- Repositorios activos:
  - `compliance_ws` (`repositoryID=14`): destino de resultados del audit
    `REAL_win10`.
  - `compliance_srv` (`repositoryID=13`): destino de resultados de
    `SIMULATE_MS_SRV_DM`, `SIMULATE_MS_SRV_DC` y `OL_8`.
  - `compliance_test` (`repositoryID=16`): destino de resultados de pruebas
    rapidas y retests ligeros.
- Los repositorios antiguos se consideran eliminados o fuera del escenario
  funcional actual. Las evidencias anteriores que los mencionan quedan como
  historico de validacion.
- Nota de lectura: las referencias previas a `naming_convention_win10_fullaudit`,
  `compliance_example` o repositorio `Default` (`9`) no se actualizan
  retroactivamente porque documentan pruebas ejecutadas antes del catalogo
  actual.
- Implicacion para las proximas queries:
  - Workstation Windows: `assetID` de `compliance_windows`,
    `auditFileID=1000018` (`REAL_win10`) y `repositoryIDs` de
    `compliance_ws` (`14`).
  - Servidores Windows/Linux simulados: `assetID` de
    `compliance_windows`, `compliance_linux` o `compliance_devices_mix` segun
    alcance, `auditFileID` de `SIMULATE_MS_SRV_DM` (`1000026`),
    `SIMULATE_MS_SRV_DC` (`1000027`) u `OL_8` (`1000028`), y `repositoryIDs`
    de `compliance_srv` (`13`).
  - Retest ligero: `assetID` de `compliance_windows` con
    `auditFileID=1000029` (`light_check_win_10`) o `assetID` de
    `compliance_linux` con `auditFileID=1000030` (`light_check_ol_8`), siempre
    acotado a `repositoryIDs=16` (`compliance_test`) cuando se quiera aislar la
    prueba.
