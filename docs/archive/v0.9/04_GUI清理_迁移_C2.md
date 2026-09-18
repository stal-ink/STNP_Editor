# 04 GUI 清理清单 · 示例与 golden 迁移方案 · C2 命名定案

> 阶段一「定方案」交付物。**本文件只出清单与方案，不删除、不修改任何文件，不写实现代码。**
>
> 输入（只读）：`docs/IR-CLI-决策.md`（补充裁定 B / C2、D2 / D3 / D8 / D9 / D12、配置拆分补充裁定）、`src/stnp_editor/gui/`、`pyproject.toml`、`tests/`、`tests/golden/`、`examples/`。
>
> 所有路径均以仓库根 `STNP_Editor_0.8.2/` 为基准。

---

## 一、GUI 删除清单（穷尽）

### 1.1 待删除目录：`src/stnp_editor/gui/`

**目录位置确认**：`gui/` 位于 `src/stnp_editor/gui/`，**不是**仓库根 `gui/`。仓库根不存在 `gui/` 目录。

**文件总数：32 个**（其中 Python 源文件 25 个、JSON 资源 4 个、其余 3 个；按目录分解如下）

| # | 目录 | 文件 | 小计 |
|---|------|------|------|
| 1 | `src/stnp_editor/gui/` | `__init__.py`、`__main__.py`、`app.py`、`defaults.py`、`launcher.py`、`main_window.py`、`style.py` | 7 |
| 2 | `src/stnp_editor/gui/controllers/` | `__init__.py`、`project_controller.py` | 2 |
| 3 | `src/stnp_editor/gui/document/` | `__init__.py`、`project_document.py` | 2 |
| 4 | `src/stnp_editor/gui/editors/` | `__init__.py`、`editor_factory.py`、`hex_utils.py` | 3 |
| 5 | `src/stnp_editor/gui/i18n/` | `__init__.py`、`catalog.py`、`translator.py`、`en_US.json`、`zh_CN.json` | 5 |
| 6 | `src/stnp_editor/gui/models/` | `__init__.py`、`project_tree_model.py`、`tree_node.py` | 3 |
| 7 | `src/stnp_editor/gui/schema/` | `__init__.py`、`gui_overrides.json`、`schema_adapter.py` | 3 |
| 8 | `src/stnp_editor/gui/views/` | `__init__.py`、`collection_table.py`、`generation_bar.py`、`json_editor.py`、`live_preview.py`、`project_tree.py`、`property_panel.py` | 7 |
| — | **合计** | | **32** |

> 删除整个目录即包含以上 32 个文件；`gui/schema/gui_overrides.json` 与 `gui/i18n/*.json` 均在此目录内（见 1.3）。

### 1.2 `pyproject.toml` 中需要删除的行

| 行号 | 原文 | 归属 |
|------|------|------|
| 18 | `gui = ["PySide6>=6.7,<7"]` | `[project.optional-dependencies]` |
| 22 | `stnp-editor-gui = "stnp_editor.gui.launcher:main"` | `[project.scripts]` entry point |
| 36 | `"gui/schema/*.json",` | `[tool.setuptools.package-data] stnp_editor` |
| 37 | `"gui/i18n/*.json",` | `[tool.setuptools.package-data] stnp_editor` |

**待删行数：4 行**（3 个逻辑条目：optional dependency、entry point、package-data 两条）。
删除后 `[project.optional-dependencies]` 仅剩 `dev`，`[project.scripts]` 仅剩 `stnp-editor`，package-data 仅剩 `config.json`、`schemas/*.json`、`templates/**/*.j2`。

### 1.3 `gui_overrides.json`、i18n 文件的精确路径

| 类型 | 精确路径 | 是否在 1.1 的 32 文件内 |
|------|----------|--------------------------|
| GUI 覆盖配置 | `src/stnp_editor/gui/schema/gui_overrides.json` | 是 |
| 中文 i18n | `src/stnp_editor/gui/i18n/zh_CN.json` | 是 |
| 英文 i18n | `src/stnp_editor/gui/i18n/en_US.json` | 是 |

> 仓库根**不存在**独立于包目录的 `gui_overrides.json`；仅上述一处。

