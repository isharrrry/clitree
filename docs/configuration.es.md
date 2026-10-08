# Configuración: `cli/<工具名>.json`

[English](configuration.md) | [中文](configuration.zh-CN.md) | **Español**

> Parte de la documentación de **CliTree** — volver al [README](../README.es.md).

Cada herramienta que hayas cargado deja un archivo de configuración en el **directorio de programa, dentro de
`cli/`**. Un solo archivo guarda tres cosas a la vez: la **caché del resultado del análisis**, **varios perfiles**
y **tus propias notas de argumentos**.

## Estructura del archivo

```jsonc
{
  "schema": 1,
  "cli": "ping",
  "updatedAt": "2026-10-08T16:01:00",

  "targets": {                        // 每个被解析过的命令路径一份缓存；"" = 根命令
    "": {
      "exe": "ping",
      "channel": ["--help"], "rc": 2, "grade": "full", "dialect": "usage-posix",
      "raw_sha256": "ffa24d0b…", "raw_bytes": 1866, "raw_head": "Usage\n  ping …",
      "parsedAt": "2026-10-08T16:01:00",
      "options": [ /* 参数树本体：names/desc/widget/required/… 全在 */ ],
      "subcommands": [ { "name": "sub", "desc": "…" } ]
    },
    "clone": { /* git clone 的那一份（点开它时才会写） */ }
  },

  "notes": {                          // ★ 你自己的参数说明（文件级：对本 CLI 所有配置生效）
    "-c": "我常用 2；外网改 1，别超过 5"
  },

  "activeProfile": "回环两次",
  "profiles": {                       // ★ 一个文件里的多个配置
    "默认":     { "note": "", "createdAt": "…", "updatedAt": "…", "values": {} },
    "回环两次": { "values": { "@0": "127.0.0.1", "-c": "2" } },
    "外网五次": { "note": "外网", "values": { "@0": "8.8.8.8", "-c": "5" },
                  "notes": { "-c": "外网限速，用 1" } }   // 配置级说明（覆盖文件级）
  }
}
```

- **Nombre de archivo**: al nombre de la herramienta se le quita la extensión y los caracteres no válidos se
  sustituyen por `_` (`C:/tools/my tool.exe` ⇒ `my_tool.json`).
- **Ubicación**: el `cli/` del directorio de programa, es decir, el mismo nivel donde está `pyproject.toml`.
  Cuando el directorio de programa no es escribible (instalación de solo lectura) se **vuelve automáticamente**
  al directorio de configuración del usuario (Linux `~/.config/clitree/cli/`, macOS
  `~/Library/Application Support/clitree/cli/`, Windows `%APPDATA%\clitree\cli\`), sin fallar.
- La escritura usa **archivo temporal ＋ reemplazo atómico**, así un corte de luz no deja un JSON a medias.

## Caché: la próxima vez no hace falta ejecutar help

- Al cargar un CLI se consulta primero `targets` de `cli/<工具>.json`: **si acierta, se renderizan directamente
  el árbol de argumentos y el formulario, sin ejecutar ni un solo help** (la barra de estado escribe «cargado
  desde la caché… analizado el …»);
- Para refrescar, pulsa **«Volver a analizar»**: solo entonces se ejecuta `--help` y, si sale bien, se
  sobrescribe la caché;
- Si no hay caché (primera carga) se sondea automáticamente y se escribe la caché;
- Cada análisis correcto actualiza la caché: una entrada para el comando raíz y otra para cada subcomando que
  abras (`targets["clone"]` y así).

La caché guarda el **árbol de argumentos en sí** (15 campos por argumento: `names`, `desc`, `value_token`,
`required`, `default`, `example`, `choices`, `widget`, `widget_reason`, `repeatable`, `group`, `position`…), por
eso sin conexión, en otra máquina o con la herramienta desinstalada la interfaz sigue listando todos los
argumentos — solo que ya no se pueden ejecutar.

`raw_sha256` / `raw_bytes` son la huella del texto de help de aquel momento (solo se guardan los primeros 2 KB
del original en `raw_head` para diagnóstico) y sirven para decidir «si el help ha cambiado».

## Varios perfiles (profiles)

En la parte superior derecha de la interfaz hay una línea: `配置： [下拉] [保存] [新配置名] [另存为…] [删除] [重新解析]`.

| Operación | Comportamiento |
|---|---|
| Cambiar en la lista | Todos los valores de argumentos de la derecha pasan a los de ese perfil; **antes de cambiar, el valor actual se guarda automáticamente en el perfil de origen** (no se pierde) |
| Guardar | Escribe los valores del formulario actual en el perfil actual |
| Guardar como | Copia el **valor actual** a un **perfil nuevo con nombre** (el perfil antiguo no se ve afectado) |
| Eliminar | Borra el perfil actual (aunque se borren todos, el archivo sigue siendo válido) |

Uso típico: en `ping` un perfil «bucle interno» (`127.0.0.1` / `-c 2`) ＋ un perfil «red externa»
(`8.8.8.8` / `-c 5`); en `tar` un perfil «empaquetar» ＋ un perfil «desempaquetar».

## Notas de argumentos (notes): nivel de archivo ＋ nivel de perfil

| Nivel | Dónde se escribe | Alcance | Cómo se crea |
|---|---|---|---|
| Archivo | `notes` | **Todos** los perfiles de ese CLI | **Doble clic** en la línea de la nota para editarla (por defecto se escribe aquí) |
| Perfil | `profiles.<名字>.notes` | **Solo ese perfil** | `set_note(key, text, scope="profile")` |

Prioridad: **nivel de perfil > nivel de archivo > texto original del help**. Vaciar el campo de entrada borra esa
entrada, se vuelve al nivel siguiente y, al final, al texto original del help.

En la interfaz tu nota se muestra como `✎ 你的说明　（原：help 原文）` — en color oscuro ＋ con la marca `✎` para
lo que has escrito tú, y el texto original del help queda entre paréntesis, así se distinguen de un vistazo.

## Migración y privacidad

- **Llevárselo**: basta con copiar todo el directorio `cli/` a la misma ubicación de otra máquina (los valores,
  las notas y la caché van juntos).
- **Privacidad**: dentro de `values` puede haber tu nombre de host, IP interna o rutas — sobre todo en
  argumentos posicionales como `@0`. Este repositorio **incluye `cli/` en el control de versiones a propósito**
  (la configuración acompaña al repositorio); si tus valores no son aptos para publicarse, basta con devolver a
  «ignorar» el fragmento comentado sobre `cli/` en `.gitignore` (el archivo lo explica).
- **Cambios de schema**: la parte superior del archivo tiene el campo `schema`; actualmente es `1`. Si el
  análisis falla o falta algún campo se continúa con un esqueleto vacío (**un archivo roto no hace fallar el
  programa**) y el siguiente guardado lo reescribe con una estructura válida.

## Recálculo

```bash
# 看当前有哪些工具配置、里面有什么
python3 - <<'PY'
import json, pathlib
for f in sorted(pathlib.Path("cli").glob("*.json")):
    d = json.loads(f.read_text())
    print(f.name, "| targets:", list(d["targets"]),
          "| profiles:", {k: v.get("values") for k, v in d["profiles"].items()},
          "| notes:", d.get("notes"))
PY
```
