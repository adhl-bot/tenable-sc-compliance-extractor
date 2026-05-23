# Tenable.sc Compliance Extractor

Proyecto para extraer compliance desde Tenable.sc en laboratorio y preparar datos para una futura ingesta en Splunk.

La guia de desarrollo por fases esta en `agents.md`.

La guia operativa y de configuracion del laboratorio esta en
`laboratorio/README.md`.

La guia para usuarios que solo quieren levantar y validar el laboratorio
portable esta en `laboratorio/GUIA_USUARIO.md`.

## Fases

- Fase 1A: extraccion de detalles de compliance a JSON usando `/rest/analysis` y validando `vulndetails` vs `listvuln`.
- Fase 1B: extraccion de KPIs por Asset List y audit file.
- Fase 2: Splunk, declarada pero no activa todavia.

El codigo actual incluye un prototipo de KPIs de Fase 1B con `sourceType=cumulative`, agrupado por Asset List y fichero audit.

## Salida inicial

Cada fila representa un cruce `asset list` x `audit file` con resultados:

- `asset_id`, `asset_name`, `asset_type`, `asset_ip_count`
- `audit_file_id`, `audit_file_name`, `audit_file_filename`, `audit_file_type`
- `passed_controls`
- `failed_controls`
- `total_controls`
- `compliance_percent`
- conteos por severidad: `info_count`, `low_count`, `medium_count`, `high_count`, `critical_count`

El prototipo usa un mapeo provisional de severidad para calcular
passed/failed. La validacion final de ese comportamiento vive en
`hypotheses_to_validate.md`.

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

Para produccion, preferir API keys con `TENABLE_SC_AUTH_MODE=api_keys`.