### 1.4 测试清理

#### 1.4.1 整体删除的测试文件

| 文件 | 行数 | 删除理由 |
|------|------|----------|
| `tests/test_gui_core.py` | 456 | 模块顶层 `import` 即 `from stnp_editor.gui.document import ProjectDocument`（第 8 行）与 `from stnp_editor.gui.schema import SchemaAdapter`（第 9 行）；`gui/` 删除后整个模块无法导入，必须整文件删除。 |

`tests/test_gui_core.py` 内的测试函数（整文件删除后一并移除）：
`test_project_document_preserves_unknown_fields`、`test_document_set_same_value_does_not_notify`、`test_schema_adapter_follows_module_notification_kind`、`test_schema_adapter_has_collection_defaults`、`test_auto_notify_dynamic_choices_filter_kind_and_payload`、`test_returncode_only_module_builds_ir`、`test_save_format_is_readable_json`、`test_returncode_only_module_generates_strict_c`、`test_gui_hex_editor_overrides`、`test_hex_input_and_display_helpers`、`test_translation_catalogs_have_core_gui_keys`、`test_document_deleted_path_falls_back_to_parent`、`test_gui_inline_collection_policy`、`test_project_tree_omits_inline_collection_items`、`test_generation_target_is_single_select_with_language_panels`、`test_generation_target_is_kept_in_target_neutral_ir`、`test_generation_target_validation_accepts_python`、`test_generation_sdks_are_target_specific`、`test_empty_project_exposes_target_specific_generation_defaults`、`test_gui_defaults_upgrade_old_generation_layout`、`test_generation_build_system_is_language_specific`、`test_instance_module_choices_follow_current_project_modules`、`test_product_version_is_0_8_0`、`test_project_tree_rebuild_ignores_reentry`、`test_gui_scalar_edit_does_not_recurse`（共 25 个）。

> 注：其中 `test_returncode_only_module_builds_ir`、`test_returncode_only_module_generates_strict_c`、`test_save_format_is_readable_json`、`test_generation_target_is_kept_in_target_neutral_ir`、`test_product_version_is_0_8_0` 等 5 个并非 GUI 逻辑测试，只是寄居在该文件内。若需保留，必须在**另一非 gui 测试文件**中重建（本阶段只提示，不实施）。

#### 1.4.2 仅部分引用、需删除局部内容的测试

| 文件 | 保留/删除 | 需删除的测试函数或行 | 精确位置 |
|------|-----------|----------------------|----------|
| `tests/test_generate_multi.py` | 文件保留 | 函数 `test_module_impl_naming_avoids_old_keil_collision` 中的 1 行 `"handler_mode": "typed",` | 第 1092 行 |

> 该函数构造的 module dict 会经 `module.schema.json` 校验，而该 schema 为 `additionalProperties: false`；`handler_mode` 删除后此键必须同时删除，函数其余断言不变。
>
> `groups` 字段在 `tests/` 下**无任何引用**（`test_generate_multi.py` / `test_generate_python.py` / `test_vectors.py` / `test_golden_targets.py` 均无）。

### 1.5 源码中对 gui 的引用点（`src/stnp_editor/`，`gui/` 之外）

**结论：`gui/` 之外不存在任何 `import stnp_editor.gui...` 或对 gui 的运行时调用。** 逐文件核对：

| 文件 | 引用性质 | 位置 | 处理 |
|------|----------|------|------|
| `src/stnp_editor/loader.py` | 仅文档字符串提及 GUI（非 import、非调用） | 第 54–55 行（`load_project_data` docstring："This is the GUI-facing loader…"）、第 65 行（`load_protocol_data`："…for GUI import."）、第 70 行（`save_protocol_data`："…for GUI export."） | 保留文件，改写 3 处 docstring 措辞 |
| `src/stnp_editor/cli.py` | 无 gui 引用 | — | 不改 |
| `src/stnp_editor/__init__.py`、`__main__.py` | 无 gui 引用 | — | 不改 |

> 附带说明（非 gui 引用，但属 GUI 配套 API）：`loader.py` 的 `load_protocol_data()`（第 64 行）与 `save_protocol_data()`（第 69 行）当前无 CLI 调用方，是 GUI 导入/导出协议 JSON 的配套函数。删除 GUI 后可评估一并删除；本方案将其列为「保留但需改动」中的待议项，不强制删除。

