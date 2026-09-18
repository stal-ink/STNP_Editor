# 3. JSON 与生成配置

本页给工程配置者：`.stnp` 与 `stnp.build.json` 的字段以 schema 为准。两份文件各自独立校验，互不引用；根对象均 `additionalProperties: false`。

`.stnp` 的 `schema_version` 与 `stnp.build.json` 的 `build_schema_version` 是两套版本标识，当前分别为 `"stnp-schema-alpha"` 与 `"stnp-build-schema-alpha"`。读到支持列表之外的取值即失败。

旧字段被拒绝的示例（0.8.2 把 `generation` 写在 `.stnp` 内）：

```json
{
  "format": "stnp",
  "schema_version": "stnp-schema-alpha",
  "generation": { "target": "c" }
}
```

加载期 schema 校验失败：`generation` 不是 `.stnp` 根对象允许属性。同样，`targets`、`handler_mode`、`groups`、`notifications[].kind` 都会被直接拒绝。

## 3.1 最小结构

`.stnp` 最小示例：

```json
{
  "format": "stnp",
  "schema_version": "stnp-schema-alpha",
  "project_name": "demo",
  "protocol": {
    "name": "STNP",
    "version": "2.3",
    "byte_order": "little",
    "max_payload": 64,
    "task": {
      "sof": [170, 85],
      "seq": {"type": "u16", "start": 1, "reserved": [0]}
    },
    "notify": {"sof": [170, 51]},
    "features": {"seq": {"enabled": false}, "crc": {"enabled": false}},
    "options": {"notify_dispatch_receive": {"enabled": false}}
  },
  "global_results": [{"name": "OK", "value": 0}],
  "modules": [
    {
      "name": "DEMO",
      "return_codes": [{"name": "OK", "value": 256}],
      "commands": [],
      "notifications": []
    }
  ],
  "instances": [
    {"name": "DemoMain", "module": "DEMO", "id": 1}
  ]
}
```

配套 `stnp.build.json` 最小示例：

```json
{
  "format": "stnp-build",
  "build_schema_version": "stnp-build-schema-alpha",
  "target": "c"
}
```

## 3.2 根对象

| 字段 | 类型 | 必填 | 约束 / 默认 | 说明 |
|---|---|---:|---|---|
| `format` | string | 是 | 固定 `"stnp"` | 文件格式标识 |
| `schema_version` | string | 是 | 固定 `"stnp-schema-alpha"` | 文件格式版本标识，与 `protocol.version` 完全解耦 |
| `project_name` | string | 是 | 非空 | 工程名 |
| `protocol` | object | 是 | 见下文 | 协议参数 |
| `common_types` | object | 否 | 空类型池 | 公共 Payload 类型 |
| `modules` | array | 是 | 至少 1 项 | Module 定义 |
| `instances` | array | 是 | 至少 1 项 | Runtime 实例 |
| `global_results` | array | 是 | 至少 1 项 | 工程级 Result 码表 |
| `embedded_files` | object | 否 | — | 随生成结果输出的附加文件 |

根对象不允许未知字段。

## 3.3 `protocol`

| 字段 | 类型 | 必填 | 约束 / 默认 | 说明 |
|---|---|---:|---|---|
| `name` | string | 是 | — | 协议名称 |
| `version` | string | 是 | — | 业务协议版本字符串 |
| `byte_order` | string | 是 | 固定 `little` | wire 字节序 |
| `max_payload` | integer | 是 | `1..255` | 最大 Payload bytes |
| `router_instance_max` | integer | 否 | `8`，范围 `1..255` | Router 最大实例数 |
| `task` | object | 是 | — | Task 参数 |
| `notify` | object | 是 | — | Notify 参数 |
| `features` | object | 否 | — | 协议 Capability 开关 |
| `options` | object | 否 | — | 本端运行时行为开关 |

`features` 承载协议 Capability：Capability 改变 wire format、两端必须一致、禁止运行时切换。`options` 承载本端行为：不改 wire format、两端可不同、允许运行时切换。两组字段不得混放。

### `protocol.task`

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---:|---|---|
| `sof` | integer[2] | 是 | 每项 `0..255` | Task SOF |
| `seq` | object | 是 | — | Task 序列号策略 |

