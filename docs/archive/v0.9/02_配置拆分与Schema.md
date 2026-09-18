# STNP Editor 配置拆分与 Schema 设计

> 阶段一·定方案 交付物 02（只出方案，不改任何代码 / schema / config 文件）。
> 输入依据：`docs/IR-CLI-决策.md`（「配置拆分补充裁定」全节，以及 D4 / D8 / D9 / D12）、`docs/STNP_SPEC_0.9.md`（§8.1 根 required、§8.2 generation）、现状 4 个 schema、`src/stnp_editor/config.json`、`settings.py`、`loader.py`、`generation.py`。
> 全文区分【现状】与【方案】；【现状】逐字来自当前源码 / schema，【方案】为本设计稿结论。

---

## 一、文件拆分定案

生成配置从 `.stnp` 拆出，独立为 `stnp.build.json`（D8）。两份文件各有一份 `format`，各自独立校验。

### 1.1 `.stnp`（工程 / 协议事实源）

| 字段 | 类型 / 形态 | 职责 | 备注 |
|---|---|---|---|
| `format` | `const "stnp"` | 文件格式标识 | 保留 |
| `schema_version` | string，`"stnp-schema-alpha"` | `.stnp` 文件格式版本 | 改自 integer（见六） |
| `project_name` | string | 工程名 | 保留 |
| `protocol` | object | 协议配置容器 | 保留 |
| `global_results` | array（`minItems 1`） | 工程级 Result 码表 | 现状 schema 缺失，本次补入 required（见七） |
| `common_types` | object | 通用类型容器 | 保留，可选 |
| `modules` | array（`minItems 1`） | Module 定义数组 | 保留 |
| `instances` | array（`minItems 1`） | 可路由实例数组 | 保留 |

【现状】`.stnp` 还含 `generation`（生成配置）与 `groups`（GUI 专用）；两者在方案中删除（`generation` 迁出到 build 文件，`groups` 随 B1 删除）。
【方案】`embedded_files` 不在本次裁定范围内，**保留现状不动**，列为待议，不在本稿处置。

### 1.2 `stnp.build.json`（生成配置）

| 字段 | 类型 / 形态 | 职责 | 备注 |
|---|---|---|---|
| `format` | `const "stnp-build"` | 文件格式标识 | 新增 |
| `build_schema_version` | string，`"stnp-build-schema-alpha"` | build 文件格式版本 | 新增，独立维护（见六） |
| `target` | string，`enum ["c","python"]` | 生成目标，**必填单选** | 由 `generation.target` 迁入；删除 `targets` 复数与回退链 |
| `c` | object | C 目标配置 | 由 `generation.c` 迁入 |
| `python` | object | Python 目标配置 | 由 `generation.python` 迁入 |
| `output_stem` | string | 输出文件名主干 | 由 `generation.output_stem` 迁入 |
| `emit_readme` | boolean，默认 `true` | 是否生成 README | 由 `generation.emit_readme` 迁入 |
| `validations` | array（`id` / `level`） | 校验规则清单，默认全列全启用 | 由 D12 新增 |
| `layout` | object | 生成产物目录布局（`output_dir_names`） | 承接 `config.json.output_dir_names` |
| `sdks` | array | **C SDK 选择列表**（用户选择，非注册表） | 由 `generation.c.sdks` 上提；与内部注册表同名但语义不同 |
| `python_sdks` | array | **Python SDK 选择列表**（用户选择，非注册表） | 由 `generation.python.sdks` 上提 |

> **命名消歧（重要）**：`stnp.build.json` 的 `sdks` / `python_sdks` 是**用户选择数组**；`config.json` 里的 `sdks` / `python_sdks` 是**生成器内部注册表**（含 `label` / `template_dir` / `output_dir` / `files` / `namespace`），后者不进入 build 文件（见四）。二者同名不同义，阶段二落地时应把内部注册表键名改为 `c_sdk_registry` / `python_sdk_registry` 以消除歧义（仅列符号，不写实现）。

### 1.3 两文件关系

