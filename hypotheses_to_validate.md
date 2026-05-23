# Hipotesis por validar

Este fichero es el registro canonico de hipotesis pendientes de validacion.

Las hipotesis referentes al comportamiento de Tenable.sc, Tenable IO, Nessus,
`.audit`, `/analysis`, identidad de controles, estados de compliance, Asset
Lists o correlacion de scans deben vivir aqui y no repetirse en otros Markdown.

Reglas de mantenimiento:

- `agents.md` puede enlazar este fichero, pero no debe mantener listados
  paralelos de hipotesis pendientes.
- `ESTANDARES_ADOPTADOS.md`, `README.md` y `HARNESS_DESARROLLO.md` pueden
  describir reglas ya confirmadas o el protocolo de trabajo, pero no duplicar
  el contenido de este registro.
- Cuando una hipotesis se confirme, mover la decision o patron confirmado a
  `agents.md` o `ESTANDARES_ADOPTADOS.md`, y actualizar o retirar la entrada
  de este fichero.
- Cuando una hipotesis se descarte, marcarla como `Rechazada` con evidencia
  minima y fecha.
- Cada entrada debe indicar estado, alcance, validacion necesaria y evidencia.

Estados permitidos:

- `Pendiente`: aun no hay prueba suficiente.
- `En validacion`: hay pruebas parciales, pero falta cerrar la conclusion.
- `Confirmada`: probada en laboratorio Tenable.sc o fuente oficial aplicable.
- `Rechazada`: probada y descartada.

## H01 - Volumen de `pluginText`

- Estado: `Pendiente`.
- Alcance: Fase 1A / salida JSON.
- Hipotesis: el JSON final podria no necesitar `pluginText` completo si los
  campos parseados y un hash permiten reconstruir trazabilidad suficiente.
- Validacion necesaria: comparar volumen, campos requeridos para Splunk,
  auditoria posterior y capacidad de reconstruir host, control, resultado,
  audit y asset.
- Evidencia actual: Fase 1A usa `vulndetails` porque `pluginText` permite
  extraer campos como `actual_value`.

## H02 - Audit registrado frente a audit observado

- Estado: `En validacion`.
- Alcance: Tenable.sc / `/analysis` / `.nessus`.
- Hipotesis: el modelo final debe conservar por separado el audit registrado
  (`auditFileID` y datos de `/auditFile`) y el audit observado en resultados
  (`<cm:compliance-audit-file>` o valor del `.nessus`), porque no siempre
  coinciden.
- Validacion necesaria: revisar scanResults reales, resultados importados y
  consultas `cumulative` e `individual` para confirmar que ambos campos dan
  trazabilidad suficiente.
- Evidencia actual: las evidencias de laboratorio sobre audit registrado frente
  a audit observado viven en `laboratorio/README.md` y en salidas locales bajo
  `outputs/`.

## H03 - Asset Lists dinamicas o no preparadas

- Estado: `Pendiente`.
- Alcance: Tenable.sc / Asset Lists / `/analysis`.
- Hipotesis: las Asset Lists dinamicas o no preparadas pueden necesitar una
  estrategia distinta al fallback por IP usado para Asset Lists estaticas.
- Validacion necesaria: probar Asset Lists dinamicas siguiendo
  `laboratorio/README.md` o en produccion, documentar errores, comprobar si hay
  fallback reproducible y definir cuando bloquear la extraccion.
- Evidencia actual: las incidencias y repairs de Asset Lists del laboratorio
  viven en `laboratorio/README.md`.

## H04 - Fiabilidad de `auditFileID` como filtro

- Estado: `En validacion`.
- Alcance: Tenable.sc / `/analysis`.
- Hipotesis: `auditFileID` permite filtrar o agrupar por audit registrado
  cuando el audit es resoluble en Tenable.sc, pero no debe usarse como unica
  prueba de audit ejecutado sin contrastar policy, `.nessus` o totales.
- Validacion necesaria: probar todos los repositorios relevantes y registrar
  audits listados por `/auditFile` que fallen o produzcan matches parciales.
- Evidencia actual: los casos de laboratorio sobre `auditFileID`, errores y
  matches parciales viven en `laboratorio/README.md` y en salidas locales bajo
  `outputs/`.

## H05 - Mapeo de severidad a PASSED/FAILED

- Estado: `Pendiente`.
- Alcance: Fase 1B / KPIs.
- Hipotesis: `severity.id=0` equivale a control superado y `severity.id>0`
  equivale a control fallido.
- Validacion necesaria: contrastar `severity`, `<cm:compliance-result>`,
  GUI y casos con error, warning, unknown o estados no binarios.
- Evidencia actual: el prototipo `sumseverity` usa este mapeo; los datos de
  validacion de laboratorio viven en `laboratorio/README.md`.

## H06 - Estados no binarios en compliance

- Estado: `Pendiente`.
- Alcance: Fase 1B / calculo de porcentaje.
- Hipotesis: pueden existir estados no binarios que deban quedar fuera del
  porcentaje `passed / total` o formar buckets propios.
