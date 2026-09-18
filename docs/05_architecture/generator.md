# 生成器架构

本页解释生成器为什么这样切分，以及失败时如何报错。实现取证于 `src/stnp_editor/ir/builder.py`、`generation.py`、`loader.py`、`errors.py`、`diagnostics.py`、`emit/c/merge.py`、`emit/manifest.py`、`emit/c/emitter.py`。

## 数据流

```text
load_project(.stnp) + load_build_data(stnp.build.json)
  → schema 校验（加载期注入 SDK 枚举）
  → IR builder 语义校验
  → ProjectIR
  → emit_c / emit_python（由 target 单选）
  → 写出 + USER CODE merge + manifest 清理
```

两份输入各自独立校验、互不引用。`.stnp` 只描述协议；`stnp.build.json` 只描述生成配置。`generate` 与 `check` 都走同一条 IR → emit 路径；`check` 在临时目录生成后与 `--golden` 树做逐文件比较。

## Schema 与 IR 语义校验分工

Schema 负责类型、required、枚举、基础范围和对象结构，`additionalProperties: false`。读到旧字段（如顶层 `generation`、复数 `targets`、`notifications[].kind`）即失败。

IR builder 继续检查（错误码 E2/E3 段），例如：

- Module / Instance / Command / Notify 名称与码值唯一性；Instance ID 全局唯一且落在 `1..255`。
- Payload 总 wire size 不超过 `protocol.max_payload`。
- common type 范围落在基础类型可表示区间。
- 每个启用 Module 的 Return Code 必须含本段 `OK`；工程级 `global_results` 必须含值为 `0x0000` 的 `OK`。
- `notify_on_*` 引用存在，且自动通知必须零 Payload。
- Task / Notify SOF 两个字节必须不同。
- SEQ `start` 不在 `reserved`；Instance 数量不超过 `router_instance_max`。
- Embedded 路径与 Base64；`output_stem` 安全。
- C 符号命名空间不冲突；Python Module snake 名不得遮蔽 `stnp.core` / `stnp.sdk` / `stnp.protocol` 保留名。

Schema 过了、IR 未过时，不会写出半套工程。

## 单目标分派与 build 文件

`stnp.build.json` 顶层 `target` 只能是 `c` 或 `python`。生成与 `check` 只按该目标分派，不再接受复数 `targets`。未知 `target` 在加载期失败。

C SDK / Python SDK 列表在加载期按内部注册表注入 schema 枚举：`loader._inject_build_enums()` 调用 `settings.available_sdks_for(target)`，来源是 `src/stnp_editor/resources/config.json` 的 `sdk_registry`（C：`stm32_hal_uart`、`freertos`）与 `python_sdk_registry`（`uart`）。静态 `stnp.build.schema.json` 里的 SDK 列表不是完整真相；`freertos` 能通过是因为内部注册表。未知 SDK 在生成期拒绝（E4003）。

## C Symbol Registry 与命名冲突拒绝

最终 C 名字不是 JSON 名的简单拷贝。Runtime、Common Type、Module、Payload、Instance 等进入同一符号登记表；公共 typedef（如 `U8`/`Result`/`ModuleHandle`）由生成运行时占用，common type 不得再叫这些名字。冲突在生成前以校验错误拒绝，不产出半套工程。

`.c` 基名另有一层 Keil-safe 检查，见下文。

## 输出安全

写出路径必须落在所选输出父目录内（containment）；拒绝 symlink 把生成路径或 manifest 清理路径导向输出根之外。`output_stem` 必须是单一安全路径组件：禁止包含 `/`、`\`、`:`、NUL，也禁止取值为 `.` 或 `..`。E4 段包含输出逃逸（E4005）、stem 不安全（E4006）、写出失败（E4010）、清单失败（E4011）、Embedded 解码失败（E4012）、Keil basename 冲突（E4007）。

最终工程文件夹名为 `{output_stem}_{layout.output_dir_names[target]}`，默认后缀 `STNP_C` / `STNP_Python`。

## USER CODE merge 与 manifest 清理

C 的 `Implementation/*_impl.c` 与 `stnp_notify_callback.c` 含用户代码区。`emit/c/merge.py` 用正则匹配：

```text
/* USER CODE BEGIN <id> */ … /* USER CODE END <id> */
/* USER DESC BEGIN <id> */ … /* USER DESC END <id> */
```

重新生成时，新模板里仍存在的 id 保留旧块全文；旧文件里有、新模板没有的块追加到文件末尾的 `USER ORPHAN BEGIN/END`，避免静默丢代码。Embedded 文件不在合并范围，Base64 严格解码。

`.stnp-manifest.json`（`MANIFEST_VERSION = 1`）记录生成器拥有的相对路径与 `kind`。`cleanup_stale()` 对不再出现的 generated 文件删除；`kind == "implementation"` 的用户实现不直接删除，而是移到 orphan 目录，避免误删手写实现。清单损坏上报 E4011 warning 并忽略，不阻断本次生成。

## Keil-safe 命名

MDK-ARM 按 `.c` 基名生成 obj，通常放在同一对象目录。`emit/c/emitter.py` 的 `_validate_unique_c_basenames` 对全部输出 `.c` 做大小写不敏感的基名唯一检查，冲突报 E4007。因此 Module 框架源为 `Module/<Module>/<module>.c`，用户实现为 `Implementation/<module>_impl.c`，保证 basename 唯一。

## 诊断与退出码

`errors.py` 分段（本轮登记约 70 码：E1 14、E2 35、E3 7、E4 12、E9 2）：

| 段 | 范围 | 阶段 |
|---|---|---|
| E1 | E1001–E1099 | 加载格式（E1001–E1050 输入解析，E1051–E1099 配置与环境） |
| E2 | E2101–E2199 | 校验 |
| E3 | E3001–E3099 | 构建（含 Return Code 分段） |
| E4 | E4001–E4099 | 生成写出 |
| E9 | E9001 / E9002 | 内部 |

已分配错误码只增不改；删除报错点时码位保留。本轮 `E1006` 登记但 `enabled=False`，不参与诊断与默认校验清单。全部登记码默认级别为 `error`；`stnp.build.json` 的 `validations` 可按 `id` 改为 `warning` / `note`。

`diagnostics.py` 输出编译器风格诊断：`文件:行:列: error[错误码]: 消息`，默认打印出错行并以 `^` 指向列；有可执行修复建议时附单行 `help:`。多条诊断空行分隔，按文件、行、列、错误码排序。诊断走 stderr；生成路径与 `-list` 走 stdout。无文件时前缀为 `<internal>`。消息为中文短句，不带句末句号。

退出码：`0` 成功，`1` E1–E4 error，`2` 用法错误，`3` E9 内部缺陷。多段同时出错时 E9 优先于失败。

CLI `check` 在临时目录生成后与 `--golden` 树做逐文件比较，不一致返回 1 并打印 `CHECK FAILED`。`-list` 只作用于 `generate`：逐文件打印 `[N/M] path`。

---

[← 架构说明](README.md) | [文档目录](../README.md) | [C 运行时 →](c_runtime.md)
