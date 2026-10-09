#!/usr/bin/env python3
"""可控假 CLI：给测试用，绝不碰真系统。"""
import sys
import time

HELP = """usage: fakecli [options] <target>

A fake cli for tests.

Commands:
  sub1            first subcommand
  sub2            second subcommand
  sub3            third subcommand

Options:
  -v, --verbose           verbose output
  -o, --output <FILE>     write output to FILE
  -n, --count <count>     number of times to repeat
  -m, --mode <mode>       mode, can be one of <fast|slow|auto>
      --color[=<COLOR>]   colorize output (auto, always, never)
  -q, --quiet             quiet mode
      --no-color          disable color
  -h, --help              show this help message and exit
"""

SUB_HELP = """usage: fakecli {sub} [options]

Options:
  -x, --extra <VALUE>     an extra value
  -f, --force             force it
      --opt <a|b|c>       pick one, can be one of <a|b|c>
"""


def main(argv):
    if "--help-rc" in argv:
        i = argv.index("--help-rc")
        rc = int(argv[i + 1])
        if "--help" in argv or "-h" in argv:
            sys.stdout.write(HELP)
            return rc
    if argv and argv[0] in ("sub1", "sub2", "sub3"):
        if "--help" in argv or "-h" in argv:
            sys.stdout.write(SUB_HELP.format(sub=argv[0]))
            return 0
        sys.stdout.write("FAKECLI sub=%s rest=%s\n" % (argv[0], " ".join(argv[1:])))
        return 0
    if "--help" in argv or "-h" in argv:
        sys.stdout.write(HELP)
        return 0
    if "--sleep" in argv:
        time.sleep(float(argv[argv.index("--sleep") + 1]))
    if "--fail" in argv:
        sys.stdout.write("FAKECLI FAILING argv=%s\n" % " ".join(argv))
        sys.stderr.write("fakecli: deliberate failure\n")
        return 3
    if "--emit-utf8" in argv or "--emit-gbk" in argv:
        # 编码探针（Windows 实测：narnat 输出 UTF-8，ping 的中文帮助是 GBK）
        if "--emit-utf8" in argv:
            sys.stdout.buffer.write("FAKECLI utf8 你好\n".encode("utf-8"))
        if "--emit-gbk" in argv:
            sys.stdout.buffer.write("FAKECLI gbk 你好\n".encode("gbk"))
        sys.stdout.buffer.flush()
        return 0
    out = sys.stdout
    if "--to-stderr" in argv:
        out = sys.stderr
    for i in range(3):
        out.write("FAKECLI line%d argv=%s\n" % (i, " ".join(argv)))
        out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