### 1.6 `.stnp` 的 `groups` 与 `modules[].handler_mode` 全部出现位置

#### 1.6.1 `groups`（GUI 专用分组字段）

| 类别 | 精确路径 | 位置 | 处理 |
|------|----------|------|------|
| schema | `src/stnp_editor/schemas/stnp.schema.json` | 第 70–86 行（`"groups"` 定义块，description 为 `"GUI-only folders; ignored by the generator."`） | **删除整块** |
| 示例 | `examples/` 下 3 个 `.stnp` | **不存在**（3 个示例均无 `groups`） | 无需处理 |
| 源码 | `src/stnp_editor/`（非 gui） | **不存在**读取方；`ir/models.py:129` 与 `ir/builder.py:367,371,407` 的 `notify_groups` 是 `NotifyGroupIR`（D15 范畴），与 `.stnp groups` **同名不同物** | 不混淆 |
| 源码 | gui | `src/stnp_editor/gui/i18n/zh_CN.json:76`（`"field.groups": "分组"`）、`en_US.json:76`（`"field.groups": "Groups"`） | 随 gui/ 目录删除 |
| 文档（现行） | `docs/02_JSON_FORMAT.md` | 第 49 行（根字段表）、第 257–262 行（§3.9 `groups[]` 整节） | **删除** |
| 文档（0.9 设计稿） | `docs/STNP_STRUCTURE.md` | 第 720–721 行（§8.1 表两行）、第 1108 行、第 1152 行、第 1226 行 | **删除/改述** |
| 文档（0.9 规范稿） | `docs/STNP_SPEC_0.9.md` | 第 400–401 行（字段表两行） | **删除两行** |
| 文档（差异分析） | `docs/IR_CLI_0.9_DIFF.md` | 第 95 行（引号内提到 `groups`） | 改述或标注为历史 |
| 文档（历史） | `docs/archive/DESIGN_EDITOR_V2.3.md:287` | 历史设计记录 | **保留**（archive 不属 0.9 清理范围） |

#### 1.6.2 `modules[].handler_mode`

| 类别 | 精确路径 | 位置 | 处理 |
|------|----------|------|------|
| schema | `src/stnp_editor/schemas/module.schema.json` | 第 20–26 行（`"handler_mode"` 定义块，`enum:["typed"]`，`default:"typed"`） | **删除整块** |
| 示例 | `examples/C/multi_demo/multi_demo.stnp` | 第 53、142、222 行（CHASSIS / MOTOR / SENSOR） | **删除 3 行** |
| 示例 | `examples/C/handshake_demo/handshake_demo.stnp` | 第 44 行（LINK） | **删除 1 行** |
| 示例 | `examples/python/python_demo/python_demo.stnp` | 第 23、49 行（LINK / SENSOR） | **删除 2 行** |
| 测试 | `tests/test_gui_core.py` | 第 88 行（`_returncode_only_project`） | 整文件删除（见 1.4.1） |
| 测试 | `tests/test_generate_multi.py` | 第 1092 行 | 删除该行（见 1.4.2） |
| 源码（gui） | `src/stnp_editor/gui/defaults.py:31`、`gui/schema/gui_overrides.json:78`、`gui/i18n/zh_CN.json:54`、`gui/i18n/en_US.json:54` | GUI 默认值与 i18n | 随 gui/ 目录删除 |
| 源码（非 gui） | `src/stnp_editor/ir/builder.py` 等 | **不存在**读取方（生成器从未消费该字段） | 无 |
| 文档（现行） | `docs/02_JSON_FORMAT.md` | 第 161 行（字段表行） | **删除该行** |
| 文档（0.9 设计稿） | `docs/STNP_STRUCTURE.md` | 第 829 行（§8.5 表）、第 1107 行、第 1224 行 | **删除/改述** |
| 文档（0.9 规范稿） | `docs/STNP_SPEC_0.9.md` | 第 478 行（字段表）、第 665、688 行（附录示例两处） | **删除 1 行 + 2 处示例键** |
| 文档（差异分析） | `docs/IR_CLI_0.9_DIFF.md` | 第 19–25 行（D2 差异）、第 291–294 行（P12 提案） | 改述或标注为历史 |
| 文档（历史） | `docs/archive/DESIGN_EDITOR_V1.md:283`、`docs/archive/DESIGN_EDITOR_V2.md:255,528` | 历史设计记录 | **保留** |

