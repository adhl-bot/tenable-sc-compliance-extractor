# Tenable.sc Compliance Extractor

Proyecto para extraer compliance desde Tenable.sc en laboratorio y preparar datos para una futura ingesta en Splunk.

La guia de desarrollo por fases esta en `agents.md`.

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

La regla inicial es:

- `severity.id=0` -> control superado.
- `severity.id=1..4` -> control fallido.

## Uso rapido

En el laboratorio de Codex, Python esta disponible en:

```powershell
& 'C:\Users\Alberto\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' extract_compliance.py assets --pretty
```

En un entorno normal:

```bash
python extract_compliance.py assets --pretty
python extract_compliance.py audit-files --pretty
python extract_compliance.py details --asset-name compliance_example --output outputs/compliance_example_details.json --pretty
python extract_compliance.py extract --asset-id 0 --audit-file-id 1000010 --pretty
```

## Fase 1A - Detalles de Compliance

Comando validado en laboratorio:

```bash
python extract_compliance.py details --asset-name compliance_example --output outputs/compliance_example_details.json --pretty
```

Resultado validado:

- Asset List: `compliance_example`.
- IP: `192.168.128.30`.
- Registros: `77`.
- Tool API: `vulndetails`.
- Fallback usado: filtro `ip`, porque el asset static no tenia preparado el fichero interno de UUIDs de Tenable.sc.

Campos actuales por registro:

- `asset`
- `ip`
- `control_name`
- `actual_value`
- `last_observed`
- `last_observed_epoch`

Resultado validado en el laboratorio para `asset_id=0` y `audit_file_id=1000010`:

- `passed_controls`: 11
- `failed_controls`: 19
- `total_controls`: 30
- `compliance_percent`: 36.67

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

La autenticacion de laboratorio usa sesion usuario/password. Para produccion, preferir API keys con `TENABLE_SC_AUTH_MODE=api_keys`.

## Nota de laboratorio

Algunas Asset Lists dinamicas del lab pueden devolver errores de Tenable.sc del tipo `Error loading uuid file into UUID list`. Eso indica que Tenable.sc no tiene preparados los ficheros internos de esa asset list para el repositorio consultado. En produccion normalmente deberian estar preparados; en laboratorio puede requerir refrescar/recalcular la Asset List desde Tenable.sc antes de consultar sus resultados.