- 各自独立：`.stnp` 与 `stnp.build.json` 分别有自己的 `format` 与版本标识，互不引用、互不嵌套。
- 不做旧格式适配：不读取 `.stnp` 内的 `generation`，不保留任何回退链（D4 / 补充裁定七）。
- CLI 入口：`generate` / `check` 增加参数指定 `stnp.build.json` 路径（补充裁定八）；CLI 只按 build 文件的单一 `target` 分派（D17）。

---

## 二、`.stnp` 根 required 变更

【现状】`stnp.schema.json` 根 `required`（逐字）：

```json
["format", "schema_version", "project_name", "protocol", "modules", "instances", "generation"]
```

【方案】删除 `generation`，并补入 `global_results`（SPEC §8.1 与七节均要求其必填，而现状 schema 完全未声明该属性）。变更后：

```json
["format", "schema_version", "project_name", "protocol", "modules", "instances", "global_results"]
```

| 项 | 动作 | 依据 |
|---|---|---|
| `generation` | 从 `required` 删除，并从 `properties` 整体删除 | D8；生成配置迁出至 `stnp.build.json` |
| `global_results` | 加入 `required`，并新增对应 `properties`（`minItems 1`） | SPEC §8.1；七节要求 |
| 其余 5 项 | 不变 | 补充裁定二「其余不变」 |

`additionalProperties: false` 保留；`common_types` 仍为可选，不进 required。

---

## 三、字段归属变更表

| 字段 | 原位置 | 新位置 | 备注 |
|---|---|---|---|
| `target` | `generation.target` | `stnp.build.json` 顶层，必填单选 | 删除 `targets` 复数、`build_system` / `sdks` / `emit_examples` 顶层回退形态与 `anyOf` 回退链；非法值由 Schema `enum` 在加载期拒绝（D18 / D19） |
| `c` | `generation.c` | `stnp.build.json` 顶层 `c` | 子对象保留 `build_system` / `emit_examples`；`sdks` 上提为顶层 `sdks` |
| `python` | `generation.python` | `stnp.build.json` 顶层 `python` | 子对象保留 `build_system` / `emit_examples` / `emit_user_scaffold`；`sdks` 上提为顶层 `python_sdks` |
| `output_stem` | `generation.output_stem` | `stnp.build.json` 顶层 | 保留 `minLength 1`；生成期仍走 `validate_output_stem()` |
| `emit_readme` | `generation.emit_readme` | `stnp.build.json` 顶层 | 默认 `true` |
| `emit_examples` | `generation.<target>.emit_examples`（同时另有 `config.json.emit_examples` 全局项） | `stnp.build.json` 的 `<target>.emit_examples` | D9：取值**只**来自 `<target>.emit_examples`，默认 `false`；删除全局项 |
| `config.json` → `output_dir_names` | `config.json.output_dir_names` | `stnp.build.json.layout.output_dir_names` | 唯一迁出的用户可调目录项（见四） |
| `config.json` → `emit_examples` | `config.json.emit_examples` | `stnp.build.json.<target>.emit_examples` | 与上一行 `emit_examples` 合并为同一目标字段 |
| `config.json` → `schemas_dir` | `config.json.schemas_dir` | **留在生成器内部** | 生成器资源定位，不进 build 文件（见四） |
| `config.json` → `schema_files` | `config.json.schema_files` | **留在生成器内部** | 同上 |
| `config.json` → `templates` | `config.json.templates` | **留在生成器内部** | 同上 |
| `config.json` → `dir_names` | `config.json.dir_names` | **留在生成器内部** | 同上 |
| `config.json` → `sdks`（注册表） | `config.json.sdks` | **留在生成器内部** | 与 build 顶层 `sdks`（选择列表）不同义（见四） |
| `config.json` → `python_sdks`（注册表） | `config.json.python_sdks` | **留在生成器内部** | 与 build 顶层 `python_sdks`（选择列表）不同义（见四） |
| `config.json` 文件本体 | 独立文件 | 保留为生成器内部资源文件 | **不整体并入 build 文件**（见四，对 D9 字面表述的收敛） |

---

## 四、`config.json` 处置定案（关键决策点）

### 4.1 问题

【现状】`config.json`（`src/stnp_editor/config.json`，由 `pyproject.toml` 的 package-data 打包）混装两类内容：