### 1.7 文档中的 GUI 表述（清理范围）

| 文档 | 位置 | 处理 |
|------|------|------|
| `docs/architecture/gui.md` | 整个文件（GUI 架构专文） | **删除整文件** |
| `docs/architecture/README.md` | 第 24 行（`- [GUI 架构](gui.md)`） | 删除该链接行 |
| `docs/README.md` | 第 15 行（第 5 章"Generator / Runtime / GUI 架构"）、第 35 行（"GUI 按语言展示独立生成配置"） | 改述为 Generator / Runtime |
| `docs/01_GETTING_STARTED.md` | 第 233–240 行（§1.6 GUI 整节，含 `pip install -e '.[gui]'`、`stnp-editor-gui` 命令） | **删除整节** |
| `docs/02_JSON_FORMAT.md` | 第 49、53、178、257–262、305 行（GUI 字样与 groups 节） | 删除/改述 |
| `docs/MIGRATION.md` | 第 5 行（"GUI 打开旧工程后会迁移为…"）、第 19–21 行（0.7.1 GUI 外观节） | 删除/改述 |
| `docs/CHANGELOG.md` | 第 31–33、39–44、74、104、134、139、146、150 行（历史版本记录中的 GUI） | **保留**（历史变更记录，不改写） |
| `docs/UPGRADE_0.6.1/0.7.0/0.7.1/0.8.0/0.8.2_CHECKLIST.md` | 各自 GUI 勾选行 | **保留**（历史清单） |
| `README.zh-CN.md` | 第 9 行（"GUI 的生成目标为单选下拉…"） | 改述 |
| `docs/archive/**` | 多处 GUI 设计 | **保留**（历史资料） |

### 1.8 计数汇总

**删除项总数**

| 类别 | 单元 | 数量 |
|------|------|------|
| 文件/目录整体删除 | `src/stnp_editor/gui/`（32 文件，含 `gui_overrides.json` + 2 个 i18n） | 1 目录 / 32 文件 |
| 文件整体删除 | `tests/test_gui_core.py` | 1 文件 |
| 文件整体删除 | `docs/architecture/gui.md` | 1 文件 |
| `pyproject.toml` 删除行 | 第 18、22、36、37 行 | 4 行 |
| schema 删除块 | `stnp.schema.json` groups 块（70–86）、`module.schema.json` handler_mode 块（20–26） | 2 块 |
| 示例删除行 | 3 个 `.stnp` 的 `handler_mode` | 6 行 |
| 测试删除行 | `test_generate_multi.py:1092` | 1 行 |
| 文档删除行/节 | `02_JSON_FORMAT.md`（49、161、257–262）、`STNP_STRUCTURE.md`（720–721、829、1107–1108、1152、1224、1226）、`STNP_SPEC_0.9.md`（400–401、478、665、688）、`01_GETTING_STARTED.md` §1.6、`architecture/README.md:24`、`IR_CLI_0.9_DIFF.md`（19–25、95、291–294） | 约 30 行 / 2 节 |

> **删除项总数**：待删文件 **34** 个（`src/stnp_editor/gui/` 32 + `tests/test_gui_core.py` 1 + `docs/architecture/gui.md` 1）+ `pyproject.toml` 4 行 + schema 2 块 + 示例 6 行 + 测试 1 行 + 文档约 30 行 / 2 节。

**保留但需改动项总数**

