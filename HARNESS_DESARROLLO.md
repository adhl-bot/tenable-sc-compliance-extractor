# Harness de desarrollo

Este documento adapta ideas de harness engineering al proyecto Tenable.sc
Compliance Extractor.

No sustituye a `agents.md`. La fuente de verdad de fases, alcance, decisiones y
contexto operativo sigue siendo `agents.md`. El harness define como trabajar de
forma controlada alrededor de esa fuente.

## Objetivo

Reducir cambios impulsivos y cierres prematuros cuando se desarrollen utilidades
para la API de Tenable.sc.

El harness debe ayudar a:

- iniciar cada sesion con el mismo contexto;
- trabajar una funcionalidad cada vez;
- verificar antes de declarar algo cerrado;
- dejar evidencia de pruebas;
- distinguir hechos confirmados de hipotesis no confirmadas;
- evitar duplicar secretos, rutas locales o decisiones de fase fuera de
  `agents.md`;
- evitar duplicar hipotesis pendientes fuera de `hypotheses_to_validate.md`.

## Subsistemas adoptados

### 1. Instrucciones

Artefactos actuales:

- `agents.md`: fuente de verdad del proyecto.
- `hypotheses_to_validate.md`: registro canonico de hipotesis pendientes.
- `laboratorio/README.md`: guia canonica de configuracion y operacion del laboratorio.
- `laboratorio/GUIA_USUARIO.md`: guia para levantar y validar el laboratorio portable sin conocimientos Docker.
- `README.md`: guia corta de uso.
- `ESTANDARES_ADOPTADOS.md`: patrones tecnicos reutilizables.
- `HARNESS_DESARROLLO.md`: protocolo de trabajo controlado; no sustituye a
  `ESTANDARES_ADOPTADOS.md` ni recoge configuraciones de laboratorio.

Regla:

- Antes de tocar codigo, leer `agents.md` y el estandar tecnico que aplique en
  `ESTANDARES_ADOPTADOS.md`.
- El estandar local es trabajar con el entorno virtual del proyecto en `.venv`.
  Usar `.\.venv\Scripts\python.exe` para comandos reproducibles desde Codex o
  activar `.\.venv\Scripts\Activate.ps1` en una terminal interactiva.
- Las dependencias Python nuevas deben instalarse dentro de `.venv` y quedar
  declaradas en el mecanismo de dependencias que adopte el proyecto; no instalar
  librerias en el Python global como parte del flujo normal.
- Si la tarea implica levantar, diagnosticar, reparar, validar, consultar,
  migrar o modificar el laboratorio, leer primero `laboratorio/README.md`; las
  configuraciones del laboratorio viven alli y no deben duplicarse aqui.
- Para comprobar portabilidad del laboratorio, usar
  `.\.venv\Scripts\python.exe laboratorio\build_lab.py package-status`.
- Todo desarrollo nuevo de utilidades, probes, llamadas API, scraping de apoyo,
  parsers y validaciones debe hacerse en Python usando librerias de Python
  estandar o dependencias declaradas del proyecto. PowerShell, `curl` u otros
  comandos manuales pueden servir para diagnostico puntual, pero no deben quedar
  como mecanismo principal reproducible del proyecto.
- Si aparece una decision de fase o modelo de datos, actualizar `agents.md`, no
  crear un documento paralelo.
- Si aparece una hipotesis pendiente de comportamiento, registrarla o actualizarla
  en `hypotheses_to_validate.md`, no en un listado paralelo.
- No convertir una observacion de Tenable VM, documentacion generica de Nessus o
  inferencia propia en comportamiento de Tenable.sc sin prueba en laboratorio o
  fuente oficial aplicable a Tenable.sc.
- Para validar estructura de `.audit`, campos de API, filtros, estados o
  comportamiento funcional, apoyarse siempre en documentacion incluida en el
  proyecto o enlazada desde `agents.md`. Si se usa scraping o busqueda web para
  acelerar la investigacion, el resultado debe acabar referenciado a una fuente
  oficial o a un artefacto local del proyecto.

### 2. Estado

Estado actual:

- El estado funcional vive en `agents.md`.
- Las hipotesis pendientes viven en `hypotheses_to_validate.md`.
- Las salidas de laboratorio viven en `outputs/`.
- Los tests viven en `tests/`.

Regla:

- No crear un `feature_list.json` con fases duplicadas mientras `agents.md`
  sea la fuente de verdad.
- Si mas adelante se necesita estado mecanico para agentes, debe referenciar IDs
  de `agents.md` y no redefinir fases.

### 3. Verificacion

