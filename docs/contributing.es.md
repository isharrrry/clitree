# Contribuir

[English](contributing.md) | [中文](contributing.zh-CN.md) | **Español**

> Parte de la documentación de **CliTree** — volver al [README](../README.es.md).

## Entorno

| Elemento | Valor (medido en esta máquina) |
|---|---|
| Intérprete | `python3` del sistema (medido 3.10.12; `requires-python >= 3.9`) |
| GUI | PyQt5 5.15.6 / Qt 5.15.3 (paquetes del sistema) |
| Pruebas | pytest 9.1.1 |

```bash
python3 -c "import PyQt5" || python3 -m pip install --user PyQt5
python3 -m pytest -q                 # 165 pruebas (160 pasan; 5 específicas de plataforma)
```

**No crear un venv** (medido en esta máquina: `python3 -m ensurepip` no existe ⇒ el venv no tiene pip, y además
el `sys.path` del venv no ve `/usr/lib/python3/dist-packages`, así que ni el PyQt5 del sistema se puede
importar). Cuando haga falta una dependencia extra, usa `python3 -m pip install --user <包>`.

Sin entorno gráfico (sin `DISPLAY` / `WAYLAND_DISPLAY`):

- Ejecutar pruebas: `QT_QPA_PLATFORM=offscreen python3 -m pytest -q` (`tests/conftest.py` ya lo configura por
  defecto);
- Abrir la ventana para ver la interfaz: `xvfb-run -a python3 -m clitree`;
- Generar capturas: `xvfb-run -a python3 tools/make_screenshots.py` (escribe en `screenshots/`).

## Mapa de pruebas

| Archivo | Cobertura |
|---|---|
| `tests/test_rules.py` | Carga de reglas, fusión en profundidad de las sobrescrituras del usuario, detección de JSON y expresiones regulares rotas |
| `tests/test_parser_blocks.py` | Modelo de bloques, los cuatro dialectos, criterio de obligatoriedad, análisis de las 29 fixtures una a una |
| `tests/test_parser_subcommands.py` | Sección de subcomandos (incluido el falso positivo de los nombres de columna de `lsblk` y el valor real de `git help -a`) |
| `tests/test_widgets.py` | Orden de inferencia de controles y cada excepción (`--[no-]`, repetible, `curl -b` no debe clasificarse como enumeración) |
| `tests/test_discovery.py` | Orden de canales, rc no fiable, comandos peligrosos rechazados, respaldo de páginas man, canales interactivos |
| `tests/test_lazy.py` | Al cargar solo 1 sondeo, al expandir 1 más, repetir 0, límite de profundidad, reintento tras fallo |
| `tests/test_executor.py` | Seguridad de argv, los tres modos, detener, adaptación de terminales |
| `tests/test_profiles.py` | Caché de `cli/<工具>.json`, varios perfiles, los dos niveles de notas, respaldo, archivos rotos |
| `tests/test_gui_smoke.py` | Crear la ventana en offscreen, cargar/expandir, tipos de control, doble clic en la nota, cambio de perfil, detener |

`tests/fixtures/help/*.txt` son **29 textos de help reales de máquina** (con formas en chino, páginas man,
argparse, bloques de dos líneas, opciones largas de GNU, ping de Windows en inglés/chino, etc.); `tests/fixtures/fakecli.py` es un CLI falso
controlable (permite fijar el código de retorno, escribir en stderr, dormir mucho) que usan las pruebas del
ejecutor y de la GUI; **nunca se usan comandos reales para verificaciones destructivas**.

## Cambiar las reglas de análisis

Ver [Reglas de análisis § Cómo iterar las reglas](parsing-rules.es.md). Tres disciplinas:

1. Validar con texto real usando `--parse --help-file`, no corregir expresiones regulares de memoria;
2. Después de cambiar hay que ejecutar `python3 -m clitree --check-rules` (distinto de 0 significa roto);
3. Añadir o actualizar la prueba correspondiente; los valores esperados de `fixtures` deben **recalcularse en el
   momento**, no vale copiar una lectura antigua como «aprobado».

## Añadir una fixture

```bash
<pick-a-real-cli> --help > tests/fixtures/help/<name>.help.txt
# 含空格/子命令的写清通道，例如 git clone -h
```

Y añadir la aserción en las pruebas (número de elementos, forma o tipo de control). La muestra debe ser el texto
original capturado de la máquina real, sin escribirlo a mano ni retocarlo.

## Cambiar la interfaz

- Qt solo puede aparecer en `clitree/ui/`, y además **`ui/qt.py` es el único archivo que importa Qt** (al cambiar
  de enlace solo se toca ese);
- En `core/` está prohibido importar Qt (así no se podría probar sin cabecera);
- Al añadir comportamiento de interfaz, añade una aserción en `test_gui_smoke.py` — allí ya hay un conjunto
  reutilizable de fixtures `MainWindow(probe_fn=..., profile_root=tmp_path)` que no contamina el `cli/` real.

## Convenciones de documentación

- Cada documento en tres idiomas: `X.md` (inglés), `X.zh-CN.md` (chino), `X.es.md` (español), manteniendo en la
  cabecera la línea de cambio de idioma `[English](X.md) | [中文](X.zh-CN.md) | [Español](X.es.md)`;
- **Si cambias el comportamiento, cambia en la misma pasada los tres idiomas** (si no puedes, deja al menos un
  TODO; no dejes que los tres idiomas se contradigan);
- Los números de la documentación o permiten un comando de recálculo o llevan escrito explícitamente «no
  verificado».

## Convenciones de commit

- El mensaje usa un título de una línea con prefijo (`feat:` / `fix:` / `docs:` / `test:` / `refactor:` /
  `chore:`) y el cuerpo explica el «por qué»;
- **No hacer commit** de `__pycache__/`, `.pytest_cache/`, `*-session.jsonl` (ya están en `.gitignore`);
- `cli/` **sí** entra en el repositorio (la configuración acompaña al repositorio); si los valores que contiene
  no son aptos para publicarse, cambia antes `.gitignore` y luego haz el commit;
- En cambios grandes, adjunta lecturas (pruebas ejecutadas, capturas, salida de `--parse`) en lugar de «debería
  estar bien».

## Lista de lo no verificado (NOINFO)

Está aquí para que nadie crea que ya se cumple:

- **Windows / macOS**: el análisis y la ejecución de `ping` y la suite de pruebas se han ejercitado en Windows 11
  (2026-10, ver la tabla del README); el canal `-?`, abrir terminal con `cmd start` / `osascript` y el
  empaquetado con PyInstaller siguen **sin medir**;
- **Si el modo de terminal nueva abre realmente una ventana**: esta máquina no tiene entorno gráfico, solo se
  puede leer que el botón queda en `launched`;
- **Empaquetado**: no se ha hecho ninguna verificación de empaquetado con PyInstaller;
- **Estabilidad a largo plazo con locale distinto del chino**: solo se ha probado el locale de esta máquina y el
  cambio a `LC_ALL=C`.

Si completas alguno de estos puntos, **borra la entrada correspondiente de aquí y adjunta la lectura** — dejar
una frase falsa en la documentación hace mucho más daño que dejar una frase «no verificado».