### `protocol.task.seq`

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---:|---|---|
| `type` | string | 是 | 固定 `u16` | SEQ 类型 |
| `start` | integer | 是 | `1..65535` | 初始 SEQ |
| `reserved` | integer[] | 否 | 每项 `0..65535`、唯一 | 自动跳过值 |

语义约束：

- `start` 不能出现在 `reserved`；
- Task SOF 与 Notify SOF 必须不同。

### `protocol.notify`

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---:|---|---|
| `sof` | integer[2] | 是 | 每项 `0..255` | Notify SOF |

### `protocol.features`

```json
{
  "features": {
    "seq": {"enabled": false},
    "crc": {"enabled": false}
  }
}
```

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `seq.enabled` | boolean | `false` | SEQ Capability 门控；Task 与 Notify 共用同一门控，关闭时 SEQ 槽完全不存在 |
| `crc.enabled` | boolean | `false` | CRC Capability 门控；决定 CRC 尾槽是否存在 |

`seq` 与 `crc` 是两项独立 Capability，可分别开启或关闭。Capability 集合固定在配置，不属于运行时状态。

### `protocol.options`

```json
{
  "options": {
    "notify_dispatch_receive": {"enabled": false}
  }
}
```

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `notify_dispatch_receive.enabled` | boolean | `false` | 本端是否启用 Notify 接收分发路径；允许运行时切换 |

运行时提供启用、禁用、查询三支接口切换该本端行为，初值来自本配置。

## 3.4 `common_types`

```json
{
  "common_types": {
    "types": [
      {"name": "Speed", "kind": "alias", "type": "u8"},
      {
        "name": "Mode",
        "kind": "enum",
        "type": "u8",
        "values": [
          {"name": "IDLE", "value": 0},
          {"name": "RUN", "value": 1}
        ]
      }
    ]
  }
}
```

### `common_types.types[]`

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---:|---|---|
| `name` | string | 是 | `^[A-Z][A-Za-z0-9]*$` | 生成 `STNP_<Name>` |
| `kind` | string | 是 | `alias` / `enum` | 类型类别 |
| `type` | string | 是 | `u8/u16/u32/i32` | 固定 wire 基础类型 |
| `values` | array | enum 时必须有有效项 | 见下文 | enum 值 |

`enum.values[]`：

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `name` | string | 是 | `^[A-Z][A-Z0-9_]*$`，同 enum 内唯一 |
| `value` | integer | 是 | 同 enum 内唯一，且必须落在基础类型范围 |

语义约束：公共类型和 enum 宏不能与 STNP Runtime 或其他生成 C 符号冲突。

## 3.5 `modules[]`

| 字段 | 类型 | 必填 | 约束 / 默认 | 说明 |
|---|---|---:|---|---|
| `name` | string | 是 | `^[A-Z][A-Z0-9_]*$`、全局唯一 | Module 名 |
| `enabled` | boolean | 否 | `true` | `false` 时生成阶段忽略 |
| `auto_notify_enabled` | boolean | 否 | `false` | 关闭时 `notify_on_*` 只作元数据 |
| `return_codes` | array | 是 | 至少 1 项 | Module Result |
| `commands` | array | 否 | `[]` | Task Commands |
| `notifications` | array | 否 | `[]` | Notify 定义 |

至少需要一个 enabled Module。

### `return_codes[]`

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `name` | string | 是 | `^[A-Z][A-Z0-9_]*$`，Module 内唯一 |
| `value` | integer | 是 | `0..65535`，Module 内唯一 |
| `brief` | string | 否 | 文档说明 |

Return Code 按值区间分段：

- `0x0000` 为工程级 `OK`，由根对象的 `global_results` 声明；
- `0x0001..0x00FF` 为 Global Result；
- `0x0100 + 256 * i` 起，按 `modules[]` 顺序为每个 Module 分配 256 个连续值（`i` 为 Module 序号，从 0 起）。

**必须存在名为 `OK` 的 Return Code，且其值落在本 Module 的区间内。** Module 数不得超过 255，每个 Module 的 Return Code 不得超过 256 条。

Module 级可选字段 `auto_notify_enabled: boolean`，默认 `false`。关闭时 `notify_on_*` 仅保留为触发时机元数据，不触发自动发送。