| 类别 | 文件 | 数量 |
|------|------|------|
| 测试局部改动 | `tests/test_generate_multi.py` | 1 |
| 源码 docstring 改动 | `src/stnp_editor/loader.py` | 1 |
| 配置迁移改动 | `pyproject.toml`（除删除外，package-data 需确认 config.json 归属） | 1 |
| 示例迁移改动 | 3 个 `.stnp`（删 `generation`、改 `schema_version`）+ 新增 3 个 `stnp.build.json` | 3 |
| 文档改述 | `docs/README.md`、`README.zh-CN.md`、`docs/MIGRATION.md`、`docs/02_JSON_FORMAT.md` | 4 |
| 文档 0.9 同步 | `docs/STNP_STRUCTURE.md`、`docs/STNP_SPEC_0.9.md`、`docs/IR_CLI_0.9_DIFF.md` | 3 |
| 待议 | `loader.py` 的 `load_protocol_data` / `save_protocol_data` | 1 |

> **保留但需改动项总数：约 14 个文件/条目**（不含本方案文档本身）。

---

## 二、C2 命名定案

### 2.1 源码证据（逐条引用）

| # | 文件:行 | 源码表达式 | 含义 |
|---|---------|-----------|------|
| E1 | `src/stnp_editor/ir/builder.py:135` | `stem = validate_output_stem(output_stem or project.get("project_name") or "stnp")` | `output_stem` 决定**主干（stem）**；优先级：显式 `output_stem` > `project_name` > 字面量 `"stnp"` |
| E2 | `src/stnp_editor/ir/builder.py:138` | `lang_dir = settings.output_dir_name(target)` | 按 `target` 查**目标后缀目录名** |
| E3 | `src/stnp_editor/ir/builder.py:151` | `output_dir_name=f"{stem}_{lang_dir}"` | 最终目录名 = **stem + 下划线 + lang_dir** |
| E4 | `src/stnp_editor/settings.py:65-67` | `def output_dir_name(self, target): names = self._data.get("output_dir_names", {}); return names.get(target, f"STNP_{target.upper()}")` | `lang_dir` 来自 `config.json` 的 `output_dir_names`（`c` → `STNP_C`，`python` → `STNP_Python`） |
| E5 | `src/stnp_editor/config.json:13-16` | `"output_dir_names": { "c": "STNP_C", "python": "STNP_Python" }` | 后缀常量来源 |
| E6 | `src/stnp_editor/loader.py:125-126` | `fallback_stem = source_path.stem if source_path is not None else data.get("project_name", "stnp")`；`output_stem = gen.get("output_stem") or fallback_stem` | 未显式给 `output_stem` 时，回退到 `.stnp` 文件名 stem，其次 `project_name` |
| E7 | `src/stnp_editor/emit_c/emitter.py:18-27` | `def resolve_stnp_c_root(output, stem): stem = validate_output_stem(stem); dir_name = f"{stem}_{settings.output_dir_name(TARGET)}"` | 发射器**用同一公式重算**同一目录名 |
| E8 | `src/stnp_editor/emit_python/emitter.py:14-23` | 同上（`TARGET = "python"`） | Python 侧同公式 |
| E9 | `src/stnp_editor/cli.py:59-63` | `golden_target = golden_root / ir.output_dir_name if (golden_root / ir.output_dir_name).is_dir() else golden_root` | `check` 用 `ir.output_dir_name` 定位 golden 子树 |

### 2.2 结论：最终文件夹名 = `{output_stem}_{output_dir_names[target]}`

**两处命名是「组合（乘法）」关系，不是「竞争（二选一）」关系；不存在双重命名冲突。**

- `output_stem`（E1/E6）只提供**主干**，是唯一的可变输入；
- `output_dir_names[target]`（E2/E4/E5）只提供**按目标固定的后缀**，不参与主干选择；
- 最终目录名由 E3 一次性拼出，E7/E8 在发射器中用**同一公式**复算，结果恒等；
- 因此二者不互相覆盖：改 `output_stem` 只改前缀，改 `output_dir_names` 只改后缀，**没有"依赖其一"的歧义**。

**对 C2 待查项的逐条回答：**

| C2 待查项 | 结论 |
|-----------|------|
| `output_stem` 与 `output_dir_name` 的关系——最终工程文件夹名由谁决定 | 由**两者组合**决定：`output_dir_name = f"{output_stem}_{output_dir_names[target]}"`；没有任何一方单独决定 |
| `layout.output_dir_names` 与 `output_stem` 是否构成双重命名 | **不构成**。`output_stem` 是前缀主干，`output_dir_names` 是按目标固定后缀；语义正交，组合公式唯一 |

