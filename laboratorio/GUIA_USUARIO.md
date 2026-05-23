# Guia De Usuario Del Laboratorio Portable

Esta guia es para una persona que solo quiere levantar el laboratorio y comprobar
que funciona. No hace falta conocer Docker en detalle.

## Que Necesitas

- Windows 10/11.
- Docker Desktop instalado y abierto.
- Python 3 instalado y disponible como `python`.
- Puertos libres:
  - `8443` para Tenable.sc.
  - `8835` para Nessus.
- La carpeta del proyecto con `laboratorio/` completa.

## Que Debe Haber Dentro De `laboratorio`

Contenido minimo:

```text
laboratorio/
  labbox-docker.zip
  docker-compose.yml
  build_lab.py
  .env.example
  GUIA_USUARIO.md
  PREPARAR_LABORATORIO.ps1
  ARRANCAR_LABORATORIO.ps1
  VALIDAR_LABORATORIO.ps1
```

Despues del primer arranque tambien apareceran:

```text
laboratorio/
  .env
  labbox-utils/
```

El fichero `labbox-docker.zip` contiene la imagen privada de Tenable.sc y no se
debe subir a GitHub ni enviar por canales no autorizados.

## Primer Uso En Un PC Nuevo

1. Abre Docker Desktop.
2. Abre PowerShell.
3. Entra en la carpeta del proyecto.
4. Ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\laboratorio\PREPARAR_LABORATORIO.ps1
```

Este script prepara el laboratorio desde la imagen:

- Crea `laboratorio/.env` si no existe.
- Carga la imagen privada desde `laboratorio/labbox-docker.zip`.
- Descarga o usa localmente la imagen publica de Nessus.
- Extrae `laboratorio/labbox-utils/`.
- Arranca Tenable.sc y Nessus.
- Ejecuta diagnostico y validacion.

No restaura backups de datos. El laboratorio se recrea desde las imagenes.

## Arrancar Un Laboratorio Ya Preparado

Si el laboratorio ya fue preparado antes, usa:

```powershell
powershell -ExecutionPolicy Bypass -File .\laboratorio\ARRANCAR_LABORATORIO.ps1
```

Al terminar, abre:

- Tenable.sc: `https://localhost:8443`
- Nessus: `https://localhost:8835`

## Validar Que Todo Esta Bien

Ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\laboratorio\VALIDAR_LABORATORIO.ps1
```

El resultado esperado es:

- `doctor` sin incidencias criticas.
- `validate` genera `outputs/compliance_example_details.json`.
- `package-status` indica `Laboratorio portable: COMPLETO`.

## Que No Debes Borrar

No borres si quieres conservar un laboratorio portable:

- `laboratorio/labbox-docker.zip`
- `laboratorio/.env`
- `laboratorio/labbox-utils/`

No hace falta guardar ni transportar backups de datos. Si se borra el contenedor,
el laboratorio se vuelve a crear desde la imagen.

## Problemas Frecuentes

Si aparece que Docker no responde:

- Abre Docker Desktop.
- Espera a que indique que esta arrancado.
- Repite el comando.

Si dice que un puerto esta ocupado:

- Cierra la aplicacion que este usando `8443` o `8835`.
- Repite el arranque.

Si `python` no se reconoce:

- Instala Python 3.
- Marca la opcion de anadir Python al PATH.
- Cierra y abre de nuevo PowerShell.

Si `package-status` dice `INCOMPLETO`, revisa la linea marcada como `FALTA`.
Normalmente significa que falta `labbox-docker.zip`, `.env` o `labbox-utils/`.