### `commands[]`

| 字段 | 类型 | 必填 | 约束 / 默认 | 说明 |
|---|---|---:|---|---|
| `name` | string | 是 | `^[A-Z][A-Z0-9_]*$`，Module 内唯一 | Command 名 |
| `code` | integer | 是 | `0..255`，Module 内唯一 | Command code |
| `payload` | array | 是 | 可为空 | Payload fields |
| `doc` | object | 否 | — | 文档元数据 |
| `validate_hook` | boolean | 否 | `false` | 是否进入校验函数 |
| `notify_on_done` | object | 否 | 必须引用存在的 Notify | 完成时触发时机的自动通知引用 |
| `notify_on_accept` | object | 否 | 必须引用存在的 Notify | 受理时触发时机的自动通知引用 |
| `notify_on_reject` | object | 否 | 必须引用存在的 Notify | 拒绝时触发时机的自动通知引用 |

`notify_on_*` 是触发时机字段：引用校验只要求引用的通知存在，不按分类匹配。开启 `auto_notify_enabled` 时，生成层按以下顺序处理：校验函数非 OK → `notify_on_reject`；校验函数通过 → `notify_on_accept` → Command handler → `notify_on_done`。

自动通知只允许引用 **零 Payload** Notify；带 Payload Notify 必须由用户业务代码显式发送。该能力只存在于生成的 Module/Decorator 层，不在 STNP Core 内建立 Task→ACK→DONE 状态机。

### `commands[].doc`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `brief` | string | 否 | 简短说明 |
| `detail` | string | 否 | 详细说明 |

## 3.6 `notifications[]`

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---:|---|---|
| `name` | string | 是 | `^[A-Z][A-Z0-9_]*$`，Module 内唯一 | Notify 名 |
| `code` | integer | 是 | `0..255`，Module 内唯一 | Notify code |
| `brief` | string | 否 | — | 说明 |
| `payload` | array | 是 | 可为空 | Payload fields |

Command code 与 Notify code 属于不同表，可使用相同数值。通知不再分类；接受与拒绝语义由 Notify 帧的 `RESULT` 槽承载。

## 3.7 Payload Field

Command 和 Notification 的 `payload[]` 使用相同字段格式：

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---:|---|---|
| `name` | string | 是 | `^[a-z][a-z0-9_]*$`、同 Payload 内唯一、不能是 C keyword | 字段名 |
| `type` | string | 是 | 基础类型或已定义 common type | wire 类型 |
| `min` | integer | 否 | 必须落在基础类型范围 | 业务元数据 |
| `max` | integer | 否 | 必须落在基础类型范围，且 `min <= max` | 业务元数据 |

Payload 所有字段 wire size 之和不得超过 `protocol.max_payload`；累计完成后即校验，超限工程直接失败。

`min/max` 当前是**元数据**，Core VTL 不自动执行范围校验。生成器按模块生成一个校验函数，`validate_hook: true` 的 Command 进入校验函数，按其字段类型与 `min`/`max` 自动产出校验代码。

## 3.8 `instances[]`