**唯一需要标注的次要事实（非冲突）：**

1. `ir/models.py:194-195` 给 `output_stem` / `output_dir_name` 设了默认值（`""` / `"STNP_C"`）。`builder.py` 总会覆盖这两个字段（E1/E3），默认值仅在绕过 builder 手工构造 `ProjectIR` 时生效；D12 已裁定 `output_dir_name` 改为生成期局部量，届时该默认值随字段一起移除。
2. `resolve_*_root`（E7/E8）有一条便利分支：若传入的 `output` 目录名**已等于** `dir_name`，则直接复用该目录（不再追加子目录）。这只是"父目录 vs 工程目录"的容错，不是第二个命名来源。

### 2.3 迁移方案

| 字段 | 现位置 | 新位置（`stnp.build.json`） | 公式 |
|------|--------|------------------------------|------|
| `output_stem` | `.stnp` 的 `generation.output_stem` | **顶层** `output_stem` | 不变 |
| `output_dir_names` | `src/stnp_editor/config.json` 顶层 | `layout.output_dir_names` | 不变 |

**组合公式保持不变：**

```
最终工程文件夹名 = f"{output_stem}_{layout.output_dir_names[target]}"
```

- `target` 取 `stnp.build.json` 顶层必填单选 `target`（D8/D17/D18）；
- `output_stem` 未给时仍回退 `.stnp` 文件名 stem / `project_name`（E6，D3 不涉及此字段）；
- `layout.output_dir_names` 缺省时回退 `STNP_{target.upper()}`（E4）。

**0.9 文档需同步的表述位置：**

| 文档 | 位置 | 需同步内容 |
|------|------|-----------|
| `docs/STNP_STRUCTURE.md` | 第 748 行、第 1164 行（`generation.output_stem`） | 改为 `stnp.build.json` 顶层 `output_stem` |
| `docs/STNP_STRUCTURE.md` | 第 705 行（`.stnp` 根 required 含 `generation`）、第 726–753 行（§8.2 生成配置整节）、第 1153、1160–1166 行 | 改为 `stnp.build.json` 字段表 |
| `docs/STNP_SPEC_0.9.md` | 第 423 行（`generation.output_stem` 表行）、第 731 行（示例 `output_stem`）、第 744 行（`generation` 冻结字段集） | 改为 build 文件顶层 |
| `docs/IR_CLI_0.9_DIFF.md` | 第 29 行、第 195 行、第 278 行（`output_dir_name` / `output_stem` 讨论） | 补记 C2 结论（组合关系、非冲突）与 `layout` 归属 |
| `docs/02_JSON_FORMAT.md` | 第 287、302、315 行（现行 `output_stem` 说明） | 迁至 build 文件说明 |
| `docs/architecture/generator.md` | 第 51 行（`output_stem` 安全约束） | 改为 build 文件字段 |
| 目录命名示例 | `docs/01_GETTING_STARTED.md:7,140`、`docs/guides/PYTHON_USAGE.md:11,25`、`docs/PYTHON_TARGET_0.8.0.md:20,76`、`docs/CHANGELOG.md:114` | 公式不变，无需改值；仅确认与新配置来源一致 |

> **复核结论与任务给出的描述一致**：`{output_stem}_{output_dir_names[target]}` 为组合关系，不存在双重命名冲突。无需修正。

---

## 三、示例与 golden 迁移方案

### 3.1 `examples/` 下全部 `.stnp`（共 3 个）

`examples/` 下仅 3 个 `.stnp`（`examples/dual_STM32_Python_integration.zip` 为打包件，不含 `.stnp`）：

1. `examples/C/multi_demo/multi_demo.stnp`
2. `examples/C/handshake_demo/handshake_demo.stnp`
3. `examples/python/python_demo/python_demo.stnp`

`examples/` 下 3 个 `.stnp` 与配套 `stnp.build.json` **不在本次迁移范围**。0.9 落地后由人工重写，**不逐字段迁移**。本次仅删除其中已废弃的字段（`handler_mode`），其余不动。

### 3.2 `tests/golden/` 目录结构与被影响 golden 树

