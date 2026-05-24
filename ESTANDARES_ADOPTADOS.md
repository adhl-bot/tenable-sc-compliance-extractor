# Estandares adoptados

Este fichero recopila patrones tecnicos que se adopten al analizar utilidades
existentes y nuevas necesidades de la API de Tenable.sc.

`agents.md` sigue siendo la fuente de verdad del proyecto para fases, alcance,
contexto operativo y decisiones generales. `hypotheses_to_validate.md` es el
registro canonico de hipotesis pendientes. Este documento solo recoge formas de
trabajo reutilizables para organizar scripts y llamadas tecnicas.

## Utilidades Tenable.sc

### Organizacion esperada

- Mantener scripts invocables por CLI.
- Separar configuracion, cliente Tenable.sc, logica de negocio y salida.
- Evitar credenciales, URLs o rutas fijas dentro del codigo.
- Ejecutar utilidades y pruebas con el entorno virtual local `.venv` del
  proyecto, preferentemente invocando `.\.venv\Scripts\python.exe` en comandos
  documentados para Windows.
- Instalar dependencias Python dentro de `.venv`; no depender de librerias
  instaladas en el Python global de la maquina.
- Usar `.env` para valores locales y `.env.example` para plantillas entregables.
- Mantener salidas y logs en carpetas dedicadas.
- Mantener modo `--dry-run` para cualquier utilidad que pueda modificar Tenable.sc.
- Permitir ejecutar una o varias tareas concretas por nombre.
- Hacer backup o registrar estado previo antes de modificar Asset Lists u otros objetos.

### Configuracion declarativa

Para utilidades repetibles, preferir un fichero JSON de configuracion con tareas
nombradas. Patron adoptado desde `TenSC_Compliance_asset_update`:

```json
{
  "queries": {
    "nombre_de_tarea": {
      "repo": "EMEA_Servers",
      "query": "( 'Asset origen [123]' AND 'Otro asset [456]' )",
      "last_observed": "0:30",
      "asset_id_to_change": 9999
    }
  }
}
```

Regla principal:

- `query` define los Asset Lists origen.
- `asset_id_to_change` define el Asset List destino que recibira los resultados.
- `repo` define el repositorio Tenable.sc donde se ejecuta la consulta.
- `last_observed` define la ventana temporal usada en el filtro `lastSeen`.

### Expresiones de Asset Lists

Patron adoptado para expresar combinaciones de assets:

```text
'Nombre del asset [ID]'
```

Se soportan expresiones booleanas:

```text
( 'Asset A [100]' AND 'Asset B [200]' )
( 'Asset A [100]' OR 'Asset B [200]' )
( 'Asset A [100]' AND NOT 'Asset B [200]' )
```

La utilidad analizada convierte esas expresiones en filtros de Tenable.sc:

- Un unico asset se envia como filtro `asset = {"id": "...", "name": "..."}`.
- Una expresion booleana se envia como asset math con operador `~`.
- `AND` se traduce a `intersection`.
- `OR` se traduce a `union`.
- `NOT` se traduce a `complement`.

### Extraccion de IPs desde Asset Lists

Patron adoptado para sacar IPs a partir de una query de assets:

```python
self.sc.analysis.vulns(
    *last_seen_filters,
    asset_filter,
    repository_filter,
    plugin_type_filter,
    type="vuln",
    tool="sumip",
    source="cumulative",
    sort_direction="asc",
    sort_field="ip",
)
```

Uso esperado:

- `tool="sumip"` cuando la finalidad sea obtener una lista de IPs.
- `source="cumulative"` salvo decision futura en contra.
- Filtro de repositorio calculado desde el nombre de repo.
- Filtro `lastSeen` parametrizado.
- Filtro de Asset List construido desde expresiones declarativas.

### Unidad De Consulta Compliance

Patron adoptado para el extractor de compliance:

- La unidad minima de alcance y salida es el Asset List de Tenable.sc.
- Las consultas funcionales de Fase 1A y Fase 1B deben anclarse en `assetID`
  o en una expresion de Asset Lists cuando aplique.
