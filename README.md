# Tenable.sc Compliance Extractor

Proyecto para extraer compliance desde Tenable.sc en laboratorio y preparar datos para una futura ingesta en Splunk.

La guia de desarrollo por fases esta en `agents.md`.

El registro de desafios de modelo, identidad y metricas esta en
`CHALLENGES.md`.

Las evidencias funcionales, resultados de API, scan results y validaciones
Tenable estan en `VALIDACIONES_TENABLE.md`.

La guia operativa y de configuracion del laboratorio esta en
`laboratorio/README.md`.

La guia para usuarios que solo quieren levantar y validar el laboratorio
portable esta en `laboratorio/GUIA_USUARIO.md`.

Reglas base del extractor:

- La unidad minima de alcance y salida es el Asset List de Tenable.sc.
- Las consultas funcionales usan `sourceType=cumulative`.
- Las vistas `individual` o descargas de scan results se usan solo como
  diagnostico/evidencia funcional, no como flujo normal de extraccion.

## Fases

- Fase 1A: extraccion de detalles de compliance a JSON usando `/rest/analysis` y validando `vulndetails` vs `listvuln`.
- Fase 1B: extraccion de KPIs por Asset List y audit file.
- Fase 2: Splunk, declarada pero no activa todavia.

El codigo actual incluye un prototipo de KPIs de Fase 1B con
`sourceType=cumulative`, agrupado por Asset List y fichero audit. Tras la
validacion del 2026-05-23, ese prototipo no debe considerarse formula final:
`sumseverity` no basta para calcular `passed_controls` y `failed_controls`
porque Tenable.sc puede devolver estados como `WARNING` y registros compliance
sin tags `cm` parseables.

## Salida inicial

Cada fila representa un cruce `asset list` x `audit file` con resultados:

- `asset_id`, `asset_name`, `asset_type`, `asset_ip_count`
- `audit_file_id`, `audit_file_name`, `audit_file_filename`, `audit_file_type`
- `passed_controls`
- `failed_controls`
- `total_controls`
- `compliance_percent`
- conteos por severidad: `info_count`, `low_count`, `medium_count`, `high_count`, `critical_count`

El prototipo usa un mapeo historico de severidad para calcular passed/failed,
pero no debe considerarse contrato final. La Fase 1B final debe calcular
buckets por `<cm:compliance-result>` y mantener estados no binarios separados.
El registro de hipotesis queda reservado para validar el comportamiento temporal
del `.audit`.

## Uso rapido

Antes de extraer datos en el laboratorio, seguir `laboratorio/README.md`.

Comandos principales del extractor:

```bash
python extract_compliance.py assets --pretty
python extract_compliance.py audit-files --pretty
python extract_compliance.py details --asset-name <asset_name> --output outputs/compliance_details.json --pretty
python extract_compliance.py extract --asset-id <asset_id> --audit-file-id <audit_file_id> --pretty
```

## Fase 1A - Detalles De Compliance

Comando principal:

```bash
python extract_compliance.py details --asset-name <asset_name> --output outputs/compliance_details.json --pretty
```

Campos actuales por registro:

- `asset`
- `ip`
- `control_name`
- `actual_value`
- `last_observed`
- `last_observed_epoch`

Exportar todos los cruces con resultados:

```bash
python extract_compliance.py extract --output outputs/compliance_summary.json --pretty
```

Exportar CSV:

```bash
python extract_compliance.py extract --format csv --output outputs/compliance_summary.csv
```

Para una validacion corta:

```bash
python extract_compliance.py extract --limit-assets 1 --limit-audit-files 3 --pretty
```

## Configuracion

Por defecto lee `.env`. Para usar otro archivo:

```bash
python extract_compliance.py --env .env extract --pretty
```

El extractor usa el perfil Security Manager:
`TENABLE_SC_SECURITY_MANAGER_USERNAME` y
`TENABLE_SC_SECURITY_MANAGER_PASSWORD`. Las credenciales del administrador
global quedan separadas como `TENABLE_SC_GLOBAL_ADMIN_USERNAME` y
`TENABLE_SC_GLOBAL_ADMIN_PASSWORD`, reservadas para configuraciones globales.

Para produccion, preferir API keys con `TENABLE_SC_AUTH_MODE=api_keys`.