1. **生成器内部资源**：`schemas_dir` / `schema_files` / `templates` / `dir_names` / `sdks` 注册表 / `python_sdks` 注册表；
2. **用户可调项**：`output_dir_names` / `emit_examples`。

D9 的字面表述是「删除 `config.json`，其内容并入 `stnp.build.json`」。若照字面执行，会把生成器的实现资源一并暴露给用户，这是本方案明确否定的。

### 4.2 处置原则与理由

**定案：`config.json` 不整体并入 build 文件。按「内部资源 / 用户可调项」二分处置——内部资源留在生成器内部，用户可调项迁出至 `stnp.build.json`。**

理由：

1. **安全边界**：`schemas_dir` / `schema_files` / `templates` / `dir_names` 决定生成器去何处读 schema 与模板、以及内部目录如何命名。放进用户可编辑文件后，用户误改会让生成器读不到 schema、模板缺失、目录错位；故障点落在生成器内部而非用户工程，报错无法归因，且表现为生成器崩溃而非用户配置错误。
2. **职责边界**：这些键回答的是「生成器怎么实现」，不是「生成什么」。`.stnp` / `stnp.build.json` 只承载工程语义与生成选择；实现资源不属于用户可见语义层。
3. **稳定性 / 兼容承诺**：`sdks` / `python_sdks` 注册表含 `label` / `template_dir` / `output_dir` / `files` / `namespace`，是随生成器版本演进的实现资源。一旦暴露进 build 文件，用户会把它当稳定 API 依赖，锁死生成器重构（改模板目录、拆 SDK 文件都会变成破坏性变更）。
4. **对 D9 的正确解释**：D9 的意图是消除用户侧「第二份配置来源」（全局 `emit_examples` 与 `.stnp` 内生成配置并存），**不是**把生成器实现资源也交给用户。因此「内容并入」应解释为「用户可调内容并入」；生成器资源继续由内部文件承载。
5. **注册表 vs 选择列表**：用户需要的是「选了哪些 SDK」（选择列表），不是「SDK 长什么样」（注册表）。因此 build 文件只放选择列表 `sdks` / `python_sdks`，注册表留内部；加载期由注册表向选择列表注入 `enum`（延续 `loader._validate()` 现有做法，见 4.5）。

### 4.3 「留下 / 迁出」清单

| `config.json` 键 | 类别 | 处置 | 去向 | 理由 |
|---|---|---|---|---|
| `schemas_dir` | 内部资源 | **留下** | 生成器内部 | 生成器资源定位，用户改坏直接损坏生成器 |
| `schema_files` | 内部资源 | **留下** | 生成器内部 | schema 文件名映射，随生成器版本演进 |
| `templates` | 内部资源 | **留下** | 生成器内部 | 模板目录定位，属实现资源 |
| `dir_names` | 内部资源 | **留下** | 生成器内部 | 内部目录命名（Core / Module / …），属生成器布局 |
| `sdks`（注册表） | 内部资源 | **留下** | 生成器内部 | 含 `template_dir` / `output_dir` / `files`，属实现资源 |
| `python_sdks`（注册表） | 内部资源 | **留下** | 生成器内部 | 含 `namespace`，属实现资源 |
| `output_dir_names` | 用户可调项 | **迁出** | `stnp.build.json.layout.output_dir_names` | 直接影响用户可见产物目录名，属生成选择 |
| `emit_examples` | 用户可调项 | **迁出** | `stnp.build.json.<target>.emit_examples` | D9：只认 target 级开关，默认 `false` |
| `config.json` 文件本体 | — | **保留** | 生成器内部资源文件 | 承载上述「留下」项；不整体并入 build 文件 |

> 可选更名：为消除 `sdks` / `python_sdks` 的语义冲突，阶段二可将内部注册表键改名为 `c_sdk_registry` / `python_sdk_registry`；此为命名建议，不改变本定案。

### 4.4 `settings.py` 相应调整点（只列符号与职责，不写实现）

