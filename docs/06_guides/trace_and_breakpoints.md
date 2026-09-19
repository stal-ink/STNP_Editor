# 链路验证：`STNP_DEBUG` 与 `stnp.trace`

本页从 0.9.1 实现规格摘录，给联调者：确认架构站点有没有走到、以及 Python 侧如何把 Task/Notify 字段打成可读行。这 **不是** 日志系统：无等级、无诊断信封、不走 `Transport_Write` 发第三 SOF。

签名见 [C API / platform.md](../04_api/c/platform.md)、[C API / core.md](../04_api/c/core.md)、[Python API](../04_api/python/README.md)。Notify 独占见 [C 运行时](../05_architecture/c_runtime.md) 与 [Python 运行时](../05_architecture/python_runtime.md)。

## 默认全关

| 机制 | 开关 | 默认 |
|---|---|---|
| C 断点宏 | 编译期 `-DSTNP_DEBUG=1` | `STNP_DEBUG` 为 0，宏展开为空 |
| Python `trace.debug` | yaml / `stnp.trace.configure` / 属性 | `enabled=False`；`trap is None` 时即使 enabled 也是空操作 |
| Python `trace.format` | yaml 总开关或名单 | `enabled=False` 且名单空则全不打 |

关着必须是真零调用。format / debug / 断点宏 **禁止**改变路由。

## C：`STNP_DEBUG`

```c
#ifndef STNP_DEBUG
#define STNP_DEBUG 0
#endif
```

仓库 golden 按 0 生成。联调时在编译选项加 `-DSTNP_DEBUG=1`。`stnp_platform_config.h` 禁止写成 1。测试用强符号覆盖 weak `STNP_Debug_Trap` 做计数；未定义 `STNP_DEBUG_TRAP_BKPT` 时禁止 BKPT。

合法 Task 典型站点：

```text
RX_COPY, PROCESS_ENTER, PARSE_OK, ENQUEUE, DISPATCH, ON_TASK
```

CRC 错：含 `PROCESS_ENTER`、`PARSE_RESYNC`；无 `PARSE_OK`、`ON_TASK`。SOF 猎寻热循环 **禁止**打 `PARSE_RESYNC`。独占 Notify 一帧 `ON_NOTIFY` 恰好 1 次。

IRQ 里仍然只允许 `STNP_Transport_Receive()` 拷贝字节；该函数里唯一允许的 trap 是 `STNP_BP_RX_COPY`（发布 `g_rx_tail` 之后），必须极短。

需要在无调试器的 MCU 上确认「代码执行到了某一层」时，仍可用临时 `STNP_Notify_Send()`，见 [用 Notify 打点](debugging_with_notify.md)。那是业务帧，不是本页的断点宏。

## Python：`stnp.trace.debug`

```python
stnp.trace.debug.enabled = True
stnp.trace.debug.trap = print   # 或 list.append；默认 None
```

`stnp.init()` 会 `trace.load()`，也可在 `config/trace.yaml` 写 `trace.debug.enabled`。站点名与 C 宏同意图：`rx_read`、`parse_ok`、`parse_resync`、`enqueue`、`dispatch`、`on_task`、`on_notify`、`seq_reserve`、`transport_write`。

合法 MOVE 一帧：

```text
rx_read, parse_ok, enqueue, dispatch, on_task
```

LEN/CRC 失步打 `parse_resync`（每个 `ParseError("len"|"crc")` 一次）。SOF 噪声不打该站点。`on_notify` 只打独占后实际走的那条。

## Python：`stnp.trace.format`

配置在 `config/trace.yaml`（**不要**塞进 `stnp.yaml`）：

```yaml
trace:
  debug:
    enabled: false
  format:
    enabled: false
    commands: []          # MODULE.COMMAND，如 CHASSIS.MOVE
    notifications: []     # MODULE.NOTIFY，如 SENSOR.DATA
```

| `format.enabled` | 列表 | 行为 |
|---|---|---|
| `true` | 忽略 | 走到 `maybe` 的 Task / Notify 都 format（含全局 fallback；无人认领除外） |
| `false` | 非空 | 只打列表内 path |
| `false` | 空 | 全不打 |

查找顺序（`stnp.init()` → `trace.load()`，先命中先用）：显式 `stnp.trace.load(path)` → 环境变量 `STNP_TRACE_CONFIG` → cwd `config/trace.yaml` → 生成包旁 `config/trace.yaml` → 内存默认全关。

`@stnp.trace.format("CHASSIS.MOVE")` **只登记**自定义字符串，不写入 yaml 名单。要看见这条，仍然需要总开关或名单含该 path。

默认行示例：

```text
STNP TASK ChassisMain CHASSIS.MOVE direction=1 speed=40
STNP NOTIFY SensorFront SENSOR.DATA result=OK value=1234 status=0
```

全局 fallback 的 payload 是 raw `bytes`，字段段为 hex。无 payload 字段则省略字段段。validate 失败：不 format、不 func。format/sink 抛错：隔离后业务 `func` 仍执行。

出口是可替换 `stnp.trace.format.sink`（默认 `print`），不是 logging 产品层。

## 与 Notify 打点的分工

```text
断点宏 / trace.debug  → 链路有没有走到（站点名）
trace.format          → 这条 MOVE / DATA 字段是什么（只读，不改路由）
STNP_Notify_Send 临时打点 → 无调试器时确认某层已执行且 TX 可用
```

禁止把 format 当成 Notify 认领者。禁止在文档或配置里把上述机制叫「日志」。

---

[← 用 Notify 打点](debugging_with_notify.md) | [文档目录](../README.md) | [CRC 与流式接收 →](crc_and_stream.md)
