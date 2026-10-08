```
库根：/home/links-dev/netTest/GitProj/clitree
第一层（入口）：15 个　　树行数：84
编号＝每层在同一父节点下的序号字母（A=第 1 个）连写，如 [BACD]；同一文件第二次出现只给引用

[A]         pyproject.toml   ← 打包／入口声明（console_scripts）
    [AA]        clitree/__main__.py   ← 入口点 → clitree.__main__:main
        [AAA]       clitree/app.py
            [AAAA]      clitree/ui/main_window.py
                [AAAAA]     clitree/core/executor.py
                    [AAAAAA]    clitree/core/terminals.py
                [AAAAB]     clitree/core/lazy.py
                    [AAAABA]    clitree/core/discovery.py
                        [AAAABAA]   clitree/core/parser.py
                            [AAAABAAA]  clitree/core/model.py
                            [AAAABAAB]  clitree/core/widgets.py
                    [AAAABB]    clitree/core/model.py   ↩ 见 [AAAABAAA]
                    [AAAABC]    clitree/core/parser.py   ↩ 见 [AAAABAA]
                [AAAAC]     clitree/core/model.py   ↩ 见 [AAAABAAA]
                [AAAAD]     clitree/core/rules.py
                    [AAAADA]    clitree/core/store.py
                        [AAAADAA]   clitree/core/rules.py   ↩ 见 [AAAAD]
                    [AAAADB]    clitree/rules/   ← 数据目录（1 项）
                [AAAAE]     clitree/core/store.py   ↩ 见 [AAAADA]
                [AAAAF]     clitree/ui/log_panel.py
                    [AAAAFA]    clitree/ui/qt.py
                [AAAAG]     clitree/ui/param_form.py
                    [AAAAGA]    clitree/core/model.py   ↩ 见 [AAAABAAA]
                    [AAAAGB]    clitree/core/store.py   ↩ 见 [AAAADA]
                    [AAAAGC]    clitree/ui/qt.py   ↩ 见 [AAAAFA]
                [AAAAH]     clitree/ui/qt.py   ↩ 见 [AAAAFA]
                [AAAAI]     clitree/ui/run_bar.py
                    [AAAAIA]    clitree/ui/icons.py
                        [AAAAIAA]   clitree/ui/qt.py   ↩ 见 [AAAAFA]
                    [AAAAIB]    clitree/ui/qt.py   ↩ 见 [AAAAFA]
                [AAAAJ]     clitree/ui/tree_panel.py
                    [AAAAJA]    clitree/ui/qt.py   ↩ 见 [AAAAFA]
            [AAAB]      clitree/ui/qt.py   ↩ 见 [AAAAFA]
        [AAB]       clitree/core/discovery.py   ↩ 见 [AAAABA]
        [AAC]       clitree/core/lazy.py   ↩ 见 [AAAAB]
        [AAD]       clitree/core/parser.py   ↩ 见 [AAAABAA]
        [AAE]       clitree/core/rules.py   ↩ 见 [AAAAD]
[B]         clitree/__main__.py   ↩ 见 [AA]
[C]         tools/make_screenshots.py   ← 独立脚本（生成界面截图）
    [CA]        clitree/ui/main_window.py   ↩ 见 [AAAA]
    [CB]        clitree/ui/qt.py   ↩ 见 [AAAAFA]
    [CC]        screenshots/   ← 数据目录（9 项）
    [CD]        tests/   ← 数据目录（12 项）
    [CE]        tests/fixtures/   ← 数据目录（2 项）
[D]         tools/deps_tree.py   ← 独立脚本（生成本文件）
    [DA]        pyproject.toml   ↩ 见 [A]
    [DB]        tests/   ↩ 见 [CD]
[E]         tests/fixtures/fakecli.py   ← 假 CLI（测试以子进程执行的入口）
[F]         tests/conftest.py   ← pytest 夹具与路径注入
    [FA]        clitree/core/rules.py   ↩ 见 [AAAAD]
    [FB]        tests/fixtures/   ↩ 见 [CE]
    [FC]        tests/fixtures/help/   ← 数据目录（27 项）
[G]         tests/test_discovery.py   ← 测试入口（pytest 收集）
    [GA]        clitree/core/discovery.py   ↩ 见 [AAAABA]
    [GB]        clitree/core/rules.py   ↩ 见 [AAAAD]
[H]         tests/test_executor.py   ← 测试入口（pytest 收集）
    [HA]        clitree/core/executor.py   ↩ 见 [AAAAA]
    [HB]        clitree/core/model.py   ↩ 见 [AAAABAAA]
    [HC]        clitree/core/terminals.py   ↩ 见 [AAAAAA]
[I]         tests/test_gui_smoke.py   ← 测试入口（pytest 收集）
    [IA]        clitree/core/discovery.py   ↩ 见 [AAAABA]
    [IB]        clitree/core/executor.py   ↩ 见 [AAAAA]
    [IC]        clitree/core/store.py   ↩ 见 [AAAADA]
    [ID]        clitree/ui/main_window.py   ↩ 见 [AAAA]
    [IE]        clitree/ui/qt.py   ↩ 见 [AAAAFA]
[J]         tests/test_lazy.py   ← 测试入口（pytest 收集）
    [JA]        clitree/core/discovery.py   ↩ 见 [AAAABA]
    [JB]        clitree/core/lazy.py   ↩ 见 [AAAAB]
    [JC]        clitree/core/rules.py   ↩ 见 [AAAAD]
[K]         tests/test_parser_blocks.py   ← 测试入口（pytest 收集）
    [KA]        clitree/core/parser.py   ↩ 见 [AAAABAA]
    [KB]        clitree/core/rules.py   ↩ 见 [AAAAD]
[L]         tests/test_parser_subcommands.py   ← 测试入口（pytest 收集）
    [LA]        clitree/core/parser.py   ↩ 见 [AAAABAA]
    [LB]        clitree/core/rules.py   ↩ 见 [AAAAD]
[M]         tests/test_rules.py   ← 测试入口（pytest 收集）
    [MA]        clitree/core/rules.py   ↩ 见 [AAAAD]
[N]         tests/test_store.py   ← 测试入口（pytest 收集）
    [NA]        clitree/core/rules.py   ↩ 见 [AAAAD]
    [NB]        clitree/core/store.py   ↩ 见 [AAAADA]
[O]         tests/test_widgets.py   ← 测试入口（pytest 收集）
    [OA]        clitree/core/parser.py   ↩ 见 [AAAABAA]
    [OB]        clitree/core/rules.py   ↩ 见 [AAAAD]
    [OC]        clitree/core/widgets.py   ↩ 见 [AAAABAAB]
```
