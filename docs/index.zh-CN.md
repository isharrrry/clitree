# 文档索引

[English](index.md) | **中文** | [Español](index.es.md)

> 属于 **CliTree** 文档的一部分 —— 返回 [README](../README.zh-CN.md)。

每篇文档都有**英文 / 中文 / 西班牙文**三个版本。下表同时给出三语链接。

| 主题 | 语言版本 | 讲什么 |
|---|---|---|
| **架构** | [English](architecture.md) · [中文](architecture.zh-CN.md) · [Español](architecture.es.md) | 三层结构（core / ui / tools）、每个模块的职责、一次「加载 → 执行」的完整数据流、为什么 `core` 不依赖 Qt |
| **解析规则** | [English](parsing-rules.md) · [中文](parsing-rules.zh-CN.md) · [Español](parsing-rules.es.md) | help 通道与安全策略、四种方言、块模型、必填口径、控件推断顺序、`rules/default.rules.json` 字段参考、怎么迭代规则 |
| **配置** | [English](configuration.md) · [中文](configuration.zh-CN.md) · [Español](configuration.es.md) | `cli/<工具名>.json` 的完整格式：解析结果缓存、多个配置、你自己的参数说明、写回时机、回退与隐私 |
| **执行模式** | [English](execution-modes.md) · [中文](execution-modes.zh-CN.md) · [Español](execution-modes.es.md) | 新终端 / 后台 / 静默三种模式、停止语义、argv 直传与转义、结果图标状态机、危险命令拦截 |
| **参与开发** | [English](contributing.md) · [中文](contributing.zh-CN.md) · [Español](contributing.es.md) | 环境与依赖、跑测试、加 fixture、改规则、生成截图、提交约定、尚未验证的清单 |
| **依赖关系树** | [DEPENDENCY-TREE.md](DEPENDENCY-TREE.md)（自动生成，单语） | 从入口展开的模块依赖树，带层级字母编号，由 `tools/deps_tree.py` 生成 |

## 从哪开始

| 你想… | 去哪 |
|---|---|
| 先跑起来看看 | [README 快速开始](../README.zh-CN.md#快速开始) |
| 让某个工具的参数面板更顺手（控件类型不对） | [解析规则 § 控件推断](parsing-rules.zh-CN.md) |
| 换机器时把自己的参数值和说明带走 | [配置](configuration.zh-CN.md) |
| 搞清楚「点执行之后发生了什么」 | [执行模式](execution-modes.zh-CN.md) |
| 改代码前先看模块边界 | [架构](architecture.zh-CN.md) |

## 关于这些文档

- 文档里的**数字都是本机实测**（Python 3.10.12 ＋ PyQt5 5.15.6，Ubuntu 22.04），不是估计；
  取数命令写在相应章节里，可以自己复算。
- 写代码时如果改了行为，**请同趟改三语文档**（见 [参与开发](contributing.zh-CN.md)）。
- 尚未验证的东西一律显式标注，不写成「应该可以」。
