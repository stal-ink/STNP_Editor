"""STNP Editor 内部资源文件访问：schema 定位、模板目录、SDK 注册表等。

config.json 是生成器的内部资源文件（非用户配置），承载 schema 定位、
schema 文件名映射、模板目录、内部目录命名与 C/Python SDK 注册表。
用户可调项（输出目录命名、示例产出开关等）已迁出至 stnp.build.json。

打包（PyInstaller ``--onefile``）后的双路径模型
------------------------------------------------
onefile 形态下 PyInstaller 每次运行都把包解压到临时目录 ``sys._MEIPASS``
（``%TEMP%/_MEIxxxxx``），退出即删 —— 该目录**只能读**，绝不能写用户数据。
因此这里把「随包只读资源」与「用户可写配置」彻底分开：

- ``bundle_root()``：随包只读资源根（内置 ``config.json``、``schemas/``、
  ``templates/``）。冻结时位于 ``_MEIPASS`` 内；源码运行时等于 ``resources_root()``。
- ``user_config_path()``：用户可写配置 —— 冻结时是 **exe 同级的** ``config.json``；
  源码运行时返回 ``None``（该机制不启用，行为与打包前完全一致）。
- ``ensure_user_config()``：首次运行时把内置默认内容复制到 exe 同级，之后用户可改；
  写入失败（只读目录 / 权限不足）不抛异常，仅向 stderr 提示并回退内置默认。

``load_config()`` 优先级（高 → 低）：

1. 显式 ``path`` 参数
2. 环境变量 ``STNP_EDITOR_CONFIG``
3. exe 同级 ``config.json``（仅冻结且存在时）
4. 内置 ``bundle_root()/config.json``

基线永远是内置默认，上面各级作为**深合并覆盖层**（``_deep_merge``）。

微决策：当 ``STNP_EDITOR_CONFIG`` 已设置（或调用方显式传入 ``path``）时，
**跳过** ``ensure_user_config()`` 的创建动作 —— 二者都代表用户显式接管配置，
不应再往磁盘写文件。

硬约束：``bundle_root()`` 只用于**读**。本模块中唯一允许写入的目标是
``user_config_path()``。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_NAME = "config.json"
CONFIG_ENV_VAR = "STNP_EDITOR_CONFIG"


def package_root() -> Path:
    """stnp_editor 包代码目录（资源统一见 ``resources_root()``）。"""
    return Path(__file__).resolve().parents[0]


def resources_root() -> Path:
    """包内单一 data root：``config.json`` / ``schemas/`` / ``templates/`` 所在目录。"""
    return package_root() / "resources"


def is_frozen() -> bool:
    """当前是否运行在 PyInstaller 等冻结产物中。"""
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """随包**只读**资源根（内置 ``config.json`` / ``schemas/`` / ``templates/``）。

    冻结时资源随 onefile 解压到 ``sys._MEIPASS``；``datas`` 把它们放在
    ``stnp_editor/resources`` 下，因此优先返回该子目录；若布局不同则回退到
    ``_MEIPASS`` 根。源码运行时等价于 ``resources_root()``。

    本函数的结果**永远只读**；任何写入都必须走 ``user_config_path()``。
    """
    if not is_frozen():
        return resources_root()
    mei = getattr(sys, "_MEIPASS", None)
    if not mei:
        return resources_root()
    candidate = Path(mei) / "stnp_editor" / "resources"
    if candidate.is_dir():
        return candidate
    return Path(mei)


def user_config_path() -> Path | None:
    """用户可写配置路径：冻结时 = exe 同级 ``config.json``；否则 ``None``。"""
    if not is_frozen():
        return None
    return Path(sys.executable).resolve().parent / DEFAULT_CONFIG_NAME


def ensure_user_config() -> Path | None:
    """首启把内置默认 ``config.json`` 复制到 exe 同级；已存在则原样返回。

    写入失败（``OSError`` / ``PermissionError``）不抛异常：向 stderr 打印警告并
    返回 ``None``，调用方回退内置默认继续运行。返回 ``None`` 还表示源码运行
    （非冻结，不启用用户配置）。
    """
    target = user_config_path()
    if target is None:
        return None
    if target.exists():
        return target
    try:
        content = (bundle_root() / DEFAULT_CONFIG_NAME).read_text(encoding="utf-8")
        target.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        print(
            f"stnpe: warning: cannot create user config at {target}: {exc}; "
            "falling back to bundled defaults",
            file=sys.stderr,
        )
        return None
    return target


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path | None = None) -> dict[str, Any]:
    """加载配置：内置默认 + 覆盖层（显式路径 > 环境变量 > exe 同级 > 内置）。

    源码运行（非冻结）时行为与打包前逐字一致：基线读包内
    ``resources/config.json``，若有 ``path`` 或 ``STNP_EDITOR_CONFIG`` 则深合并覆盖。
    """
    cfg = json.loads((bundle_root() / DEFAULT_CONFIG_NAME).read_text(encoding="utf-8"))

    overlay: Path | None = None
    if path is not None:
        # 显式路径：用户已接管配置，跳过首启写文件。
        overlay = Path(path)
    else:
        env = os.environ.get(CONFIG_ENV_VAR)
        if env:
            # 环境变量：用户显式接管，跳过 ensure_user_config()（见模块 docstring）。
            overlay = Path(env)
        elif user_config_path() is not None:
            user = ensure_user_config()
            if user is not None and user.is_file():
                overlay = user

    if overlay is not None:
        ext = json.loads(overlay.read_text(encoding="utf-8"))
        cfg = _deep_merge(cfg, ext)
    return cfg


class Settings:
    """带默认值的内部资源访问器；缺失键回退到 config.json 里的原值或内置默认。"""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data = data if data is not None else load_config()

    @property
    def raw(self) -> dict[str, Any]:
        return self._data

    @property
    def schemas_dir(self) -> str:
        return self._data.get("schemas_dir", "schemas")

    def schema_file(self, key: str) -> str:
        files = self._data.get("schema_files", {})
        return files.get(key, f"{key}.schema.json")

    def template_dir(self, target: str) -> str:
        templates = self._data.get("templates", {})
        return templates.get(target, f"templates/{target}")

    def dir_name(self, key: str) -> str:
        dirs = self._data.get("dir_names", {})
        return dirs.get(key, key.title())

    @property
    def sdk_definitions(self) -> dict[str, dict[str, Any]]:
        value = self._data.get("sdk_registry", {})
        if not isinstance(value, dict):
            return {}
        return {str(key): dict(item) for key, item in value.items() if isinstance(item, dict)}

    def sdk_definitions_for(self, target: str) -> dict[str, dict[str, Any]]:
        if target == "c":
            return self.sdk_definitions
        if target == "python":
            value = self._data.get("python_sdk_registry", {})
            if not isinstance(value, dict):
                return {}
            return {str(key): dict(item) for key, item in value.items() if isinstance(item, dict)}
        return {}

    def available_sdks_for(self, target: str) -> tuple[str, ...]:
        return tuple(self.sdk_definitions_for(target))

    def sdk_definition_for(self, target: str, key: str) -> dict[str, Any]:
        try:
            return self.sdk_definitions_for(target)[key]
        except KeyError as exc:
            raise KeyError(f"unknown {target} SDK: {key}") from exc

    def default_validations(self) -> list[dict[str, str]]:
        """默认校验清单：由 errors.DEFAULT_VALIDATIONS 导出（排除预留与内部码）。"""
        from stnp_editor.errors import DEFAULT_VALIDATIONS

        return [dict(x) for x in DEFAULT_VALIDATIONS]


settings = Settings()