- Las validaciones de comportamiento temporal deben incluir siempre al menos un
  Asset List concreto y el filtro `pluginType=compliance`.
- No usar una IP suelta como agrupacion funcional, aunque aparezca en los
  registros de salida.
- El filtro `ip` solo puede usarse como fallback tecnico cuando un Asset List
  estatico falle por artefactos internos no preparados. En ese caso, la salida
  debe conservar el `asset_id`, `asset_name` y la indicacion de fallback usado.

### Compliance acumulado

Patron adoptado para este proyecto:

- Trabajar siempre contra el acumulado de Tenable.sc: `sourceType=cumulative`.
- Interpretar `cumulative` como la vista acumulada/latest de resultados en
  Tenable.sc.
- No usar `individual` ni `patched` como vista funcional del extractor.
- `individual` y descargas de `scanResult` pueden usarse solo como diagnostico
  o evidencia funcional para cerrar hipotesis, por ejemplo consistencia
  temporal de un `.audit`.

### Estados de compliance y KPIs

Patron adoptado tras validacion del 2026-05-23:

- No calcular `passed_controls` y `failed_controls` solo desde `severity.id`.
- Usar `<cm:compliance-result>` como fuente funcional del estado cuando este
  disponible.
- Mantener buckets separados para estados no binarios como `WARNING`, `ERROR`,
  `UNKNOWN` o registros `pluginType=compliance` sin tags `cm` parseables.
- Para la metrica principal, todo estado distinto de `PASSED` se agrupa en
  `failed_controls`. Esto incluye `FAILED`, `WARNING`, `ERROR`, `UNKNOWN`,
  registros sin tags `cm` parseables y cualquier otro estado no superado.
- Calcular `compliance_percent` como `passed_controls / total_controls`, donde
  `total_controls = passed_controls + failed_controls`.
- Mantener ademas metricas separadas por estado concreto, por ejemplo
  `failed_explicit_controls`, `warning_controls`, `error_controls`,
  `unknown_controls` y `unparsed_controls`.
- Los controles de aplicabilidad/report y controles con `if` anidados cuentan
  como un unico control principal cuando Tenable devuelve un unico resultado
  final con subresultados anidados en el `pluginText`.
- Usar `sumseverity` solo como apoyo para conteos de severidad, no como mapeo
  binario definitivo.
- Conservar `plugin_text_sha256` cuando se parseen campos desde `pluginText`;
  no incluir `pluginText` completo por defecto en salidas pensadas para ingesta.

### Audit files

Patron adoptado tras investigacion inicial:

- Usar `/auditFile` para inventario de `.audit` registrados.
- Usar `auditFileID` como filtro de `/analysis` cuando el audit sea resoluble en
  Tenable.sc.
- Para validar estado actual/latest de un audit registrado, consultar con
  `assetID`, `pluginType=compliance`, `sourceType=cumulative` y `auditFileID`;
  el cumulative amplio por Asset List puede conservar controles de ejecuciones
  anteriores que ya no estan en el audit actual.
- Separar identidad registrada y trazabilidad observada: `auditFileID` es el
  filtro funcional para latest, el prefijo estable de
  `<cm:compliance-audit-file>` identifica el audit observado en las evidencias,
  y el valor completo `...-scfile_*` identifica la copia concreta de una
  ejecucion.
- No usar la policy como separador implicito del estado `cumulative`: en la
  validacion con el mismo Asset List y el mismo `auditFileID` ejecutados desde
  dos policies distintas, Tenable.sc mantuvo continuidad de controles y solo
  actualizo `lastSeen`.
- No asumir que `<cm:compliance-audit-file>` dentro de `pluginText` coincide con
  `/auditFile.name`, `/auditFile.filename` u `/auditFile.originalFilename`.
- Conservar el audit observado en `pluginText` como trazabilidad separada del
  `auditFileID` usado para filtrar.
- Registrar errores por audit sin romper la ejecucion completa, porque un audit
  listado por `/auditFile` puede devolver errores de filesystem al usarse como
  filtro de analysis.

