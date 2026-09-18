"""STNP 统一诊断呈现层：数据结构、格式化、排序与批量输出。

本模块只依赖标准库，**不得导入** ``stnp_editor.errors``：错误码注册表单向依赖
本模块，反向导入会形成循环导入。

呈现契约（0.9 冻结计划 §4.1.3）：

- 单条格式：``文件:行:列: error[错误码]: 消息``。
- 默认打印出错行 1 行，并以 ``^`` 指向列；有可执行修复建议时附单行 help，
  无则整行省略。
- 多条诊断之间空一行分隔。
- 排序：文件字典序（无文件者排最后）→ 行升序 → 列升序 → 错误码升序 →
  发现顺序稳定排序。
- 位置省略：无具体源位置时省略行列，只输出文件与诊断；连文件都没有时以
  内部哨兵 ``<internal>`` 标识；位置不完整时按可用部分输出。
- 消息为中文一句话，以事实结尾，不带句末句号。
- 诊断输出到 stderr，正常输出（生成路径、``-list``）到 stdout。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

Level = Literal["error", "warning", "note"]

LEVELS: tuple[Level, ...] = ("error", "warning", "note")

#: 无文件诊断的内部哨兵，作为位置前缀中的文件名输出。
INTERNAL_SENTINEL = "<internal>"

__all__ = [
    "INTERNAL_SENTINEL",
    "LEVELS",
    "Diagnostic",
    "Level",
    "emit_diagnostics",
    "format_diagnostic",
    "render_diagnostics",
]


@dataclass
class Diagnostic:
    """一条诊断：错误码、级别、消息与可选源位置。

    ``json_pointer`` 携带机器可读的定位信息（不进入呈现格式）；
    ``help`` 为单行修复建议，为空则呈现时整行省略。
    """

    code: str
    level: Level
    message: str
    file: str | None = None
    line: int | None = None
    column: int | None = None
    json_pointer: str | None = None
    help: str | None = None


def format_diagnostic(diag: Diagnostic, *, source_lines: list[str] | None = None) -> list[str]:
    """把单条诊断渲染为若干行（位置行 + 可选源行 / ``^`` 行 + 可选 help 行）。"""
    if diag.level not in LEVELS:
        raise ValueError(f"unknown diagnostic level: {diag.level!r}")
    lines = [f"{_format_location(diag)}{diag.level}[{diag.code}]: {diag.message}"]
    lines.extend(_source_and_caret(diag, source_lines))
    if diag.help:
        lines.append(f"help: {diag.help}")
    return lines


def render_diagnostics(
    diags: list[Diagnostic], *, source_lines: dict[str, list[str]] | None = None
) -> str:
    """排序并渲染全部诊断，多条之间空一行；无诊断时返回空串。"""
    blocks: list[str] = []
    for diag in _sorted_diagnostics(diags):
        file_lines = None
        if source_lines is not None and diag.file is not None:
            file_lines = source_lines.get(diag.file)
        blocks.append("\n".join(format_diagnostic(diag, source_lines=file_lines)))
    return "\n\n".join(blocks)


def emit_diagnostics(
    diags: list[Diagnostic],
    *,
    source_lines: dict[str, list[str]] | None = None,
    stream=None,
) -> None:
    """把全部诊断输出到 stderr（可用 ``stream`` 覆盖），无诊断时不输出。"""
    text = render_diagnostics(diags, source_lines=source_lines)
    if not text:
        return
    target = sys.stderr if stream is None else stream
    print(text, file=target)


def _format_location(diag: Diagnostic) -> str:
    file_part = diag.file if diag.file else INTERNAL_SENTINEL
    if diag.line is None:
        return f"{file_part}: "
    if diag.column is None:
        return f"{file_part}:{diag.line}: "
    return f"{file_part}:{diag.line}:{diag.column}: "


def _source_and_caret(diag: Diagnostic, source_lines: list[str] | None) -> list[str]:
    if source_lines is None or diag.line is None:
        return []
    if diag.line < 1 or diag.line > len(source_lines):
        return []
    text = str(source_lines[diag.line - 1]).rstrip("\r\n")
    lines = [text]
    if diag.column is not None and diag.column >= 1:
        prefix = text[: diag.column - 1].expandtabs(4)
        lines.append(" " * len(prefix) + "^")
    return lines


def _sorted_diagnostics(diags: list[Diagnostic]) -> list[Diagnostic]:
    return [diag for _, diag in sorted(enumerate(diags), key=_sort_key)]


def _sort_key(item: tuple[int, Diagnostic]) -> tuple[object, ...]:
    index, diag = item
    # 文件字典序；无文件者排最后。
    file_key = (1, "") if diag.file is None else (0, diag.file)
    # 行 / 列升序；位置缺失者在同文件内排最后。
    line_key = (1, 0) if diag.line is None else (0, diag.line)
    column_key = (1, 0) if diag.column is None else (0, diag.column)
    # 错误码升序，最后以发现顺序稳定排序。
    return (file_key, line_key, column_key, diag.code, index)
