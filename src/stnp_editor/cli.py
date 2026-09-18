from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from stnp_editor import __version__
from stnp_editor.diagnostics import Diagnostic, emit_diagnostics
from stnp_editor.emit.c import emit_c
from stnp_editor.emit.python import emit_python
from stnp_editor.errors import (
    EXIT_FAILURE,
    EXIT_INTERNAL,
    EXIT_OK,
    EXIT_USAGE,
    InternalError,
    StnpError,
    exit_code_for,
)
from stnp_editor.generation import generated_dir_name
from stnp_editor.loader import load_build_data, load_project
from stnp_editor.settings import settings


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：统一捕获、按错误码映射退出码。"""
    try:
        return _run(argv)
    except SystemExit as exc:
        # argparse 用法错误（2）与 --help（0）已由解析库自行打印消息，这里只回传码。
        code = exc.code
        if code is None:
            return EXIT_OK
        return code if isinstance(code, int) else EXIT_USAGE
    except KeyboardInterrupt:
        # 键盘中断不映射为 3，原样抛出交还 shell 处理。
        raise
    except StnpError as exc:
        diagnostics = [exc.to_diagnostic()]
        emit_diagnostics(diagnostics)
        return exit_code_for(diagnostics)
    except Exception as exc:
        diagnostics = [InternalError("E9001", message=f"未捕获异常: {exc!r}").to_diagnostic()]
        emit_diagnostics(diagnostics)
        return EXIT_INTERNAL


def _run(argv: list[str] | None) -> int:
    """CLI 执行体：解析参数并按 build 顶层单一 target 分派。"""
    args = _build_parser().parse_args(argv)

    if args.cmd == "version":
        print(__version__)
        return EXIT_OK

    if args.cmd == "generate":
        diagnostics: list[Diagnostic] = []
        ir = load_project(args.project, args.build, diagnostics=diagnostics)
        build = load_build_data(args.build)
        target = build["target"]
        out = (
            emit_python(ir, args.output, build)
            if target == "python"
            else emit_c(ir, args.output, build)
        )
        emit_diagnostics(diagnostics)
        if args.list:
            _print_file_list(out)
        else:
            print(f"generated: {out}")
        return EXIT_OK

    if args.cmd == "check":
        diagnostics = []
        ir = load_project(args.project, args.build, diagnostics=diagnostics)
        build = load_build_data(args.build)
        target = build["target"]
        dir_name = f"{ir.output_stem}_{generated_dir_name(build, target)}"
        golden_root = args.golden.resolve()
        candidate = golden_root / dir_name
        golden_target = candidate if candidate.is_dir() else golden_root
        with tempfile.TemporaryDirectory(prefix="stnp_check_") as tmp:
            tmp_path = Path(tmp)
            got = (
                emit_python(ir, tmp_path, build)
                if target == "python"
                else emit_c(ir, tmp_path, build)
            )
            diffs = _diff_trees(got, golden_target)
        emit_diagnostics(diagnostics)
        if diffs:
            print("CHECK FAILED:")
            for line in diffs:
                print(f"  {line}")
            return EXIT_FAILURE
        print("CHECK OK")
        return EXIT_OK

    return EXIT_USAGE


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stnpe",
        description=(
            "STNP C/Python code generator.\n"
            "\n"
            "Commands:\n"
            "  generate <project.stnp> <stnp.build.json> -o <output> [-list]\n"
            "      Generate the C or Python tree selected by <stnp.build.json>.\n"
            "      -o, --output <output>  parent directory that receives the generated tree\n"
            "                             (required; the tree is created inside it)\n"
            "      -list                  print every generated file as [N/M] path on stdout\n"
            "  check <project.stnp> <stnp.build.json> --golden <dir>\n"
            "      Generate into a temporary directory and diff it against <dir>.\n"
            "      --golden <dir>         golden directory holding the expected tree\n"
            "                             (required; the tree itself or its parent)\n"
            "  version\n"
            "      Print the stnpe version.\n"
            "\n"
            "Run `stnpe <command> -h` for a command's operands, flags and an example."
        ),
        epilog=(
            "Examples:\n"
            "  stnpe generate examples/dual_multi_c_py/dual_multi.stnp "
            "examples/dual_multi_c_py/stnp.build.python.json -o _out\n"
            "  stnpe generate examples/handshake_c/handshake.stnp "
            "examples/handshake_c/stnp.build.json -o _out -list\n"
            "  stnpe check examples/handshake_c/handshake.stnp "
            "examples/handshake_c/stnp.build.json --golden _out\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="Print the stnpe version and exit",
    )
    sub = parser.add_subparsers(
        dest="cmd",
        required=True,
        metavar="{generate,check,version}",
        help="Command to run",
    )

    gen = sub.add_parser(
        "generate",
        help="Generate the selected C/Python target tree",
        description=(
            "Generate the target tree selected by <stnp.build.json> from <project.stnp>.\n"
            "The two files are validated independently and never reference each other.\n"
            "\n"
            "Operands:\n"
            "  <project.stnp>      path to the .stnp protocol project\n"
            "  <stnp.build.json>   path to the generation config that selects the target\n"
            "\n"
            "Flags:\n"
            "  -o, --output <output>  parent directory that receives the generated tree\n"
            "                         (required; created when missing)\n"
            "  -list                  print generated files as [N/M] path on stdout instead\n"
            "                         of the usual `generated: <tree>` line"
        ),
        epilog=(
            "Example:\n"
            "  stnpe generate examples/handshake_c/handshake.stnp "
            "examples/handshake_c/stnp.build.json -o _out\n"
            "  # writes _out/handshake_STNP_C/ and prints: generated: <path>"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    gen.add_argument(
        "project",
        metavar="<project.stnp>",
        type=Path,
        help="Path to the .stnp protocol project",
    )
    gen.add_argument(
        "build",
        metavar="<stnp.build.json>",
        type=Path,
        help="Path to the stnp.build.json generation config",
    )
    gen.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        metavar="<output>",
        help="Parent directory for the selected generated target tree",
    )
    gen.add_argument(
        "-list",
        dest="list",
        action="store_true",
        help="Print generated files as [N/M] path on stdout",
    )

    chk = sub.add_parser(
        "check",
        help="Generate to temp and diff against golden",
        description=(
            "Generate the selected target into a temporary directory and compare it with\n"
            "the expected tree under <dir>.  Only protocol areas are compared;\n"
            "Implementation/ may differ or be skipped.\n"
            "\n"
            "Operands:\n"
            "  <project.stnp>      path to the .stnp protocol project\n"
            "  <stnp.build.json>   path to the generation config that selects the target\n"
            "\n"
            "Flags:\n"
            "  --golden <dir>      golden directory holding the expected output tree\n"
            "                      (required; either the tree itself or its parent)\n"
            "\n"
            "Exit status: 0 when the trees match (prints `CHECK OK`), 1 on differences\n"
            "(prints `CHECK FAILED:` followed by one line per difference)."
        ),
        epilog=(
            "Example:\n"
            "  stnpe check examples/handshake_c/handshake.stnp "
            "examples/handshake_c/stnp.build.json --golden _out\n"
            "  # compares the generated tree against _out/ (or the tree found under it)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    chk.add_argument(
        "project",
        metavar="<project.stnp>",
        type=Path,
        help="Path to the .stnp protocol project",
    )
    chk.add_argument(
        "build",
        metavar="<stnp.build.json>",
        type=Path,
        help="Path to the stnp.build.json generation config",
    )
    chk.add_argument(
        "--golden",
        type=Path,
        required=True,
        metavar="<dir>",
        help="Golden root containing the selected target output tree",
    )

    sub.add_parser(
        "version",
        help="Print the stnpe version",
        description="Print the stnpe version and exit.",
        epilog=(
            "Example:\n"
            "  stnpe version\n"
            "Equivalent to the top-level `stnpe --version`."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    return parser


def _print_file_list(root: Path) -> None:
    """按 D-010 逐文件打印 ``[N/M] path``（path 相对生成工程根的 posix 路径）。"""
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    total = len(files)
    for index, rel in enumerate(files, start=1):
        print(f"[{index}/{total}] {rel}")


def _norm_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _diff_trees(got: Path, golden: Path) -> list[str]:
    diffs: list[str] = []
    if not golden.is_dir():
        return [f"golden missing: {golden}"]

    got_files = {p.relative_to(got).as_posix() for p in got.rglob("*") if p.is_file()}
    gold_files = {
        p.relative_to(golden).as_posix() for p in golden.rglob("*") if p.is_file()
    }

    # Implementation may differ / be skipped — compare protocol areas only for check
    skip_prefixes = (f"{settings.dir_name('implementation')}/",)

    for rel in sorted(gold_files | got_files):
        if any(rel.startswith(p) for p in skip_prefixes):
            continue
        g = got / rel
        k = golden / rel
        if not g.is_file():
            diffs.append(f"missing in generated: {rel}")
            continue
        if not k.is_file():
            diffs.append(f"extra in generated: {rel}")
            continue
        if _norm_text(g) != _norm_text(k):
            diffs.append(f"content differs: {rel}")
    return diffs


if __name__ == "__main__":
    raise SystemExit(main())