### Nombres unicos en controles `.audit`

Patron adoptado para audits custom cuando se parte de cero en produccion:

- Evitar controles con el mismo `description` exacto en distintos `.audit`;
  Tenable puede reutilizar/generar el mismo `pluginID` y provocar solapes
  visibles incluso cuando se filtra por un `auditFileID` concreto.
- El `description` debe incluir un namespace visible, estable y controlado:
  `[<control_id>][<OS>][<OS_VERSION>][<ROLE>][<BENCHMARK_VERSION>][<LEVEL>] <titulo original>`.
- Todos los campos que forman el identificador visible van entre corchetes y no
  llevan separador entre bloques.
- `control_id` es el numero inicial del control dentro del benchmark.
- `OS` y `OS_VERSION` usan una taxonomia cerrada y reducida. Valores iniciales:
  `[MS][W10]`, `[MS][W11]`, `[MS][2016]`, `[MS][2019]`, `[MS][2022]` y
  `[OL][8]` para Oracle Linux 8.
- Para anadir un nuevo sistema operativo o version, definir primero el par de
  tokens en esta taxonomia y adaptar cualquier parser/validador que consuma el
  prefijo. No introducir valores libres en los `.audit`.
- `ROLE` solo tiene semantica especifica cuando aplique. Para Microsoft Server:
  `[DM]` significa domain member/member server y `[DC]` significa domain
  controller. Para OS, workstation o Linux donde el rol no aplique o no este
  definido, usar `[N/A]`; no usar placeholders como `[role]`.
- `BENCHMARK_VERSION` es la version simplificada del benchmark, por ejemplo
  `[v4.0.0]` o `[v5.0.0]`.
- `LEVEL` es el layer/nivel de cumplimiento, por ejemplo `[L1]` o `[L2]`.
- `<titulo original>` se conserva sin modificar respecto al titulo original de
  Tenable/CIS, incluidos sufijos como `(MS only)` cuando formen parte del
  titulo.
- `reference` debe incluir como minimo `CONTROL_IG|IGx` y
  `CONTROL_INTERNAL_VERSION|x`.
- `CONTROL_IG` conserva el IG heredado del benchmark.
- `CONTROL_INTERNAL_VERSION` registra la version interna del control cuando
  cambian sus campos o su forma de actuar, pero no cambia su ID funcional. El
  valor inicial es `CONTROL_INTERNAL_VERSION|0`.
- Todos los metadatos propios que se anadan para enriquecer el control en
  `reference` deben empezar por `CONTROL_`, usando pares
  `CONTROL_<NOMBRE>|<valor>`. Las referencias originales de frameworks externos
  pueden conservar su nombre original, por ejemplo `800-53|...`.
- Los metadatos adicionales que pida el cliente se anaden como nuevos pares
  `CONTROL_<NOMBRE>|<valor>` en `reference`; enriquecen el control, pero no
  modifican su identificador unico.
- Para audits Microsoft Server, los campos `CONTROL_MS_ONLY|true|false` y
  `CONTROL_DC_ONLY|true|false` indican si el control aplica solo a Member
  Server o solo a Domain Controller. Estos campos enriquecidos solo aplican a
  audits Windows Server; si el `.audit` no es de Microsoft Server, no deben
  anadirse.
- Consecuencia importante: `CONTROL_INTERNAL_VERSION` no separa `pluginID`
  porque no esta en `description`. Si dos implementaciones del mismo control
  deben coexistir como controles distintos, anadir un campo visible de version
  de coexistencia en el `description`, por ejemplo `[CV1]` y `[CV2]`:
  `[<control_id>][<OS>][<OS_VERSION>][<ROLE>][<BENCHMARK_VERSION>][<LEVEL>][CVx] <titulo original>`.
  Este campo solo se usa cuando sea necesario ejecutar varias versiones vivas
  del mismo control.

Ejemplos:

