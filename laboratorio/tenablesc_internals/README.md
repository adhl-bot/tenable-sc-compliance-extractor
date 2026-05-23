# Tenable.sc Internals Lab

Esta carpeta contiene el mapa interno del laboratorio Tenable.sc y un inspector
read-only para repetir el diagnostico cuando el contenedor cambie.

## Objetivo

Entender como se relacionan los elementos internos de Tenable.sc para poder
diagnosticar fallos reales del laboratorio: importacion de scans, filtros por
Asset List, estado de PostgreSQL, restos SQLite, Redis, microservicios, reportes
PDF, repositorios binarios y logs.

El objetivo no es sustituir la API soportada por Tenable. Para automatizaciones
del extractor se debe seguir usando la API REST documentada. Este material sirve
para salud del laboratorio, investigacion y reparacion controlada.

## Ficheros

- `inspect_tenablesc_internals.py`: inspector Python sin dependencias externas.
- `TENABLESC_INTERNAL_MAP.md`: mapa tecnico de componentes, relaciones y checks.
- `evidence/`: evidencias JSON generadas por el inspector cuando se ejecuta con
  `--output`.

## Ejecutar

Desde la raiz del proyecto:

```powershell
python laboratorio\tenablesc_internals\inspect_tenablesc_internals.py --pretty
```

Guardar evidencia versionable y revisable:

```powershell
python laboratorio\tenablesc_internals\inspect_tenablesc_internals.py `
  --pretty `
  --output laboratorio\tenablesc_internals\evidence\current_report.json `
  --quiet
```

Si `python` no esta en PATH dentro de Codex, usar el runtime bundled indicado en
`laboratorio/README.md`.

## Seguridad

El inspector esta disenado para no leer:

- Ficheros de licencia.
- Credenciales de `.env`.
- Claves de API.
- Dumps completos de resultados de scans.
- Contenido completo de ficheros `.audit`.

Solo recoge metadatos tecnicos, conteos, estados, nombres de objetos de
laboratorio, tamanos de ficheros, rutas y patrones de log. Aun asi, antes de
subir evidencia a GitHub conviene revisar el JSON porque los logs pueden incluir
IPs, nombres de host o nombres de scans del laboratorio.

## Relacion Con El Doctor

`laboratorio/build_lab.py doctor` es la herramienta operativa para saber si el
laboratorio esta listo.

Este inspector va mas profundo: explica de donde sale cada sintoma, que base de
datos o fichero lo respalda y que relacion hay entre GUI, API, Jobd, importacion,
repositorios, Asset Lists y motores de analysis.

## Fuentes

- Evidencia local del contenedor `tenablesc-labbox-ol8`.
- Codigo y herramientas locales bajo `/opt/sc`.
- Tenable.sc API Overview: https://docs.tenable.com/security-center/api/index.htm
- Tenable.sc Analysis API: https://docs.tenable.com/security-center/api/Analysis.htm
- Tenable.sc Asset API: https://docs.tenable.com/security-center/api/Asset.htm
- Tenable.sc AuditFile API: https://docs.tenable.com/security-center/api/AuditFile.htm
- Tenable.sc Scan Result API: https://docs.tenable.com/security-center/api/Scan-Result.htm
- Tenable.sc Status API: https://docs.tenable.com/security-center/api/Status.htm
