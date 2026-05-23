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

### Compliance acumulado

Patron adoptado para este proyecto:

- Trabajar siempre contra el acumulado de Tenable.sc: `sourceType=cumulative`.
- Interpretar `cumulative` como la vista acumulada/latest de resultados en
  Tenable.sc.
- No usar `individual` ni `patched` para este proyecto.

### Audit files

Patron adoptado tras investigacion inicial:

- Usar `/auditFile` para inventario de `.audit` registrados.
- Usar `auditFileID` como filtro de `/analysis` cuando el audit sea resoluble en
  Tenable.sc.
- No asumir que `<cm:compliance-audit-file>` dentro de `pluginText` coincide con
  `/auditFile.name`, `/auditFile.filename` u `/auditFile.originalFilename`.
- Conservar el audit observado en `pluginText` como trazabilidad separada del
  `auditFileID` usado para filtrar.
- Registrar errores por audit sin romper la ejecucion completa, porque un audit
  listado por `/auditFile` puede devolver errores de filesystem al usarse como
  filtro de analysis.

#### Hipotesis pendientes

Las hipotesis pendientes sobre identidad de controles, cambios de `.audit`,
`reference`, duplicados y separacion por audit viven en
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