- Validacion necesaria: recolectar resultados con Error, Warning, Unknown u
  otros estados y definir formula final.
- Evidencia actual: Tenable IO observo contadores `Passed`, `Error` y
  `Failed`; la evidencia del laboratorio secundario vive en
  `laboratorio/README.md`. No extrapolar automaticamente a Tenable.sc.

## H07 - Asset Lists tecnicas o default

- Estado: `Pendiente`.
- Alcance: Fase 1B / seleccion de alcance.
- Hipotesis: algunas Asset Lists de produccion seran tecnicas/default y deben
  excluirse de KPIs y detalle.
- Validacion necesaria: inventariar Asset Lists de produccion y clasificarlas
  como negocio o tecnicas.
- Evidencia actual: pendiente de inventario real.

## H08 - Identidad de host

- Estado: `Pendiente`.
- Alcance: modelo de datos.
- Hipotesis: la identidad de host final debe priorizar o combinar `hostUUID`,
  `uuid`, `ip`, `dnsName`, `netbiosName` y repositorio.
- Validacion necesaria: comparar estabilidad de esos campos entre scans,
  repositorios, imports y cambios de IP/nombre.
- Evidencia actual: Fase 1A conserva IP y datos visibles; falta definir clave
  historica.

## H09 - Identidad de controles al cambiar el `.audit`

- Estado: `En validacion`.
- Alcance: Tenable.sc / identidad historica de controles.
- Hipotesis: cambios funcionales del `.audit` afectan a distintos
  identificadores de control segun el campo modificado.
- Validacion necesaria: consolidar la matriz de cambios:
  `reference`, `value_data`, `description`, ejecucion de dos audits y
  duplicados con mismo titulo/alcance.
- Evidencia actual:
  - Conversacion externa con Exa de Tenable VM 2026-05-22, no confirmada para
    Tenable.sc: cambiar solo valor esperado mantendria el control; cambiar
    nombre/descripcion lo trataria como control nuevo; sin filtro de audit
    podrian verse controles logicamente equivalentes.
  - La referencia de compliance checks de Nessus indica en varios tipos de
    checks que `description` debe ser unico y que Tenable puede usarlo para
    generar un plugin ID unico. Es evidencia relacionada, pero no cierra por si
    sola el comportamiento en Tenable.sc `sourceType=cumulative`.
  - Cambiar solo `reference` no creo controles nuevos ni aumento totales en
    Tenable.sc; mantuvo `pluginID`, `pluginName`, `vulnUUID`, severidad y
    resultado.
  - Cambiar `value_data` manteniendo nombre no creo control visible nuevo, pero
    cambio `policy_value`, `actual_value`, `check_id`, `full_id` y
    `functional_id`.
  - Cambiar `description`/nombre si creo un control nuevo visible.

## H10 - Duplicados o colapso de controles equivalentes

- Estado: `Pendiente`.
- Alcance: Tenable.sc / cumulative.
- Hipotesis: dos checks con mismo titulo o alcance funcional pueden colapsar en
  un unico resultado visible en lugar de generar dos registros separados.
- Validacion necesaria: aislar una prueba de duplicados y comparar
  `pluginID`, `vulnUUID`, `actual_value`, `firstSeen`, `lastSeen` y
  `totalRecords`.
- Evidencia actual: se observo un `actual_value` doble (`0\n\n0`) en lugar de
  otro registro separado, pero aun no se considera contrato.

## H11 - `reference` como metadato de negocio

- Estado: `En validacion`.
- Alcance: Tenable.sc y Tenable IO.
- Hipotesis: `reference` puede usarse para anadir etiquetas de negocio
  (`CLIENT_IG`, `CLIENT_TAG`, criticidad, owner u otros metadatos) sin cambiar
  la identidad del control ni generar duplicados.
- Validacion necesaria: revalidar matriz completa en Tenable.sc y mantener la
  evidencia de Tenable IO separada hasta confirmar equivalencia.
- Evidencia actual:
  - En Tenable.sc, una sola linea `reference` con referencias originales y
    custom al final promociono metadatos a `xref` en controles aplicables.
  - Una segunda linea `reference` separada llego a `<cm:compliance-reference>`,
    pero no siempre a GUI/Cross References.
  - En Tenable IO, un mismo check observado en dos audits mantuvo
    `compliance_full_id`, `compliance_functional_id` y
    `compliance_informational_id`, con y sin referencias custom.

## H12 - Ubicacion final del extractor

- Estado: `Pendiente`.
- Alcance: despliegue / Fase 2.
- Hipotesis: ejecutar el extractor en host, contenedor dedicado, Splunk modular
  input o tarea programada cambia credenciales, rutas, logs, dependencias y
  operativa.
- Validacion necesaria: decidir topologia antes de Fase 2 y parametrizar el
  despliegue.
- Evidencia actual: la configuracion operativa actual vive en
  `laboratorio/README.md`; Splunk no esta activo como fase.
