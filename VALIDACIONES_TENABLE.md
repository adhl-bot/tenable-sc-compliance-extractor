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
  comparativas GUI/API, importaciones, evidencias Tenable IO y salidas de
  validacion funcional.
- No documentar aqui como levantar o reparar el laboratorio; eso vive en
  `laboratorio/README.md`.
- No guardar credenciales reales.
- Si una evidencia cierra una hipotesis, actualizar tambien
  `hypotheses_to_validate.md` y mover la decision confirmada a `agents.md` o
  `ESTANDARES_ADOPTADOS.md` cuando corresponda.
- Si una evidencia afecta a desafios de modelo o metricas, actualizar
  `CHALLENGES.md`.

## Comandos de validacion funcional

Probar API Tenable IO / Vulnerability Management:

```powershell
python scripts\tenable_io_probe.py --sample-size 5 --max-text-len 160
```

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
- El audit observado en `.nessus` y `pluginText` cambio en cada ejecucion como
  copia `...-scfile_*`.
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
  con policy y/o `.nessus` cuando haya dudas.

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

## Tenable IO secundario

Alcance de la evidencia:

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
- Pruebas reproducibles con `scripts/tenable_io_probe.py`.
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