#### 3.2.1 目录结构

```
tests/golden/
├── README.md
├── C/
│   └── multi_demo/
│       ├── vectors.json
│       └── multi_demo_STNP_C/                 ← golden 树（C 目标）
│           ├── .stnp-manifest.json
│           ├── README.md
│           ├── Core/  (stnp.h, stnp_codec.*, stnp_core.*, stnp_frame.*,
│           │           stnp_notify.*, stnp_router.*, stnp_runtime.*,
│           │           stnp_task.*, stnp_vtl.*)
│           ├── Embedded/docs/note.md
│           ├── Examples/ (main.c, transport_mock.c, transport_mock.h)
│           ├── Implementation/ (chassis_impl.c, motor_impl.c, sensor_impl.c,
│           │                     stnp_notify_callback.c)
│           ├── Instance/ (stnp_instances.c, stnp_instances.h)
│           ├── Module/ (stnp_module.c/h, Chassis/*, Motor/*, Sensor/*)
│           └── Platform/ (stnp_platform.h, stnp_platform_config.h, stnp_types.h)
└── python/
    └── python_demo/
        └── python_demo_STNP_Python/            ← golden 树（Python 目标）
            ├── .stnp-manifest.json
            ├── README.md
            ├── pyproject.toml
            ├── config/stnp.yaml
            ├── Example/ (README.md, main.py, mock_serial.py)
            └── stnp/ (core/*, protocol/*, sdk/uart/*)
```

**受影响 golden 树：2 个**（`tests/golden/C/multi_demo/multi_demo_STNP_C/`、`tests/golden/python/python_demo/python_demo_STNP_Python/`）。对应的驱动测试：`tests/test_golden_targets.py`（`test_c_multi_demo_matches_c_golden`、`test_python_demo_matches_python_golden`）。

#### 3.2.2 批次一（本次迁移）：必须保持不变（不得重新生成）

**批次一 = GUI 清理 + 配置拆分 + C2 命名。golden 零改动，两个 golden 树都必须逐字节保持一致；提交信息标注为「迁移批次」。**

理由：

1. `handler_mode` 从未被生成器消费（1.6.2 已证）；从 `.stnp` 删除它不改变 IR，也不改变模板输出。
2. `groups` 从未被生成器消费（1.6.1 已证）；本就不在示例中。
3. `generation` 段只是**配置来源迁移**（`.stnp` → `stnp.build.json`），配置值本身不变（`target`/`build_system`/`sdks`/`emit_examples`/`emit_readme` 逐一保留），故 IR 与输出不变。
4. `output_stem` 与 `output_dir_names` 迁移后**组合公式不变**（§2.3），目录名仍为 `multi_demo_STNP_C` / `python_demo_STNP_Python`，与 golden 树名一致。
5. `schema_version` 从整数改字符串不进入 IR（D4 明确"不进入 IR"），不影响生成。

**验证方式**：迁移后运行 `tests/test_golden_targets.py`，`_diff_trees`（`cli.py:84-110`）必须返回空差异；`.stnp-manifest.json` 的文件清单与 `kind` 亦须不变。

#### 3.2.3 批次二（协议裁定）：需要重新生成的 golden

**批次二 = 以下协议裁定落地。两个 golden 树整体重新生成；提交信息标注为「协议批次」。** 逐项影响如下：

| 裁定 | 对 golden 的影响 |
|------|------------------|
| D5（P2 移除 `crc_runtime_toggle`） | 删 `ProtocolIR.crc_runtime_toggle`，CRC 槽存在性只由 `features.crc.enabled` 决定；改 `stnp_platform_config.h` / runtime 的 `STNP_CRC_Enable/Disable/IsEnabled` 等生成产物 |
| D6（SEQ 门控，Task/Notify 共用门控与计数器） | 改 `protocol.yaml` / runtime / 帧常量等生成产物 |
| D7（删 `features.notify_dispatcher`，新增 `protocol.options.notify_dispatch_receive`） | 改 `protocol.yaml` / `stnp_platform_config.h` / runtime 等生成产物 |
| D10（帧头长按 §3.5 矩阵计算） | 改帧结构常量与 runtime |
| D13（Task/Notify 头长、CRC 尾、RX Ring 预留） | 改帧结构常量与 runtime |
| D14（Return Code 分段） | 改 return code 校验与常量 |
| D15（删 `NOTIFY_KIND_VALUES` / `STNP_NOTIFY_KIND_*` / `NotifyGroupIR` / `NotificationIR.kind`） | 改 Notify enum、dispatch、模板输出 |
| D16（P3 CRC 覆盖范围固定为 body） | 改 CRC 计算与帧结构；**本身属「确认现状已符合」**（见 `03_IR生成侧CLI.md` §2.5），列入批次二仅为与 D5 的 CRC 实现改动同批追溯 |

