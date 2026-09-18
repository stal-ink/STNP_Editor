from __future__ import annotations

from stnp_editor.errors import GenerationError


def ensure_supported_sdks(sdks: tuple[str, ...] | list[str], target: str = "c") -> tuple[str, ...]:
    """Validate optional SDK selections against the target-specific SDK registry."""
    from stnp_editor.settings import settings

    normalized = tuple(dict.fromkeys(str(sdk) for sdk in (sdks or ())))
    supported = set(settings.available_sdks_for(target))
    unsupported = tuple(sdk for sdk in normalized if sdk not in supported)
    if unsupported:
        raise GenerationError(
            "E4003",
            message=f"Unsupported {target} SDK(s): {', '.join(unsupported)}",
        )
    return normalized


def validate_output_stem(stem: str) -> str:
    """Require a single safe path component for generated output directory names."""
    if (
        not stem
        or stem in {".", ".."}
        or "/" in stem
        or "\\" in stem
        or ":" in stem
        or "\x00" in stem
    ):
        raise GenerationError("E4006", message=f"unsafe output_stem: {stem!r}")
    return stem


#: C2 命名公式的内置回退：build.layout.output_dir_names 缺省时按目标取值。
_DEFAULT_OUTPUT_DIR_NAMES = {"c": "STNP_C", "python": "STNP_Python"}


def generated_dir_name(build: dict, target: str) -> str:
    """最终工程文件夹后缀：``build["layout"]["output_dir_names"][target]``。

    命中 C2 命名公式 ``{output_stem}_{layout.output_dir_names[target]}`` 的后半段；
    ``layout`` / ``output_dir_names`` / 目标键任一缺省时回退到 ``STNP_C`` /
    ``STNP_Python``。``target`` 已由加载期 schema 限定为 ``c`` / ``python``。
    """
    layout = build.get("layout") or {}
    names = layout.get("output_dir_names") or {}
    name = names.get(target)
    return str(name) if name else _DEFAULT_OUTPUT_DIR_NAMES[target]
