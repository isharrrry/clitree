# Índice de documentación

[English](index.md) | [中文](index.zh-CN.md) | **Español**

> Parte de la documentación de **CliTree** — volver al [README](../README.es.md).

Cada documento tiene **tres versiones: inglés / chino / español**. La tabla siguiente da los enlaces en los
tres idiomas.

| Tema | Versiones | De qué trata |
|---|---|---|
| **Arquitectura** | [English](architecture.md) · [中文](architecture.zh-CN.md) · [Español](architecture.es.md) | La estructura de tres capas (core / ui / tools), la responsabilidad de cada módulo, el flujo de datos completo de una «carga → ejecución» y por qué `core` no depende de Qt |
| **Reglas de análisis** | [English](parsing-rules.md) · [中文](parsing-rules.zh-CN.md) · [Español](parsing-rules.es.md) | Canales de help y política de seguridad, los cuatro dialectos, modelo de bloques, criterio de obligatoriedad, orden de inferencia de controles, referencia de campos de `rules/default.rules.json` y cómo iterar las reglas |
| **Configuración** | [English](configuration.md) · [中文](configuration.zh-CN.md) · [Español](configuration.es.md) | El formato completo de `cli/<工具名>.json`: caché del análisis, varios perfiles, tus propias notas de argumentos, cuándo se escribe, respaldo y privacidad |
| **Modos de ejecución** | [English](execution-modes.md) · [中文](execution-modes.zh-CN.md) · [Español](execution-modes.es.md) | Los tres modos terminal nueva / segundo plano / silencioso, la semántica de detener, paso directo de argv y escape, la máquina de estados del icono de resultado y el bloqueo de comandos peligrosos |
| **Contribuir** | [English](contributing.md) · [中文](contributing.zh-CN.md) · [Español](contributing.es.md) | Entorno y dependencias, ejecutar pruebas, añadir fixtures, cambiar reglas, generar capturas, convenciones de commit y la lista de lo no verificado |
| **Árbol de dependencias** | [DEPENDENCY-TREE.md](DEPENDENCY-TREE.md) (generado automáticamente, un solo idioma) | Árbol de dependencias entre módulos desplegado desde las entradas, con numeración alfabética por nivel, generado por `tools/deps_tree.py` |

## Por dónde empezar

| Quieres… | Ve a |
|---|---|
| Ejecutarlo primero para verlo | [Inicio rápido del README](../README.es.md#inicio-rápido) |
| Que el panel de argumentos de alguna herramienta sea más cómodo (tipo de control incorrecto) | [Reglas de análisis § Inferencia de controles](parsing-rules.es.md) |
| Llevarte tus valores de argumentos y notas al cambiar de máquina | [Configuración](configuration.es.md) |
| Entender «qué pasa después de pulsar ejecutar» | [Modos de ejecución](execution-modes.es.md) |
| Ver los límites entre módulos antes de tocar código | [Arquitectura](architecture.es.md) |

## Sobre esta documentación

- Los **números de la documentación están medidos en esta máquina** (Python 3.10.12 ＋ PyQt5 5.15.6,
  Ubuntu 22.04), no son estimaciones; los comandos para obtenerlos están en el capítulo correspondiente y se
  pueden recalcular.
- Si al escribir código cambias el comportamiento, **cambia en la misma pasada la documentación en los tres
  idiomas** (ver [Contribuir](contributing.es.md)).
- Todo lo que no está verificado se marca de forma explícita; no se escribe como «debería funcionar».
