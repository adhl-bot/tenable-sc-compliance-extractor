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
  `agents.md`.

## Subsistemas adoptados

### 1. Instrucciones

Artefactos actuales:

- `agents.md`: fuente de verdad del proyecto.
- `README.md`: guia corta de uso.
- `ESTANDARES_ADOPTADOS.md`: patrones tecnicos reutilizables.
- `HARNESS_DESARROLLO.md`: protocolo de trabajo controlado.

Regla:

- Antes de tocar codigo, leer `agents.md` y el estandar tecnico que aplique.
- Si aparece una decision de fase o modelo de datos, actualizar `agents.md`, no
  crear un documento paralelo.
- No convertir una observacion de Tenable VM, documentacion generica de Nessus o
  inferencia propia en comportamiento de Tenable.sc sin prueba en laboratorio o
  fuente oficial aplicable a Tenable.sc.

### 2. Estado

Estado actual:

- El estado funcional vive en `agents.md`.
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
- disponibilidad de Python;
- ejecucion de tests unitarios;
- ayuda del CLI principal.

Cuando una utilidad toque Tenable.sc real:

- primero ejecutar en modo no destructivo si existe;
- guardar comando usado;
- revisar que los resultados tienen sentido funcional;
- documentar errores conocidos.

Cuando una funcionalidad dependa de comportamiento no confirmado:

- crear primero una prueba de laboratorio o una consulta de diagnostico;
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
   una hipotesis pendiente.
4. Ejecutar `.\scripts\harness_check.ps1` cuando se vaya a tocar codigo.
5. Si hay hipotesis pendiente, preparar primero la validacion de laboratorio.
6. Identificar una unica funcionalidad activa.

Ejecucion:

1. Implementar con cambios pequenos.
2. Mantener secretos fuera de codigo y docs versionables.
3. Si la tarea depende de comportamiento no confirmado, ejecutar solo pruebas o
   diagnosticos hasta confirmarlo.
4. Anadir o ajustar tests si cambia logica reusable.
5. Ejecutar verificacion.

Cierre:

1. Resumir archivos cambiados.
2. Indicar comandos de prueba ejecutados.
3. Registrar limitaciones o pruebas no ejecutadas.
4. Si hay una decision nueva de proyecto, actualizar `agents.md`.

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

## Referencias analizadas

- https://github.com/walkinglabs/learn-harness-engineering
- https://github.com/walkinglabs/learn-harness-engineering/tree/main/skills/harness-creator