```json
{
  "name": "SensorFront",
  "module": "SENSOR",
  "id": 3
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `name` | string | 是 | `^[A-Za-z][A-Za-z0-9_]*$`、全局唯一 |
| `module` | string | 是 | 必须引用 enabled Module |
| `id` | integer | 是 | `1..255`、全局唯一 |

实例总数不得超过 `protocol.router_instance_max`。

生成 ID：

```c
STNP_INSTANCE_SENSORFRONT_ID
```

用户统一使用实例 ID 宏寻址；不存在单实例便捷宏。

## 3.9 `global_results[]`

工程级 Result 码表，至少 1 项：

```json
{
  "global_results": [
    {"name": "OK", "value": 0, "brief": "工程级成功"}
  ]
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `name` | string | 是 | `^[A-Z][A-Z0-9_]*$` |
| `value` | integer | 是 | `0..65535` |
| `brief` | string | 否 | 说明 |

必须存在名为 `OK` 且值为 `0x0000` 的条目；其余条目值落在 `0x0001..0x00FF`，条目数不超过 255。工程级 `OK` 与各 Module 的 `OK` 并存，语义不同：前者表示整条链路成功，后者表示该 Module 处理成功。

## 3.10 `stnp.build.json` 生成配置

生成配置不再内嵌于 `.stnp`，而是由独立的 `stnp.build.json` 承载，由 `stnp.build.schema.json` 校验。最终工程文件夹名为 `{output_stem}_{layout.output_dir_names[target]}`。

```json
{
  "format": "stnp-build",
  "build_schema_version": "stnp-build-schema-alpha",
  "target": "python",
  "python": {
    "build_system": "python",
    "emit_examples": false,
    "emit_user_scaffold": false
  },
  "output_stem": "demo",
  "emit_readme": true,
  "layout": {"output_dir_names": {"c": "STNP_C", "python": "STNP_Python"}},
  "python_sdks": ["uart"]
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---:|---|---|
| `format` | string | 是 | — | 固定 `"stnp-build"` |
| `build_schema_version` | string | 是 | — | 固定 `"stnp-build-schema-alpha"` |
| `target` | string | 是 | — | 单选 `c` / `python`；生成与检查只按此单一目标分派 |
| `c.build_system` | string | 否 | `mdk_arm` | `mdk_arm` / `cmake` |
| `c.emit_examples` | boolean | 否 | `false` | C PC Mock Example |
| `python.build_system` | string | 否 | `python` | 固定值，不提供其他构建系统 |
| `python.emit_examples` | boolean | 否 | `false` | 生成 `Example/mock_serial.py + main.py` |
| `python.emit_user_scaffold` | boolean | 否 | `false` | 首次创建 `User/<module>_logic.py`，后续永不覆盖/删除 |
| `output_stem` | string | 否 | 工程文件名主干 | 输出目录前缀 |
| `emit_readme` | boolean | 否 | `true` | 生成目标 README |
| `validations` | array | 否 | 全列全启用 | 校验清单；条目含 `id` 与 `level`（`error` / `warning` / `note`） |
| `layout.output_dir_names.c` | string | 否 | `STNP_C` | C 目标输出目录后缀 |
| `layout.output_dir_names.python` | string | 否 | `STNP_Python` | Python 目标输出目录后缀 |
| `sdks` | string[] | 否 | `[]` | C SDK 选择列表；条目枚举由加载期从内部注册表注入 |
| `python_sdks` | string[] | 否 | `[]` | Python SDK 选择列表；条目枚举由加载期从内部注册表注入 |

`build_schema_version` 与 `.stnp` 的 `schema_version` 各自独立维护支持列表，读到列表外取值即失败。`output_stem` 必须是单一安全路径组件：禁止包含 `/`、`\`、`:`、NUL，也禁止取值为 `.` 或 `..`。

Python 的 UART、Runtime 与协议配置不混在一个 YAML：

```text
stnp/protocol/protocol.yaml   # Editor/IR 生成
config/stnp.yaml              # 用户 Runtime 配置
stnp/sdk/uart/uart.yaml       # 用户 UART SDK 配置
```

## 3.11 `embedded_files`

```json
{
  "embedded_files": {
    "docs/note.md": {
      "content": "hello\n",
      "encoding": "text"
    }
  }
}
```

每个值：

| 字段 | 类型 | 必填 | 约束 |
|---|---|---:|---|
| `content` | string | 是 | text 内容或 Base64 文本 |
| `encoding` | string | 是 | `text` / `base64` |

文件统一生成到：

```text
Embedded/<key path>
```

路径必须是安全相对 POSIX 路径；禁止绝对路径、`..`、`.`、空 path component、反斜杠和 drive/colon 写法。Base64 使用严格校验，但允许正常空白换行。

## 3.12 生成 C 命名冲突

Schema 合法并不代表任意名字都能成为安全 C 标识符。IR 构建阶段会统一检查 Runtime、Common Type、Module、Command、Notify、Payload、Return Code、Instance macro 等生成符号。

原则：

- 不要使用 STNP Runtime 已占用的名字；
- 不要依赖大小写/下划线差异制造“看起来不同”的名称；
- 如果多个配置名经过 C normalization 后产生相同符号，会拒绝生成。

---

[← 协议格式](02_protocol.md) | [文档目录](README.md) | [API →](04_api/README.md)
