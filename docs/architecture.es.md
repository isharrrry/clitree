# Arquitectura

[English](architecture.md) | [中文](architecture.zh-CN.md) | **Español**

> Parte de la documentación de **CliTree** — volver al [README](../README.es.md).

## Tres capas, una regla dura

```
clitree/
├── core/      纯逻辑：解析、规则、控件推断、探测、懒加载、执行、落盘   ← 不 import Qt
├── ui/        Qt 界面；**只有 ui/qt.py 一个文件 import Qt**
├── rules/     default.rules.json（解析规则的唯一真相源）
tests/         158 项测试（含 offscreen GUI 冒烟）
tools/         生成依赖树 / 生成界面截图的脚本
cli/           每个工具的配置文件（缓存 ＋ 多个配置 ＋ 你的说明）
```

**Regla dura**: dentro de `core` no aparece `PyQt5`/`PySide6`. Esto tiene dos ventajas prácticas:
① la lógica de análisis y de ejecución se puede probar unitariamente en un entorno sin gráficos (el CI de esta
máquina es exactamente `QT_QPA_PLATFORM=offscreen` ＋ pytest puro);
② si en el futuro hay que pasar de PyQt5 a PySide6 (por ejemplo por la LGPL), **solo se cambia el archivo
`ui/qt.py`**.

## Responsabilidad de los módulos

| Módulo | Responsabilidad | Punto clave |
|---|---|---|
| `core/model.py` | Estructuras de datos `ParamSpec` / `CommandNode` / `ParseResult` | Con `to_dict/from_dict`; la caché del archivo de configuración es exactamente esto |
| `core/rules.py` | Cargar / validar / fusionar en profundidad el archivo de reglas | Tus cambios se escriben en `rules.user.json`, **sin tocar las reglas que vienen con el paquete** |
| `core/parser.py` | Texto de help → argumentos y subcomandos estructurados | Modelo de bloques; detección de dialecto; criterio de obligatoriedad |
| `core/widgets.py` | Inferencia de argumento → tipo de control | Cada decisión produce un `widget_reason` (visible en la interfaz) |
| `core/discovery.py` | Sondear los canales de help (incluida la política de seguridad) | Los comandos peligrosos se rechazan directamente; `-h` debe estar declarado antes; no se mira el rc, solo el contenido |
| `core/lazy.py` | Árbol con carga diferida | Al cargar solo salen 2 niveles; se sondea al expandir un nodo |
| `core/executor.py` | Los tres modos de ejecución ＋ detener | La lista argv se pasa directamente, nunca se compone una cadena de shell |
| `core/terminals.py` | Adaptación de «abrir terminal nueva» en las tres plataformas | Un conjunto de comandos para Linux / macOS / Windows |
| `core/store.py` | Directorio de configuración, comandos recientes | Calcula la ruta según la convención de la plataforma (`XDG_CONFIG_HOME` / `APPDATA` / `Library/Application Support`) |
| `core/profiles.py` | Lectura y escritura de `cli/<工具名>.json` | Caché del análisis ＋ varios perfiles ＋ notas de argumentos |
| `ui/qt.py` | Capa de adaptación fina de Qt | El único lugar del proyecto que importa Qt |
| `ui/main_window.py` | Montaje de la ventana principal, arrastrar y soltar, carga, línea de perfiles, ejecución | Las llamadas de vuelta de los hilos vuelven al hilo principal por una cola para refrescar la interfaz |
| `ui/tree_panel.py` | Árbol izquierdo | Los subcomandos se marcan «sin expandir»; el sondeo se dispara al abrirlos |
| `ui/param_form.py` | Formulario de argumentos de la derecha | Ordenación, fábrica de controles, nota siempre visible y edición con doble clic |
| `ui/run_bar.py` / `ui/icons.py` | Los tres botones de ejecución y los iconos de estado | Durante la ejecución pasa a «■ Detener»; cada botón recuerda su último resultado |
| `ui/log_panel.py` | Zona de registro | **Solo escribe el modo de segundo plano** |

## Flujo de datos completo de una «carga → ejecución»

```
用户输入 / 拖入一个 CLI
        │
        ├─ profiles.cached_node(cli)  ── 命中 ⇒ 直接渲染树与表单（**不探测**）
        │                                 状态栏写「已从缓存载入…解析于 …」
        │
        └─ 未命中 ⇒ discovery.probe(exe, rules, node_path)
                     ├─ 危险命令？ ⇒ 立即拒绝（reason 写进状态栏）
                     ├─ 交互式命令（gdb 等）⇒ 走专用通道 `-batch -ex "help all"`
                     └─ 否则按通道顺序 --help → -h → /? → -? → help → -help
                          逐条真跑，**以输出内容判定成败**（rc 完全不可信）
                          │
                          ▼
                    parser.parse_help(text, rules)  →  ParamSpec 列表 ＋ 子命令名单
                          │
                          ▼
                    widgets.infer_widget(spec)      →  控件类型 ＋ 推断依据
                          │
                          ├─ profiles.save_node(...)     把解析结果写进 cli/<工具>.json
                          └─ lazy.TreeLoader._fill(...)  只长 2 层，其余标 pending
                          │
                          ▼
                    TreePanel.show_root()  ＋  ParamForm.build()  （位置参数置顶 → 必填 → 其余）
                          │
                          用户填值 / 选配置（profiles.get_profile → form.set_value）
                          ▼
                    executor.build_argv(exe, node, values)   ← argv 列表，不经 shell
                          │
        ┌─────────────────┼──────────────────────────┐
        ▼                 ▼                          ▼
  新终端（terminals）  后台（Popen + 线程泵）      静默（Popen，不读输出）
  拿不到 rc ⇒          stdout/stderr 逐行进日志    日志区零新增行
  「已启动」           结束按 rc 判 ok / fail       结束按 rc 判 ok / fail
```

## Por qué la caché y los perfiles en el mismo archivo

`cli/<工具名>.json` guarda tres clases de cosas a la vez:

- `targets`: un resultado de análisis por **cada ruta de comando analizada** (el comando raíz es `""`, `git
  clone` es `"clone"`);
- `profiles`: los **varios perfiles** de la misma herramienta (valores de argumentos para distintas
  máquinas/escenarios);
- `notes`: **tus propias notas de argumentos** (nivel de archivo) ＋ cada perfil puede volver a sobrescribirlas.

La razón es que comparten vida por naturaleza: el árbol de argumentos de una herramienta, los valores que le
das y tu comprensión de ella deberían mudarse juntos al cambiar de máquina.
Detalles en [Configuración](configuration.es.md).

## Ver las dependencias reales entre módulos

`tools/deps_tree.py` analiza los import con AST y genera un árbol de dependencias con **numeración alfabética por
nivel**:

```bash
python3 tools/deps_tree.py            # 打印
python3 tools/deps_tree.py --out docs/DEPENDENCY-TREE.md
```

La numeración tiene la forma `[BACD]` ＝ segundo de la primera capa → primero de la segunda → tercero de la
tercera → cuarto de la cuarta; la segunda aparición del mismo archivo solo escribe `↩ 见 [首次编号]` y no vuelve
a desplegarse. La instantánea actual está en [DEPENDENCY-TREE.md](DEPENDENCY-TREE.md).
