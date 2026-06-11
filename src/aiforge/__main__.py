"""``python -m aiforge`` 入口(契约 03:极薄,顶层零业务 import)。

包加载失败也必须非 0(→3,infra_error);argparse 的 usage 错误(SystemExit 2)
重映射为 3——退出码 2 保留给 needs_human,不许语义冲撞。
"""
import sys


def _main() -> int:
    try:
        from aiforge.cli import main
    except Exception as exc:  # noqa: BLE001 — 兜底即职责
        sys.stderr.write(f"[infra] aiforge 包加载失败: {exc}\n")
        return 3
    try:
        return main()
    except SystemExit as exc:  # argparse: usage 错误=2,--help=0
        code = exc.code if isinstance(exc.code, int) else 0
        return 3 if code == 2 else code
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"[infra] 未预期异常: {exc}\n")
        return 3


if __name__ == "__main__":
    sys.exit(_main())
