# Reglas de análisis

[English](parsing-rules.md) | [中文](parsing-rules.zh-CN.md) | **Español**

> Parte de la documentación de **CliTree** — volver al [README](../README.es.md).

Este capítulo explica «cómo el texto de help se convierte en un árbol de argumentos», dónde se escriben las
reglas, cómo cambiarlas y cómo validarlas.

## 1. Canales: primero obtener el texto de help

Orden: `--help` → `-h` → `/?` → `-?` → `help` → `-help`, se ejecutan de verdad uno a uno y se para al primer
acierto.

**La decisión se toma solo por el contenido de la salida; el rc no es fiable en absoluto** — esto no es teoría,
está medido:

| Comando | rc | Situación real |
|---|---|---|
| `git clone -h` | **129** | Imprimió la ayuda breve completa |
| `ping -h` | **2** | Imprimió la ayuda completa de 20 argumentos |
| `ip --help` / `ssh --help` | **255** | Hay salida (ssh solo una línea de usage) |
| `npm --help` | 1 | Hay salida |
| `dotnet --help` | 0 | Tarda 314 ms en volver (por eso el tiempo de espera por canal es de 5 segundos) |

**Clasificación por calidad**: el texto obtenido se reparte en tres grados — `full` (≥3 bloques de argumentos),
`weak` (hay contenido pero la estructura es débil) y `usage-only` (solo la línea de uso).
En la interfaz, `weak` / `usage-only` avisan explícitamente de que «la ayuda es demasiado escueta, el resultado
del análisis puede estar incompleto»; **nunca se toma el `nslookup --help` de 27 bytes como «este comando no
tiene argumentos»**.

Distribución de los 105 comandos reales de esta máquina: `full` **76**, `weak` **15**, `usage-only` **14**;
cero bloques (no se obtienen argumentos) 27.

## 2. Política de seguridad (escrita en el archivo de reglas)

1. **Los comandos peligrosos nunca se sondean ni se ejecutan**: `shutdown`, `reboot`, `halt`, `poweroff`,
   `init`, `telinit`, `mkfs*`, `dd`, `fdisk`, `parted`, `mkswap`, `swapon`, `swapoff`, `wipefs`, `blkdiscard`,
   `passwd`, `userdel`, `groupdel`, `chpasswd`, `visudo`, `at`, `batch` — 24 en total, se rechazan en cualquier
   entrada.
2. **`-h` debe estar declarado antes**: solo se permite ejecutar `-h` cuando el texto de `--help` escribe
   `-h … help` (o el comando está en la lista blanca medida).
   Motivo: `sort -h`, `df -h`, `du -h`, `free -h` **no son help**, son ejecutar el comando sin condiciones.
3. **Nunca paginar, nunca interactuar**: stdin cerrado, `PAGER`/`MANPAGER`/`GIT_PAGER`/`SYSTEMD_PAGER` todos a
   `cat`, tiempo de espera de 5 segundos por canal y límite de salida de 256 KB (medido con los 105 de esta
   máquina: 0 tiempos de espera agotados, 0 bloqueos).
4. **Los CLI interactivos usan un canal propio**: `gdb --help` solo tiene 3 071 B, mientras que
   `gdb -batch -ex "help all"` tiene **111 781 B (36 veces)**, y además con una sintaxis completamente distinta
   (`awatch -- Set an access watchpoint…` ＋ agrupación por `Command class:`).
   En el archivo de reglas se configura `interactiveChannels` por nombre de comando.

## 3. Los cuatro dialectos

| Dialecto | Criterio de detección | Ejemplo | Forma de analizar |
|---|---|---|---|
| `man-page` | La primera línea tiene la forma `GIT-CLONE(1)` | `git clone --help` | No cuenta como éxito, se vuelve a `-h` |
| `dashdash-interactive` | Contiene `Command class:` o ≥5 líneas `nombre -- descripción` | `gdb -batch -ex "help all"` | Se analiza con la sintaxis de gdb (en esta máquina la prueba retrospectiva acierta 170/1531 líneas) |
| `usage-posix` | Tiene `usage:` / `用法:` / `使用情况:` | La gran mayoría | Modelo de bloques |
| `blocks-only` | No hay línea usage pero sí bloques de argumentos | `curl --help all` | También usa el modelo de bloques |

## 4. Modelo de bloques (el núcleo del analizador)

**La unidad es el «bloque», no la «línea».** Formas medidas:

```
  -v, --version                       ← 选项名单独一行
          Print the pnpm version      ← 说明在下一行、缩进更深 ⇒ 并入同一块

  -A, --catenate, --concatenate   追加 tar 文件至归档     ← 一个选项三个别名
      --occurrence[=NUMBER]  仅处理归档中每个文件的第 NUMBER
                             --diff, --extract 或是 --list   ← 续行里的词**不是**新参数
```

Puntos clave de las reglas (todos en la sección `optionBlock` de `clitree/rules/default.rules.json`):

- `joinContinuation: true` ＋ `continuationMinExtraIndent: 2`: las líneas con más sangría se unen al bloque
  anterior;
- `nameToken`: `--[A-Za-z][\w-]*` o `-[A-Za-z][\w-]*` — **hay que admitir nombres largos con un solo guion**
  (el `-pass-exit-codes` de GNU);
- `valueToken` exige estar **pegado al nombre del argumento**: `-c <count>` es un valor, mientras que el
  `SO_DEBUG` de `-d      use SO_DEBUG socket option` es solo una palabra de la descripción (se clasificó mal
  como valor y ya está corregido);
- la forma `--[no-]color` se normaliza a `--color` y se marca como «triestado».