| 符号 | 现状职责 | 方案处置 |
|---|---|---|
| `DEFAULT_CONFIG_NAME` / `CONFIG_ENV_VAR` | 内部 config 文件名 / 覆盖环境变量 | 保留 |
| `package_root()` | 包根定位 | 保留 |
| `_deep_merge()` | 内部 config 深合并 | 保留 |
| `load_config()` | 加载内部 config（包内默认 + 外部覆盖） | 保留（内部资源仍由此加载） |
| `Settings.raw` | 原始内部配置 | 保留 |
| `Settings.schemas_dir` | 读 `schemas_dir` | 保留（内部资源） |
| `Settings.schema_file()` | 读 `schema_files` | 保留；需新增 `stnp_build` 键映射 |
| `Settings.template_dir()` | 读 `templates` | 保留 |
| `Settings.dir_name()` | 读 `dir_names` | 保留 |
| `Settings.sdk_definitions` / `sdk_definitions_for()` / `sdk_definition()` / `sdk_definition_for()` | 读 SDK 注册表 | 保留（注册表留内部）；供加载期注入选择列表 `enum` |
| `Settings.available_sdks` / `available_sdks_for()` | 注册表键集 | 保留；供加载期注入选择列表 `enum` |
| `Settings.output_dir_name()` | 读 `output_dir_names` | **语义变更**：数据源由内部 config 改为 build 文件的 `layout.output_dir_names`（由 build 加载器注入），符号保留 |
| `Settings.emit_examples` | 读全局 `emit_examples` | **移除 / 降级**：不再作为全局项；`emit_examples` 由 build 文件 `<target>.emit_examples` 提供，消费方（`ir/builder.py`）直接读 target 配置 |
| `settings`（模块级单例） | 全局访问点 | 保留 |
| `default_validations()`（新增符号，建议） | 导出默认 `validations` 清单（全列全启用） | 新增；供 build 文件默认值与加载期补全 |
| `c_sdk_registry` / `python_sdk_registry`（更名，建议） | 内部注册表键 | 可选更名，消除与 build 选择列表的同名歧义 |

### 4.5 `loader._validate()` 中「运行时改写 SDK enum」逻辑的重新定位

【现状】`loader._validate()` 在加载 `stnp.schema.json` 时，运行时改写该 schema 的：
- `properties.generation.c.properties.sdks.items`（及 `python` 同构）；
- 遗留 `properties.generation.sdks.items`（v0.7.1 回退形态）；
用 `settings.available_sdks_for(target)` 注入 `enum` 与 `x-enumLabels`；判定条件为 `schema_path.name == settings.schema_file("stnp")`。

【方案】配置拆分后 `.stnp` 已无 `generation`，该注入目标整体消失，逻辑必须重新定位：

| 项 | 处置 |
|---|---|
| 注入目标 | 从 `stnp.schema.json` 的 `generation.*.sdks.items` 改为 `stnp.build.schema.json` 的 `properties.sdks.items`（C，用 `available_sdks_for("c")`）与 `properties.python_sdks.items`（用 `available_sdks_for("python")`） |
| 判定条件 | `schema_path.name == settings.schema_file("stnp")` 改为匹配 build schema 文件名（`settings.schema_file("stnp_build")`） |
| 遗留分支 | 删除 `generation.sdks.items` 分支（不做任何旧格式适配，D4） |
| 归属 | 建议从通用 `_validate()` 中抽出为 build 文件专用的 schema 解析步骤，使 `_validate()` 保持纯校验；由 build 加载路径调用 |

---

## 五、`stnp.build.schema.json` 设计

### 5.1 顶层约定

- `additionalProperties: false`；顶层 `required = ["format", "build_schema_version", "target"]`。
- `target` 必填单选 `enum ["c","python"]`；`c` / `python` 子对象各自可选（按 target 生效）。
- `build_schema_version` 取值 `"stnp-build-schema-alpha"`（见六）。
- `validations` 默认由生成器导出、全列全启用；`layout` 承接 `output_dir_names`。
- `sdks` / `python_sdks` 为选择列表；其 `items.enum` 由加载期从内部注册表注入（骨架中给出代表性取值，非最终硬编码）。

