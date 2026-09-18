from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError, TemplateNotFound

from stnp_editor.errors import GenerationError
from stnp_editor.settings import resources_root, settings


def make_env(template_root: Path | None = None) -> Environment:
    """构造 Python 模板环境；模板目录不可用时映射为 ``E4009``。"""
    try:
        root = template_root or (resources_root() / settings.template_dir("python"))
        env = Environment(
            loader=FileSystemLoader(str(root)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.filters["repr"] = repr
    except (TemplateError, OSError) as exc:
        raise GenerationError("E4009", message=f"Python 模板环境初始化失败: {exc}") from exc
    return env


def render(env: Environment, template_name: str, **ctx) -> str:
    """加载并渲染模板；模板缺失 -> ``E4009``，渲染失败 -> ``E4008``。"""
    try:
        template = env.get_template(template_name)
    except TemplateNotFound as exc:
        raise GenerationError("E4009", message=f"模板缺失: {template_name}") from exc
    except (TemplateError, OSError) as exc:
        raise GenerationError("E4009", message=f"模板不可读: {template_name}") from exc
    try:
        return template.render(**ctx)
    except TemplateError as exc:
        raise GenerationError("E4008", message=f"模板渲染失败: {template_name}: {exc}") from exc