Los títulos de sección usan **decisión estructural primero ＋ lista de palabras como respaldo**: los títulos son
un conjunto abierto (medido: además de `options`/`usage` hay títulos de una sola vez como
`main operation mode` o `valid arguments for -d`), así que no se puede agotar la lista de palabras.

## 5. Subcomandos: no es fiable, por eso carga diferida

| Muestra | Elementos extraídos | Verdadero o falso |
|---|---|---|
| `pnpm --help` | 91 | **Verdadero** (pnpm tiene realmente muchos comandos y no incluye falsos positivos como `verbose`/`color`) |
| `git help -a` | 141 | Verdadero |
| `git --help` (chino) | 22 | Verdadero (lista agrupada; los títulos de grupo no cierran la sección) |
| `lsblk --help` | 0 | Verdadero (`Available output columns:` son **nombres de columna**; se extrajeron por error como 54 subcomandos y ya se bloquean con una condición de respaldo) |

Por eso: **al cargar solo salen 2 niveles** (los argumentos de este comando ＋ la lista de subcomandos de primer
nivel, con los subcomandos marcados «sin expandir»); solo al abrir un subcomando se ejecuta su help. Además hay
un botón «Expandir todo» (límite de 3 niveles).

## 6. Criterio de obligatoriedad

- **Si hay línea usage** ⇒ los argumentos **se tratan siempre como opcionales** (también funcionan sin pasarlos)
  y solo los **argumentos posicionales** se dividen en obligatorio/opcional (escritos fuera de `[]` en el usage
  ⇒ obligatorio);
- **Si no hay línea usage** ⇒ se muestra «？sin determinar», sin fingir que se sabe;
- Orden en la interfaz: **posicionales arriba → el resto de obligatorios → los demás en el orden original del
  help**.

Este criterio es fruto de una corrección: en `ping [options] <destination>` solo el argumento posicional cae en
la posición obligatoria, y la implementación inicial trataba «el argumento no mencionado en el usage» como «sin
marcar», con lo que los 32 argumentos de ping quedaban todos con `[未标注]`.

## 7. Orden de inferencia de controles

La decisión va de arriba abajo y para al primer acierto (implementado en `core/widgets.py`; **cada decisión
produce un motivo de la inferencia** y en la interfaz se puede cambiar el tipo con el botón derecho):

| Orden | Condición | Control |
|---|---|---|
| 1 | Sobrescritura del usuario (`widgets.overrides`) | Lo que indique el usuario |
| 2 | El help escribe la forma `--[no-]xyz` | Lista desplegable de triestado |
| 3 | La descripción contiene `...` / `multiple times` | Lista multivalor |
| 4 | El bloque **no tiene marca de valor** | **Casilla de verificación** (＋ explicación del help) |
| 5 | La descripción contiene `one of` y la forma es `<a\|b\|c>` | **Lista desplegable editable** |
| 6 | El nombre del valor o la descripción acierta en `numericWords` (`count`/`ttl`/`timeout`…) | Campo numérico |
| 7 | Acierta en `pathWords` (`file`/`dir`/`interface`…) | Campo de texto ＋ «Examinar…» |
| 8 | Otros | Campo de texto (marcado «sin determinar», modificable) |

⚠️ **No tomar `curl -b <data|filename>` como enumeración**: eso es una «forma del valor», no un conjunto; en las
reglas hay una lista negra `reject`.
Medido: de los 105 comandos reales, los que dan explícitamente un conjunto de valores en el help son **solo
`ping -M` / `-T`, dos sitios** — por eso la lista desplegable es siempre **editable** y, si no se extrae, no se
inventan candidatos.

## 8. Referencia del archivo de reglas

`clitree/rules/default.rules.json` (JSON estricto, `rulesVersion: 3`):

| Sección | Función |
|---|---|
| `evidence` | Los números medidos en los que se basan las reglas (la distribución de los 105 comandos, etc.), útil para comparar más adelante |
| `dialects.detect` | Orden y expresiones regulares de detección de dialecto |
| `helpChannels` | Orden de canales, requisito de declaración de `-h`, lista blanca medida, canales interactivos, los 24 comandos peligrosos, tiempos de espera y límites |
| `segments` | Lista de palabras para las secciones (decisión estructural primero; la lista solo sirve de respaldo) |
| `optionBlock` | Unión de bloques y expresiones regulares de nombres/valores |
| `widgets` | Lista de palabras para la inferencia de controles, tabla de enumeraciones y sobrescrituras |
| `subcommands` | `initialDepth: 2`, `lazyExpand`, `maxDepth: 3`, condiciones de respaldo |
| `manPage` / `locale` / `limits` | Respaldo de páginas man, sondeo preferente con `LC_ALL=C`, límites de concurrencia y de registro |

**Tus cambios no van al archivo del repositorio**: se escriben en `~/.config/clitree/rules.user.json` (o el
directorio equivalente de la plataforma) y se **fusionan en profundidad** sobre las reglas por defecto (cambiar
el tipo de control con el botón derecho en la GUI va por este camino).

## 9. Cómo iterar las reglas

```bash
# 1) 改规则
$EDITOR clitree/rules/default.rules.json
python3 -m clitree --check-rules          # 坏 JSON / 坏正则立刻报出来（非 0 退出）

# 2) 拿真实命令看效果
python3 -m clitree --parse ping
python3 -m clitree --parse --help-file /tmp/some-tool--help.txt

# 3) 跑回归（fixtures 是 27 条真机 help 文本）
python3 -m pytest tests/test_parser_blocks.py tests/test_widgets.py -q
```

Para añadir una fixture nueva: `<命令> --help > tests/fixtures/help/<命令>.help.txt`, se mantiene el nombre de
archivo `<工具>.help.txt` y se añade una aserción en las pruebas (forma, número de elementos o tipo de control).