Comando de verificacion local:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\harness_check.ps1
```

Debe comprobar como minimo:

- estructura basica del proyecto;
- disponibilidad de `.venv` y de `.\.venv\Scripts\python.exe`;
- ejecucion de tests unitarios;
- ayuda del CLI principal.

Cuando una utilidad toque Tenable.sc real:

- primero ejecutar en modo no destructivo si existe;
- guardar comando usado;
- revisar que los resultados tienen sentido funcional;
- documentar errores conocidos.

Cuando una funcionalidad dependa de comportamiento no confirmado:

- crear primero una prueba de laboratorio o una consulta de diagnostico;
- si se usa el laboratorio, seguir `laboratorio/README.md`;
- registrar campos observados y comando usado;
- no cerrar la funcionalidad hasta que el comportamiento este confirmado o la
  dependencia se elimine del diseno.

### 4. Scope

Reglas de alcance:

- Una funcionalidad nueva cada vez.
- No avanzar de Fase 1A a 1B, ni a Splunk, sin validacion explicita.
- Las utilidades que modifiquen Asset Lists deben tener `--dry-run`.
- Las utilidades repetibles deben recibir configuracion declarativa.
- Los cambios de modelo de datos bloquean el avance hasta resolver la duda.
- Las hipotesis solo pueden generar pruebas; no pueden convertirse en reglas de
  negocio, campos obligatorios o filtros definitivos.

### 5. Ciclo de sesion

Inicio:

1. Leer `agents.md`.
2. Leer `ESTANDARES_ADOPTADOS.md` si se va a implementar una utilidad nueva.
3. Identificar si la tarea usa solo comportamiento confirmado o si depende de
   una hipotesis pendiente consultando `hypotheses_to_validate.md`.
4. Ejecutar `.\scripts\harness_check.ps1` cuando se vaya a tocar codigo.
5. Si hay hipotesis pendiente, preparar primero la validacion de laboratorio.
6. Identificar una unica funcionalidad activa.

Ejecucion:

1. Implementar con cambios pequenos.
2. Mantener secretos fuera de codigo y docs versionables.
3. Si la tarea depende de comportamiento no confirmado, ejecutar solo pruebas o
   diagnosticos hasta confirmarlo.
4. Convertir diagnosticos utiles en scripts Python reproducibles cuando vayan a
   repetirse o sustenten una decision del proyecto.
5. Anadir o ajustar tests si cambia logica reusable.
6. Ejecutar verificacion.

Cierre:

1. Resumir archivos cambiados.
2. Indicar comandos de prueba ejecutados.
3. Registrar limitaciones o pruebas no ejecutadas.
4. Si hay una decision nueva de proyecto, actualizar `agents.md`.
5. Si se valida o rechaza una hipotesis, actualizar primero
   `hypotheses_to_validate.md`; despues promover solo la decision confirmada a
   `agents.md` para decisiones/contexto de proyecto o a
   `ESTANDARES_ADOPTADOS.md` para patrones tecnicos.
6. Tras documentar una validacion, ejecutar el ciclo Git para no perder
   contexto: `git status`, `git add`, `git commit` y `git push`.

## Aplicacion a utilidades Tenable.sc

Para nuevas utilidades:

- CLI estable.
- Configuracion en JSON cuando haya tareas repetibles.
- Cliente Tenable.sc compartido o patron comun.
- Parsers y normalizadores con tests.
- `--dry-run` para modificaciones.
- Backup o registro de estado previo antes de actualizar objetos.
- Outputs en carpeta dedicada.

Para llamadas de Asset Lists:

- Expresar origen con `'Nombre [ID]'`.
- Expresar destino con un campo explicito como `asset_id_to_change`.
- Usar Asset List como unidad minima de alcance; no sustituirlo por IP como
  agrupacion funcional.
- Filtrar por `assetID` o asset math. El filtro `ip` queda reservado a fallback
  tecnico documentado cuando un Asset List estatico falle por artefactos internos.
- Usar `sumip` cuando el objetivo sea obtener IPs.
- Usar siempre `sourceType=cumulative`.

## Politica de confirmacion

Estados permitidos:

- Confirmado: probado en laboratorio Tenable.sc o documentado por fuente oficial
  aplicable a Tenable.sc.
- Hipotesis: observado en Tenable VM, inferido desde Nessus o deducido desde un
  resultado parcial.
- Rechazado: probado y descartado.

Reglas:

- Solo `Confirmado` puede guiar implementacion funcional.
- `Hipotesis` puede guiar pruebas, diagnosticos y documentacion de pendientes.
- Si una hipotesis afecta modelo de datos, filtros de `/analysis`, identidad de
  controles o calculo de KPIs, la funcionalidad queda bloqueada hasta confirmar.
- Cuando una hipotesis pase a `Confirmado`, el cambio debe quedar versionado y
  subido a GitHub en el mismo ciclo de trabajo.

## Referencias analizadas

- https://github.com/walkinglabs/learn-harness-engineering
- https://github.com/walkinglabs/learn-harness-engineering/tree/main/skills/harness-creator