```text
description : "[17.7.5][MS][2019][DC][v5.0.0][L1] Ensure 'Audit Other Policy Change Events' is set to include 'Failure'"
reference   : "800-53|AU-2,CONTROL_IG|IG2,CONTROL_INTERNAL_VERSION|0,CONTROL_MS_ONLY|false,CONTROL_DC_ONLY|true"

description : "[1.2.3][MS][2022][DM][v5.0.0][L1] Ensure 'Allow Administrator account lockout' is set to 'Enabled' (MS only)"
reference   : "800-53|AC-7,CONTROL_IG|IG3,CONTROL_INTERNAL_VERSION|0,CONTROL_MS_ONLY|true,CONTROL_DC_ONLY|false"

description : "[1.1.1][MS][W11][N/A][v4.0.0][L1] Ensure 'Enforce password history' is set to '24 or more password(s)'"
reference   : "800-53|IA-5(1),CONTROL_IG|IG1,CONTROL_INTERNAL_VERSION|0"
```

#### Validaciones pendientes

Las validaciones pendientes ya no se organizan como una lista amplia de
hipotesis tecnicas. El registro canonico se limita al comportamiento temporal
del `.audit`, sus controles, policies e importaciones en
`hypotheses_to_validate.md`. Este documento solo debe recoger patrones ya
adoptados o reglas tecnicas confirmadas.

### Actualizacion de Asset Lists

Patron adoptado para llevar resultados a otro asset:

```python
sc.asset_lists.edit(asset_id, ips=list_ip)
```

Reglas:

- El asset destino debe venir identificado por ID.
- Antes de actualizar, consultar el detalle del asset destino y registrar sus
  `definedIPs` actuales.
- Si la lista de IPs calculada esta vacia, no actualizar automaticamente salvo
  que la tarea lo indique de forma explicita.
- Cualquier actualizacion debe poder ejecutarse antes con `--dry-run`.

### Criterios para nuevas utilidades

- Cada utilidad debe tener una entrada CLI clara.
- Cada utilidad debe poder probarse en modo no destructivo cuando modifique datos.
- Cada utilidad debe documentar inputs, endpoint/tool usado y outputs.
- La logica reusable debe vivir en modulos, no quedar duplicada en scripts sueltos.
- Los tests deben cubrir parsers, normalizacion de datos y construccion de filtros.
- Los errores por tarea deben registrarse sin romper toda la ejecucion cuando sea
  posible continuar con las siguientes tareas.

## Observaciones del analisis inicial

La utilidad `TenSC_Compliance_asset_update` aporta patrones utiles:

- Configuracion por tareas en JSON.
- Parser de expresiones booleanas de Asset Lists.
- Uso de pyTenable para `analysis.vulns`.
- Uso de `sumip` para obtener IPs.
- Backup previo de IPs del Asset List destino.
- Modo `--dry-run`.
- Ejecucion parcial con `--queries`.

Aspectos que no se deben trasladar tal cual:

- Credenciales o host hardcodeados.
- Secretos codificados en base64 dentro del codigo.
- `venv` versionado dentro del proyecto.
- Actualizar automaticamente con una IP ficticia cuando una query no devuelve
  resultados, salvo que se pida explicitamente para un caso concreto.

## Harness de desarrollo

Patron adoptado desde el analisis de `walkinglabs/learn-harness-engineering`:

- Instrucciones: mantener `agents.md` como fuente de verdad y usar documentos
  auxiliares solo para protocolos o patrones tecnicos.
- Estado: no duplicar fases ni decisiones en un `feature_list.json` mientras
  `agents.md` sea la fuente de verdad del proyecto.
- Verificacion: usar un comando de arranque/check local antes de cerrar cambios.
- Scope: trabajar una funcionalidad cada vez y bloquear avance si cambia el
  modelo de datos o la query de Tenable.sc.
- Ciclo de sesion: inicio con lectura de contexto, ejecucion con pruebas, cierre
  con evidencia y limitaciones.

Artefactos adoptados:

- `HARNESS_DESARROLLO.md`: protocolo de harness adaptado al proyecto.
- `scripts/harness_check.ps1`: verificacion local basica.

Regla:

- El harness debe controlar el flujo de trabajo, no reemplazar la documentacion
  operativa del proyecto.
