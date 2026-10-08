# Modos de ejecución

[English](execution-modes.md) | [中文](execution-modes.zh-CN.md) | **Español**

> Parte de la documentación de **CliTree** — volver al [README](../README.es.md).

## Los tres modos

| Modo | Implementación | Zona de registro | Código de retorno | ¿Se puede detener? |
|---|---|---|---|---|
| **Ejecución en terminal nueva** | `terminals.build_terminal_argv()` elige la terminal de la plataforma (Linux: `gnome-terminal`/`xfce4-terminal`/`konsole`/`xterm`/`x-terminal-emulator`; macOS: `osascript` controlando Terminal.app; Windows: `wt.exe` o `cmd /c start`) | No vuelve (lo muestra la propia terminal) | **No se obtiene** | **No** (ventana externa) |
| **Ejecución en segundo plano** | `subprocess.Popen` ＋ un hilo que lee stdout+stderr línea a línea | Se escribe en tiempo real línea a línea | Sí | Sí |
| **Ejecución silenciosa** | `Popen` pero enviando stdout/stderr a `/dev/null` | **No escribe ni una línea** | Sí | Sí |

Criterio de diseño: **si no se obtiene el código de retorno, no se determina éxito o fallo**. El modo de terminal
nueva solo marca el botón como «iniciado en la terminal»; no finge éxito (ni tampoco finge fallo).

## Detener

Durante la ejecución, el texto del botón de ese modo pasa a **`■ Detener`**; un segundo clic lo termina:

```
RunHandle.stop()  →  terminate()  →  等最多 3 秒  →  仍在 ⇒ kill()
```

- El estado del resultado se registra como **`stopped`** (neutro, no cuenta como fallo) y el icono del botón
  cambia al cuadrado de detención;
- Si se detiene el modo de segundo plano, la zona de registro conserva la salida ya producida;
- Detener el modo silencioso tampoco escribe registro;
- Llamar a `stop()` sobre una ejecución ya terminada es una **operación vacía** (no cambia el estado ni lanza
  excepciones).

## Máquina de estados del icono de resultado

Cada botón recuerda **de forma independiente** su propio último resultado:

| Estado | Cuándo | Icono |
|---|---|---|
| `idle` | Nunca se ha ejecutado | ▶ |
| `running` | Se está ejecutando (el texto del botón pasa a «■ Detener») | ↻ |
| `ok` | Código de retorno 0 | ✓ |
| `fail` | Código de retorno distinto de 0 | ✗ |
| `launched` | Terminal nueva ya iniciada (sin código de retorno) | 方框 |
| `stopped` | El usuario pulsó detener | ■ |
| `error` | Fallo al iniciar (por ejemplo, no se encuentra emulador de terminal) | ⚠ |

## Paso directo de argv: nunca a través del shell

Los argumentos se entregan siempre al proceso hijo como **lista**:

```python
argv = build_argv(exe, node, values)
# 例：{"--verbose": True, "--count": "3", "--output": "a b; rm -rf /", "@0": "host"}
#   ⇒ ["ping", "--verbose", "--count", "3", "--output", "a b; rm -rf /", "host"]
```

Un valor como `a b; rm -rf /` **sigue siendo un único elemento de argv** y no se interpreta como separador de
comandos (hay una prueba que lo fija).

Solo en el camino de «abrir terminal nueva» hay que componer una línea de comando, y solo entonces se aplica el
escape: en POSIX con `shlex.join`, en Windows envolviendo en `"…"` y escapando las comillas internas.

Reglas de valor de `build_argv`:

| Estado del formulario | Resultado |
|---|---|
| Casilla sin marcar / lista vacía / campo numérico en «（不传）」 | **No se pasa ese argumento** |
| Casilla marcada | Se pasa el nombre largo (si no hay nombre largo, el corto) |
| Con valor | Se pasan dos elementos `名字 值` |
| Repetible (lista multivalor) | Cada valor se pasa una vez como `名字 值` |
| Argumento posicional | Se añade al final en orden (sin nombre) |

## Comandos peligrosos: dos barreras

1. **Antes de sondear**: `discovery.probe()` al ver uno de los 24 como `shutdown`/`dd`/`mkfs*` devuelve el
   rechazo directamente, **sin arrancar ni un proceso**;
2. **Antes de ejecutar**: `MainWindow.run()` vuelve a consultar la misma lista (así ni un sondeo que venga de la
   caché ni un sondeo falso inyectado pueden esquivarla) y escribe el motivo en la barra de estado.

Medido en la interfaz: al cargar `/sbin/shutdown` ⇒ el árbol y el formulario quedan vacíos y la barra de estado
escribe «安全策略：shutdown 属于危险命令，CliTree 不探测也不执行它» (captura `08-dangerous-refused.png`).

## Recálculo

```bash
python3 -m pytest tests/test_executor.py -q      # 三模式 ＋ 停止 ＋ argv 安全
python3 - <<'PY'
import sys; sys.path.insert(0, ".")
from clitree.core import executor, terminals
print(terminals.build_terminal_argv(["echo", "hi there"], platform="linux"))
print(executor.build_argv("ping", __import__("clitree.core.model", fromlist=["CommandNode"]).CommandNode(
    name="ping", path=["ping"], options=[]), {}))
PY
```