> 注：**D11 不列入批次二**——它属「确认现状已符合」，无代码改动（见 `03_IR生成侧CLI.md` §2.2）。

> 结论：**批次一（迁移）= 0 个 golden 重新生成，逐字节保持不变；批次二（协议裁定）= 2 个 golden 树整体重新生成。** **两批不得混在同一次提交**，否则 golden diff 无法归因。

### 3.3 `pyproject.toml` 中 `config.json` 相关 package-data 与依赖

| 项 | 现状 | 处理 |
|----|------|------|
| package-data `"config.json"` | `pyproject.toml:33` | **保留不变**：`config.json` 保留为生成器内部资源文件（`schemas_dir` / `schema_files` / `templates` / `dir_names` / `sdks` 注册表 / `python_sdks` 注册表留在生成器内部），**不删除**；仅 `output_dir_names` 与 `emit_examples` 迁出到 `stnp.build.json`（`output_dir_names` → `layout.output_dir_names`）。`stnp.build.schema.json` 仍由现有 `"schemas/*.json"` 覆盖，无需新增行 |
| `"schemas/*.json"` | `pyproject.toml:34` | 保留；新增 `stnp.build.schema.json` 自动被匹配 |
| `"templates/**/*.j2"` | `pyproject.toml:35` | 保留不变 |
| `"gui/schema/*.json"` | `pyproject.toml:36` | **删除**（见 1.2） |
| `"gui/i18n/*.json"` | `pyproject.toml:37` | **删除**（见 1.2） |
| 依赖 `gui = ["PySide6>=6.7,<7"]` | `pyproject.toml:18` | **删除**（见 1.2）；核心 `dependencies`（`jinja2`、`jsonschema`）不变 |
| entry point `stnp-editor-gui` | `pyproject.toml:22` | **删除**（见 1.2）；保留 `stnp-editor = "stnp_editor.cli:main"` |

> **依赖结论**：删除 GUI 后 `PySide6` 从可选依赖中移除，`pyproject.toml` 无其他依赖变更。`config.json`（`src/stnp_editor/config.json`）**保留为生成器内部资源文件**，不删除；其内部资源（`schemas_dir` / `schema_files` / `templates` / `dir_names` / `sdks` 注册表 / `python_sdks` 注册表）留在生成器内部，不进 `stnp.build.json`。仅 `output_dir_names` 与 `emit_examples` 迁出到 `stnp.build.json`（`output_dir_names` → `layout.output_dir_names`），需与 `settings.py` 相应调整同步进行（§2.3）。

---

## 四、执行顺序建议（供后续实施阶段参考，本阶段不实施）

1. 先删 `src/stnp_editor/gui/`（32 文件）+ `tests/test_gui_core.py` + `docs/architecture/gui.md`。
2. 清 `pyproject.toml` 4 行（entry point / gui 依赖 / 2 条 package-data）。
3. 清 schema 2 块（`groups`、`handler_mode`），同步清 3 个示例的 6 行 `handler_mode` 与 `test_generate_multi.py:1092`。
4. 删除 3 个示例中的 `handler_mode` 行（其余不动；示例迁移不在本次范围）。
5. 改 `loader.py` 3 处 docstring；同步 0.9 文档（§2.3 与 §1.6/1.7 列出的位置）。
6. **回归锁**：`tests/test_golden_targets.py` 必须通过且 golden 零 diff；`test_generate_multi.py` / `test_generate_python.py` / `test_vectors.py` 按新配置来源更新用例。