### 5.2 完整结构骨架（可直接作为阶段二落地依据）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://stnp.local/schemas/stnp.build.schema.json",
  "title": "STNP build configuration",
  "type": "object",
  "additionalProperties": false,
  "required": ["format", "build_schema_version", "target"],
  "properties": {
    "format": {
      "type": "string",
      "const": "stnp-build"
    },
    "build_schema_version": {
      "type": "string",
      "enum": ["stnp-build-schema-alpha"]
    },
    "target": {
      "type": "string",
      "enum": ["c", "python"],
      "x-enumLabels": {
        "c": "C",
        "python": "Python"
      }
    },
    "c": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "build_system": {
          "type": "string",
          "enum": ["mdk_arm", "cmake"],
          "x-enumLabels": {
            "mdk_arm": "MDK-ARM",
            "cmake": "CMake"
          },
          "default": "mdk_arm"
        },
        "emit_examples": {
          "type": "boolean",
          "default": false
        }
      },
      "default": {
        "build_system": "mdk_arm",
        "emit_examples": false
      }
    },
    "python": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "build_system": {
          "type": "string",
          "const": "python",
          "default": "python"
        },
        "emit_examples": {
          "type": "boolean",
          "default": false
        },
        "emit_user_scaffold": {
          "type": "boolean",
          "default": false
        }
      },
      "default": {
        "build_system": "python",
        "emit_examples": false,
        "emit_user_scaffold": false
      }
    },
    "output_stem": {
      "type": "string",
      "minLength": 1
    },
    "emit_readme": {
      "type": "boolean",
      "default": true
    },
    "validations": {
      "type": "array",
      "description": "校验规则清单；默认由生成器导出、全列全启用。",
      "items": {
        "type": "object",
        "required": ["id", "level"],
        "additionalProperties": false,
        "properties": {
          "id": {
            "type": "string",
            "minLength": 1
          },
          "level": {
            "type": "string",
            "enum": ["error", "warning", "off"],
            "default": "error"
          }
        }
      },
      "default": []
    },
    "layout": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "output_dir_names": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "c": {
              "type": "string",
              "minLength": 1,
              "default": "STNP_C"
            },
            "python": {
              "type": "string",
              "minLength": 1,
              "default": "STNP_Python"
            }
          },
          "default": {
            "c": "STNP_C",
            "python": "STNP_Python"
          }
        }
      },
      "default": {
        "output_dir_names": {
          "c": "STNP_C",
          "python": "STNP_Python"
        }
      }
    },
    "sdks": {
      "type": "array",
      "description": "C SDK 选择列表；items.enum 由加载期从内部注册表注入。",
      "items": {
        "type": "string",
        "enum": ["stm32_hal_uart"],
        "x-enumLabels": {
          "stm32_hal_uart": "STM32 HAL UART"
        }
      },
      "uniqueItems": true,
      "default": []
    },
    "python_sdks": {
      "type": "array",
      "description": "Python SDK 选择列表；items.enum 由加载期从内部注册表注入。",
      "items": {
        "type": "string",
        "enum": ["uart"],
        "x-enumLabels": {
          "uart": "UART (pyserial)"
        }
      },
      "uniqueItems": true,
      "default": []
    }
  }
}
```

> 可选强化（阶段二决定，不影响本骨架可用性）：用 `allOf` + `if/then` 表达「`target == "c"` 时要求 `c` 出现、`target == "python"` 时要求 `python` 出现」。当前骨架依赖对象级 `default`，不强制子对象存在。

### 5.3 段位说明

| 段 | 必填 | 关键约束 | 说明 |
|---|---|---|---|
| `format` | 是 | `const "stnp-build"` | 与 `.stnp` 的 `format` 区分 |
| `build_schema_version` | 是 | `enum ["stnp-build-schema-alpha"]` | build 文件格式版本，独立维护（见六） |
| `target` | 是 | `enum ["c","python"]` | 单选；非法值加载期拒绝（D18 / D19） |
| `c` | 否 | `additionalProperties false` | `build_system` / `emit_examples`；SDK 选择在顶层 `sdks` |
| `python` | 否 | `additionalProperties false` | `build_system` / `emit_examples` / `emit_user_scaffold`；SDK 选择在顶层 `python_sdks` |
| `output_stem` | 否 | `minLength 1` | 生成期仍走 `validate_output_stem()` |
| `emit_readme` | 否 | 默认 `true` | — |
| `validations` | 否 | items required `id` / `level` | 默认全列全启用；`level` 枚举为方案建议，最终值阶段二定 |
| `layout` | 否 | `output_dir_names.c` / `.python` | 承接 `config.json.output_dir_names` |
| `sdks` | 否 | `uniqueItems`；enum 注入 | C SDK 选择列表（非注册表） |
| `python_sdks` | 否 | `uniqueItems`；enum 注入 | Python SDK 选择列表（非注册表） |

### 5.4 `build_schema_version` 取值

取 `"stnp-build-schema-alpha"`（补充裁定五）。它与 `.stnp` 的 `schema_version` 各自独立，各有支持列表；读到不在列表的值直接抛异常（见六）。

---

## 六、版本标识定性

两个版本标识都是**生成器可解析的文件格式版本**，与 `protocol.version`（用户定义、通信层标识）完全解耦。

| 维度 | `schema_version` | `build_schema_version` |
|---|---|---|
| 所属文件 | `.stnp` | `stnp.build.json` |
| 类型 | string | string |
| 当前取值 | `"stnp-schema-alpha"` | `"stnp-build-schema-alpha"` |
| 是否必填 | 必填 | 必填 |
| 支持列表 | 生成器独立维护 | 生成器独立维护 |
| 列表外取值 | **直接抛异常** | **直接抛异常** |
| 与 `protocol.version` 关系 | 完全解耦 | 完全解耦 |
| 是否进入 IR | **否** | **否** |
| 旧格式适配 | **不做任何适配** | **不做任何适配** |

规则：

1. 两个版本标识**各自独立维护支持列表**，互不推导、互不约束。
2. 读到不在支持列表中的值，**直接抛异常**，不做降级、不猜测。
3. 与 `protocol.version` 完全解耦：后者是用户自定义的通信层标识，不参与文件格式解析。
4. 两者**不进入 IR**（IR 只承载工程语义，不承载文件格式版本）。
5. **不做任何旧格式适配**（D4）：不识别 `.stnp` 内的 `generation`、不识别 integer `schema_version`、不识别 `targets` 复数。
6. 本次改动同步修订 `docs/STNP_SPEC_0.9.md` §10 待定项 1 与附录示例：`schema_version` 由示例值 `3` 改为 `"stnp-schema-alpha"`，附录示例删除 `generation` 段。

---

## 七、schema 现有字段的增删清单

### 7.1 `stnp.schema.json`

| 项 | 动作 | 判定依据 |
|---|---|---|
| `generation` 及其全部子属性（`target` / `targets` / `c` / `python` / `output_stem` / `emit_readme` / `build_system` / `sdks` / `emit_examples` / `anyOf`） | **删** | D8：生成配置整体迁出至 `stnp.build.json`；不再保留任何回退链 |
| `groups`（含 `groups[].name`） | **删** | 补充裁定 B1：GUI 专用字段，0.9 直接删除 |
| `modules[].handler_mode` | **删** | D2 / B1：生成器遗留字段，非协议概念。注：`stnp.schema.json` 的 `modules.items` 为泛 `object`，`handler_mode` 实际定义在 `module.schema.json`，删除动作落在 7.3 |
| `schema_version` | **改**：`{"type":"integer","const":2}` → `{"type":"string","enum":["stnp-schema-alpha"]}` | D4：保留必填，类型改 string，生成器维护支持列表 |
| `global_results` | **增**：新增属性，`minItems 1`，item required `["name","value"]`，并加入根 `required` | SPEC §8.1；五节要求。现状 schema 完全缺失该属性，属新增而非修改 |
| 根 `required` 的 `generation` | **删** | 同 `generation` 行 |
| `embedded_files` | **保留不动** | 不在本次裁定范围；列为待议 |
| `format` / `project_name` / `protocol` / `common_types` / `modules` / `instances` | **不变** | 补充裁定二「其余不变」 |

### 7.2 `protocol.schema.json`

| 项 | 动作 | 判定依据 |
|---|---|---|
| `features.notify_dispatcher` 及其 `.enabled` | **删** | D7：删 `protocol.features.notify_dispatcher` 与其 `.enabled` 子行 |
| `features.notify_dispatcher.enabled` 的运行时语义 | **迁移**：改为 `options.notify_dispatch_receive.enabled`（boolean，默认 `false`，允许运行时切换） | D7：语义为「本端是否启用 Notify 接收分发路径」，归入 `options`（本端行为）而非 `features`（Capability） |
| `options` 容器 | **增**（关联裁定） | D7：新增 `protocol.options` 组；`options` 不改 wire format、两端可不同、允许运行时切 |
| `features.seq` / `features.seq.enabled` | **增**（关联裁定） | D6 / SPEC §8.3：SEQ 门控对齐 `features.seq.enabled`，默认 `false` |
| `features.crc.runtime_toggle` | **删**（关联裁定） | SPEC §3.10：0.9 不包含该字段；CRC 存在性只由生成期 Capability 决定 |
| `name` / `version` / `byte_order` / `max_payload` / `router_instance_max` / `task` / `notify` | **不变** | 与 SPEC §8.3 一致 |

### 7.3 `module.schema.json`

| 项 | 动作 | 判定依据 |
|---|---|---|
| `enabled` | **保留** | D2：`enabled` 保留，并在 ModuleIR 中新增、在生成侧消费 |
| `handler_mode` | **删** | D2 / B1：`handler_mode` 全部删除（0.9 文档、schema、GUI 三处一并清除） |
| `notifications[].kind` 及其 required 项 | **删**（关联裁定） | D15：`NotificationIR.kind` 删除，`NOTIFY_KIND_VALUES` / `STNP_NOTIFY_KIND_*` 一并删除；通知不再分类，接受/拒绝语义由 `RESULT` 槽承载 |
| `name` / `auto_notify_enabled` / `return_codes` / `commands` / `notifications` 其余字段 | **不变** | 与 SPEC §8.5 一致；D15 明确 `notify_on_*` 保留、`validate_hook` 保留 |

### 7.4 `common_types.schema.json`

| 项 | 动作 | 判定依据 |
|---|---|---|
| 全部字段（`types` / `name` / `kind` / `type` / `values`） | **不变更** | 配置拆分不涉及 `common_types`；D 系列裁定未触及；现状与 SPEC §8.5 一致 |

### 7.5 关联裁定的额外 schema 影响（超出配置拆分范围，供阶段二一并处理）

以下条目不由配置拆分触发，但由同一份决策文档（D6 / D7 / D15）与 SPEC §3.10 触发，若不同步落地会导致 schema 与规范/IR 不一致：

- `protocol.schema.json`：删 `features.notify_dispatcher`、增 `options.notify_dispatch_receive.enabled`、增 `features.seq.enabled`、删 `features.crc.runtime_toggle`。
- `module.schema.json`：删 `notifications[].kind`（含 `required` 中的 `kind`）。
- `stnp.schema.json`：`schema_version` 改 string 枚举（已列于 7.1，同时服务两处目标）。

> 上述字段均为**用户裁定内**（D6 / D7 / D15 / SPEC §3.10）的既有或指定字段，未新增任何裁定之外字段（尤其无 `release_channel` 类字段）。

---

## 附：待议与阶段二落地顺序

| 项 | 状态 | 说明 |
|---|---|---|
| `embedded_files` 去留 | 待议 | 不在本次裁定范围，暂保留 |
| `validations[].level` 枚举取值 | 阶段二定 | 本稿给 `["error","warning","off"]` 作建议；默认全列全启用 |
| `c` / `python` 子对象的条件必填（`if/then`） | 阶段二定 | 本稿用对象级 `default`，不强制出现 |
| 内部注册表键更名（`c_sdk_registry` / `python_sdk_registry`） | 阶段二定 | 消除与 build 选择列表的同名歧义 |
| 阶段二落地顺序 | 建议 | 先建 `stnp.build.schema.json` → 改 4 个既有 schema → 调整 `settings.py` 符号 → 重定位 `loader._validate()` 注入 → 改 CLI 参数 |
