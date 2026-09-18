"""STNP 统一错误码注册表与异常基类（0.9 冻结计划 §4.1.1 / §4.1.2 / §4.1.4）。

本模块单向依赖 ``stnp_editor.diagnostics``；``diagnostics`` 不得反向导入。

## 错误码分段

====================  ==========================  ==================
段                    段内范围                     归属阶段
====================  ==========================  ==================
``E1xxx`` 加载格式      ``E1001–E1099``             加载期
                       （``E1001–E1050`` 输入解析，
                       ``E1051–E1099`` 配置与环境）
``E2xxx`` 校验          ``E2101–E2199``             校验期
``E3xxx`` 构建          ``E3001–E3099``             构建期
``E4xxx`` 生成写出      ``E4001–E4099``             生成期
``E9xxx`` 内部          仅 ``E9001`` / ``E9002``     任意阶段兜底
====================  ==========================  ==================

## 错误码纪律

**已分配错误码只增不改；删除报错点时其码位保留，不复用。**
已登记的码不得改名、不得改变归属段、不得把码位让给其它报错点；删除报错点
只是不再产出该码，注册表条目与默认校验清单中的位置均保留。本轮的
``E1006``（schema 文件缺失）为预留码，登记在册但 ``enabled=False``，不参与
诊断、退出码与默认校验清单。

## 本轮口径

- 码总数 70：E1 段 14、E2 段 35、E3 段 7、E4 段 12、E9 段 2。
- 全部登记码默认级别为 ``error``；``warning`` / ``note`` 由 build 文件的
  ``validations`` 段按 ``id`` / ``level`` 覆盖。
- 消息模板为完整中文短句，以事实结尾、不带句末句号；需要携带具体取值的
  报错点在构造异常时自行传入 ``message``。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from stnp_editor.diagnostics import LEVELS, Diagnostic, Level

__all__ = [
    "DEFAULT_VALIDATIONS",
    "ERROR_CODES",
    "EXIT_FAILURE",
    "EXIT_INTERNAL",
    "EXIT_OK",
    "EXIT_USAGE",
    "BuildError",
    "ErrorCodeSpec",
    "GenerationError",
    "InternalError",
    "LoadingError",
    "StnpError",
    "ValidationError",
    "exit_code_for",
]

#: 成功。
EXIT_OK = 0
#: 失败：E1 / E2 / E3 / E4 段的 error 级诊断。
EXIT_FAILURE = 1
#: 用法错误：命令行解析失败；由 CLI 层负责，不携带错误码。
EXIT_USAGE = 2
#: 内部缺陷：E9 段 error（未捕获异常或内部不变量破坏）。
EXIT_INTERNAL = 3


@dataclass(frozen=True)
class ErrorCodeSpec:
    """单个错误码的登记信息。

    ``segment_range`` 为段内范围，``category`` 为段内细分归属，
    ``enabled=False`` 表示本轮预留、不启用。
    """

    code: str
    segment: str
    segment_range: str
    category: str
    phase: str
    message: str
    default_level: str = "error"
    help: str = ""
    enabled: bool = True


_SPECS: tuple[ErrorCodeSpec, ...] = (
    # ------------------------------------------------------------------
    # E1xxx 加载格式 · 输入解析（E1001–E1050）· 加载期
    # ------------------------------------------------------------------
    ErrorCodeSpec(
        "E1001", "加载格式", "E1001–E1099", "输入解析", "加载期",
        "工程文件缺失或不可读", help="确认路径存在且文件扩展名为 .stnp",
    ),
    ErrorCodeSpec(
        "E1002", "加载格式", "E1001–E1099", "输入解析", "加载期",
        "工程文件 JSON 解析失败", help="检查 JSON 语法，尤其是括号与逗号",
    ),
    ErrorCodeSpec(
        "E1003", "加载格式", "E1001–E1099", "输入解析", "加载期",
        "工程文件 schema 校验失败", help="按校验路径修正字段名或取值",
    ),
    ErrorCodeSpec(
        "E1004", "加载格式", "E1001–E1099", "输入解析", "加载期",
        "嵌入文件 Base64 内容无效", help="重新编码嵌入文件内容并保持标准 Base64",
    ),
    ErrorCodeSpec(
        "E1005", "加载格式", "E1001–E1099", "输入解析", "加载期",
        ".stnp 版本标识不受支持", help="将 schema_version 改为生成器支持的取值",
    ),
    # 预留：schema 文件缺失，本轮不启用（不参与诊断 / 退出码 / 默认校验清单）。
    ErrorCodeSpec(
        "E1006", "加载格式", "E1001–E1099", "输入解析", "加载期",
        "schema 文件缺失", help="重装生成器或修复安装文件", enabled=False,
    ),
    # ------------------------------------------------------------------
    # E1xxx 加载格式 · 配置与环境（E1051–E1099）· 加载期
    # ------------------------------------------------------------------
    ErrorCodeSpec(
        "E1051", "加载格式", "E1001–E1099", "配置与环境", "加载期",
        "内部资源文件缺失或不可读", help="重装生成器或修复安装文件",
    ),
    ErrorCodeSpec(
        "E1052", "加载格式", "E1001–E1099", "配置与环境", "加载期",
        "内部资源文件格式非法", help="重装生成器或修复安装文件",
    ),
    ErrorCodeSpec(
        "E1053", "加载格式", "E1001–E1099", "配置与环境", "加载期",
        "内部 SDK 注册表条目未知", help="使用生成器注册表登记的 SDK 名称",
    ),
    ErrorCodeSpec(
        "E1054", "加载格式", "E1001–E1099", "配置与环境", "加载期",
        "build 文件缺失或不可读", help="确认 build 文件路径存在且可读",
    ),
    ErrorCodeSpec(
        "E1055", "加载格式", "E1001–E1099", "配置与环境", "加载期",
        "build 版本标识不受支持", help="将 build_schema_version 改为生成器支持的取值",
    ),
    ErrorCodeSpec(
        "E1056", "加载格式", "E1001–E1099", "配置与环境", "加载期",
        "build 文件 schema 校验失败", help="按校验路径修正字段名或取值",
    ),
    ErrorCodeSpec(
        "E1057", "加载格式", "E1001–E1099", "配置与环境", "加载期",
        "build 文件 target 缺失或非法", help="将 target 设为 c 或 python",
    ),
    ErrorCodeSpec(
        "E1058", "加载格式", "E1001–E1099", "配置与环境", "加载期",
        "环境变量指定的覆盖配置不可用", help="修正或清除 STNP_EDITOR_CONFIG 指向的文件",
    ),
    # ------------------------------------------------------------------
    # E2xxx 校验 · 名称与重复（E2101–E2119）· 校验期
    # ------------------------------------------------------------------
    ErrorCodeSpec(
        "E2101", "校验", "E2101–E2199", "名称与重复", "校验期",
        "标识符不是合法 C 标识符", help="改用字母或下划线开头且仅含字母、数字、下划线的名称",
    ),
    ErrorCodeSpec("E2102", "校验", "E2101–E2199", "名称与重复", "校验期", "模块名重复"),
    ErrorCodeSpec("E2103", "校验", "E2101–E2199", "名称与重复", "校验期", "模块名归一化后冲突"),
    ErrorCodeSpec("E2104", "校验", "E2101–E2199", "名称与重复", "校验期", "生成的命令行为符号重复"),
    ErrorCodeSpec("E2105", "校验", "E2101–E2199", "名称与重复", "校验期", "实例 ID 重复"),
    ErrorCodeSpec("E2106", "校验", "E2101–E2199", "名称与重复", "校验期", "实例名重复"),
    ErrorCodeSpec("E2107", "校验", "E2101–E2199", "名称与重复", "校验期", "实例名归一化后冲突"),
    ErrorCodeSpec("E2108", "校验", "E2101–E2199", "名称与重复", "校验期", "通用类型名重复"),
    ErrorCodeSpec("E2109", "校验", "E2101–E2199", "名称与重复", "校验期", "通用类型名与保留 STNP 类型冲突"),
    ErrorCodeSpec("E2110", "校验", "E2101–E2199", "名称与重复", "校验期", "枚举值名重复"),
    ErrorCodeSpec("E2111", "校验", "E2101–E2199", "名称与重复", "校验期", "枚举值重复"),
    ErrorCodeSpec("E2112", "校验", "E2101–E2199", "名称与重复", "校验期", "载荷字段名重复"),
    ErrorCodeSpec("E2113", "校验", "E2101–E2199", "名称与重复", "校验期", "生成 C 符号冲突"),
    ErrorCodeSpec("E2114", "校验", "E2101–E2199", "名称与重复", "校验期", "通知名重复"),
    ErrorCodeSpec("E2115", "校验", "E2101–E2199", "名称与重复", "校验期", "通知码重复"),
    ErrorCodeSpec("E2116", "校验", "E2101–E2199", "名称与重复", "校验期", "通知名归一化后冲突"),
    ErrorCodeSpec("E2117", "校验", "E2101–E2199", "名称与重复", "校验期", "命令名重复"),
    ErrorCodeSpec("E2118", "校验", "E2101–E2199", "名称与重复", "校验期", "命令码重复"),
    ErrorCodeSpec("E2119", "校验", "E2101–E2199", "名称与重复", "校验期", "命令名归一化后冲突"),
    # 返回码名 / 值重复（现 builder._build_return_codes；分段归属见 E3xxx）。
    ErrorCodeSpec("E2120", "校验", "E2101–E2199", "名称与重复", "校验期", "返回码名或值重复"),
    # ------------------------------------------------------------------
    # E2xxx 校验 · 取值范围（E2121–E2129）· 校验期
    # ------------------------------------------------------------------
    ErrorCodeSpec("E2121", "校验", "E2101–E2199", "取值范围", "校验期", "枚举没有任何取值"),
    ErrorCodeSpec("E2122", "校验", "E2101–E2199", "取值范围", "校验期", "枚举值超出基础类型范围"),
    ErrorCodeSpec("E2123", "校验", "E2101–E2199", "取值范围", "校验期", "基础类型不受支持"),
    ErrorCodeSpec("E2124", "校验", "E2101–E2199", "取值范围", "校验期", "字段 min 或 max 超出基础类型范围"),
    ErrorCodeSpec("E2125", "校验", "E2101–E2199", "取值范围", "校验期", "字段 min 大于 max"),
    ErrorCodeSpec("E2126", "校验", "E2101–E2199", "取值范围", "校验期", "task 与 notify 的 SOF 相同"),
    ErrorCodeSpec("E2127", "校验", "E2101–E2199", "取值范围", "校验期", "task seq 保留集合非法"),
    ErrorCodeSpec("E2128", "校验", "E2101–E2199", "取值范围", "校验期", "实例 ID 超出 1..255"),
    ErrorCodeSpec("E2129", "校验", "E2101–E2199", "取值范围", "校验期", "实例数量超过 router_instance_max"),
    # ------------------------------------------------------------------
    # E2xxx 校验 · 引用完整性（E2130–E2133）· 校验期
    # ------------------------------------------------------------------
    ErrorCodeSpec("E2130", "校验", "E2101–E2199", "引用完整性", "校验期", "实例引用的模块不存在"),
    ErrorCodeSpec("E2131", "校验", "E2101–E2199", "引用完整性", "校验期", "通知引用缺失或指向不存在的通知"),
    # 0.9 起通知去分类，该报错点删除；码位保留，不复用。
    ErrorCodeSpec("E2132", "校验", "E2101–E2199", "引用完整性", "校验期", "通知引用与触发时机的分类不匹配"),
    ErrorCodeSpec("E2133", "校验", "E2101–E2199", "引用完整性", "校验期", "自动通知引用了非零载荷通知"),
    # ------------------------------------------------------------------
    # E2xxx 校验 · 结构完整性与路径安全（E2134–E2135）· 校验期
    # ------------------------------------------------------------------
    ErrorCodeSpec("E2134", "校验", "E2101–E2199", "结构完整性", "校验期", "工程没有启用的模块"),
    ErrorCodeSpec("E2135", "校验", "E2101–E2199", "路径安全", "校验期", "嵌入文件路径不安全"),
    # ------------------------------------------------------------------
    # E3xxx 构建（E3001–E3099）· 构建期
    # ------------------------------------------------------------------
    ErrorCodeSpec("E3001", "构建", "E3001–E3099", "构建语义", "构建期", "载荷累计长度超过 max_payload"),
    ErrorCodeSpec("E3002", "构建", "E3001–E3099", "构建语义", "构建期", "模块返回码缺少 OK"),
    ErrorCodeSpec("E3003", "构建", "E3001–E3099", "构建语义", "构建期", "模块返回码值超出 u16 范围"),
    ErrorCodeSpec("E3004", "构建", "E3001–E3099", "Return Code 分段", "构建期", "模块返回码值不在本模块分段区间"),
    ErrorCodeSpec("E3005", "构建", "E3001–E3099", "Return Code 分段", "构建期", "工程级返回码缺少值为 0x0000 的 OK"),
    ErrorCodeSpec("E3006", "构建", "E3001–E3099", "Return Code 分段", "构建期", "工程级返回码值不在 0x0001..0x00FF"),
    ErrorCodeSpec("E3007", "构建", "E3001–E3099", "Return Code 分段", "构建期", "返回码分段容量超限"),
    # ------------------------------------------------------------------
    # E4xxx 生成写出（E4001–E4099）· 生成期
    # ------------------------------------------------------------------
    ErrorCodeSpec("E4001", "生成写出", "E4001–E4099", "分派", "生成期", "生成目标不受支持"),
    # 0.9 起复数目标形态删除，该报错点删除；码位保留，不复用。
    ErrorCodeSpec("E4002", "生成写出", "E4001–E4099", "分派", "生成期", "复数生成目标形态不受支持"),
    ErrorCodeSpec("E4003", "生成写出", "E4001–E4099", "SDK", "生成期", "目标 SDK 选择不受支持"),
    ErrorCodeSpec("E4004", "生成写出", "E4001–E4099", "SDK", "生成期", "SDK 注册表条目缺少模板目录或输出目录"),
    ErrorCodeSpec("E4005", "生成写出", "E4001–E4099", "路径安全", "生成期", "生成输出目录逃逸所选父目录"),
    ErrorCodeSpec("E4006", "生成写出", "E4001–E4099", "路径安全", "生成期", "输出文件名主干不安全"),
    ErrorCodeSpec("E4007", "生成写出", "E4001–E4099", "写出", "生成期", "Keil 目标文件基名冲突"),
    ErrorCodeSpec("E4008", "生成写出", "E4001–E4099", "模板", "生成期", "模板渲染失败"),
    ErrorCodeSpec("E4009", "生成写出", "E4001–E4099", "模板", "生成期", "模板缺失或不可读"),
    ErrorCodeSpec("E4010", "生成写出", "E4001–E4099", "写出", "生成期", "生成文件写出失败"),
    ErrorCodeSpec("E4011", "生成写出", "E4001–E4099", "写出", "生成期", "生成清单读写失败"),
    ErrorCodeSpec("E4012", "生成写出", "E4001–E4099", "写出", "生成期", "嵌入文件负载解码或写出失败"),
    # ------------------------------------------------------------------
    # E9xxx 内部（E9001 / E9002）· 任意阶段兜底
    # ------------------------------------------------------------------
    ErrorCodeSpec(
        "E9001", "内部", "E9001–E9002", "未捕获异常", "任意阶段兜底",
        "未捕获异常", help="将完整诊断信息反馈给生成器维护者",
    ),
    ErrorCodeSpec(
        "E9002", "内部", "E9001–E9002", "内部不变量破坏", "任意阶段兜底",
        "内部不变量破坏", help="将完整诊断信息反馈给生成器维护者",
    ),
)

ERROR_CODES: dict[str, ErrorCodeSpec] = {spec.code: spec for spec in _SPECS}

#: 默认校验清单：全列启用、默认级别 error；排除预留码与内部码。
DEFAULT_VALIDATIONS: list[dict[str, str]] = [
    {"id": spec.code, "level": spec.default_level}
    for spec in ERROR_CODES.values()
    if spec.enabled and spec.segment != "内部"
]


def _validate_registry() -> None:
    """导入期自检：形式、段计数与段内范围必须与冻结计划一致。"""
    expected: dict[str, tuple[int, tuple[int, int], int]] = {
        # 段名: (段首数字, (段内最小, 段内最大), 期望条数)
        "加载格式": (1, (1001, 1099), 14),
        "校验": (2, (2101, 2199), 35),
        "构建": (3, (3001, 3099), 7),
        "生成写出": (4, (4001, 4099), 12),
        "内部": (9, (9001, 9002), 2),
    }
    if len(_SPECS) != 70 or len(ERROR_CODES) != 70:
        raise RuntimeError("错误码总数必须为 70")
    for spec in _SPECS:
        if not re.fullmatch(r"E\d{4}", spec.code):
            raise RuntimeError(f"错误码形式非法: {spec.code}")
        head, (low, high), _count = expected[spec.segment]
        number = int(spec.code[1:])
        if spec.code[0] != "E" or int(spec.code[1]) != head:
            raise RuntimeError(f"错误码段号与段不一致: {spec.code} / {spec.segment}")
        if not low <= number <= high:
            raise RuntimeError(f"错误码超出段内范围: {spec.code}")
        if spec.default_level not in LEVELS:
            raise RuntimeError(f"默认级别非法: {spec.code} / {spec.default_level}")
    for segment, (_, _, count) in expected.items():
        actual = sum(1 for spec in _SPECS if spec.segment == segment)
        if actual != count:
            raise RuntimeError(f"段 {segment} 条数 {actual}，期望 {count}")
    disabled = {spec.code for spec in _SPECS if not spec.enabled}
    if disabled != {"E1006"}:
        raise RuntimeError(f"本轮仅允许 E1006 未启用，实际: {sorted(disabled)}")


_validate_registry()


class StnpError(Exception):
    """统一异常基类：携带错误码、级别、位置、JSON 指针、消息与 help。"""

    #: 子类钉死的段前缀（如 ``E1``）；基类为 None，接受任意已登记码。
    _segment_code: str | None = None

    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        file: str | None = None,
        line: int | None = None,
        column: int | None = None,
        json_pointer: str | None = None,
        help: str | None = None,
        level: str | None = None,
    ) -> None:
        spec = ERROR_CODES.get(code)
        if spec is None:
            raise ValueError(f"未登记的错误码: {code}")
        if self._segment_code is not None and not code.startswith(self._segment_code):
            raise ValueError(
                f"{type(self).__name__} 只接受 {self._segment_code}xxx 段错误码，收到 {code}"
            )
        resolved_level = spec.default_level if level is None else level
        if resolved_level not in LEVELS:
            raise ValueError(f"unknown diagnostic level: {resolved_level!r}")
        self.code = code
        self.level = resolved_level
        self.message = spec.message if message is None else message
        self.file = file
        self.line = line
        self.column = column
        self.json_pointer = json_pointer
        self.help = spec.help if help is None else help
        super().__init__(self.message)

    def to_diagnostic(self) -> Diagnostic:
        """转换为诊断层数据（help 为空视为无）。"""
        return Diagnostic(
            code=self.code,
            level=cast(Level, self.level),
            message=self.message,
            file=self.file,
            line=self.line,
            column=self.column,
            json_pointer=self.json_pointer,
            help=self.help or None,
        )


class LoadingError(StnpError):
    """加载期异常（E1xxx）。"""

    _segment_code = "E1"


class ValidationError(StnpError):
    """校验期异常（E2xxx）。"""

    _segment_code = "E2"


class BuildError(StnpError):
    """构建期异常（E3xxx）。"""

    _segment_code = "E3"


class GenerationError(StnpError):
    """生成期异常（E4xxx）。"""

    _segment_code = "E4"


class InternalError(StnpError):
    """内部异常（E9xxx）。"""

    _segment_code = "E9"


def exit_code_for(diags: list[Diagnostic]) -> int:
    """按诊断集合判定退出码。

    - 任意 ``E9xxx`` 的 error → 3（多段同时出错时内部错误优先于失败）。
    - 任意 ``E1`` / ``E2`` / ``E3`` / ``E4`` 的 error → 1。
    - 仅 ``warning`` / ``note``、空集合或成功 → 0；未启用码不参与判定。
    - 用法错误（命令行解析）→ 2 由 CLI 层负责，键盘中断不映射为 3。
    """
    internal = False
    failure = False
    for diag in diags:
        if diag.level != "error":
            continue
        spec = ERROR_CODES.get(diag.code)
        if spec is not None and not spec.enabled:
            continue
        if diag.code.startswith("E9"):
            internal = True
        else:
            failure = True
    if internal:
        return EXIT_INTERNAL
    if failure:
        return EXIT_FAILURE
    return EXIT_OK
