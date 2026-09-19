# STNP 0.9.1 运行时诊断方案（实现规格）

本目录是 **0.9.1 实现规格**（追溯用）。0.9.1 已落地：现行行为以 `docs/` 与 [spec_0.9.1.md](../../05_architecture/spec_0.9.1.md) delta 为准；本目录不再作为开发接口。

基线：STNP Editor **0.9.0**（仓库当前树）。目标发行版本 **0.9.1**。  
执行对象：当前模板与生成器，不是一份抽象协议。

## 冻结范围

- 不改 Task / Notify 10 槽 wire，不加 Capability，不把 UART 写进 Core。
- 不给 `.stnp` 的 `protocol.options` 增加键。`notify_dispatch_receive` 已有，保持。
- **禁止**实现日志子系统：无 `STNP_LOGx` / `STNP_LOGE` / `STNP_LOG_LEVEL`，无诊断信封，无第三 SOF，无 `on_log` / `stnp.log`。
- Python 观察面只叫 `stnp.trace`（`debug` + `format`），禁止叫日志。
- C `STNP_DEBUG` 只是预编译 0/1，宏只打在规格列出的链路站点。

## 文档

| # | 主题 | 文档 | 切片 |
|---|---|---|---|
| 1 | Notify 接收：并行 → module XOR global | [01_notify独占分发.md](01_notify独占分发.md) | A |
| 2 | 未知 / 不可路由帧：两道闸回调，默认关 | [02_未知帧回调.md](02_未知帧回调.md) | B |
| 3 | Python `stnp.trace`：`debug` + `format` | [03_python_trace.md](03_python_trace.md) | C 的 debug / D 的 format |
| 4 | C 断点宏：只验证链路 | [04_c断点宏.md](04_c断点宏.md) | C |
| 5 | 文件、顺序、禁止项、编码陷阱 | [05_改造清单.md](05_改造清单.md) | 全切片 |

实现顺序（硬顺序，禁止调换）：**A → C → B+D → E**。理由见 05。

## 统一原则（硬规则）

| 机制 | 开关 | 默认 | 作用 |
|---|---|---|---|
| Notify 独占 | `notify_dispatch_receive`（整条接收分发总门；生成初值 + 运行时 API） | 随工程 | 本端是否投递 Notify |
| 未知帧回调 | SetCallback **并且** Enable | 两闸都关 | 非法 / 不可路由 |
| SOF 上报 | C `STNP_UNKNOWN_REPORT_SOF`；Python `unknown_report_sof` | 关 | 仅 SOF 噪声；不是主开关 |
| C 断点宏 | `STNP_DEBUG` 预编译 | 0 | 链路站点 |
| `trace.debug` | yaml / 运行时 flag | 关 | Python 链路站点名 |
| `trace.format` | yaml 总开关或名单；装饰器只改字 | 关 | Task/Notify 字段 |

```text
业务帧：decode -> validate -> format.maybe（只读）-> func
未知帧：解析失败 / 不可路由 -> unknown 回调(reason)（两闸都开才进）
链路验证：C STNP_BP_*  /  Python trace.debug.bp(site)
```

- 默认关。关着必须是真零调用（禁止 weak 空函数每帧都进）。
- 旁路观察：format / debug / 断点宏 **禁止**改变路由。
- 消息透传：合法业务帧仍按原路径到达。
- 用户 unknown 回调异常必须隔离，且 **禁止**计入 `callback_errors`。
- `STNP_Transport_Receive` / `transport.read`：**只拷贝字节**。禁止在其中解析、回调、构帧发送。

## 非目标

- 不改冻结规范两家族 wire、Capability、Result 区间。
- 不做 auto-notify 再封装、ID 自动分配、环境路径硬编码。
- 不新增 UART 驱动。
- 不把断点宏扩展成 LOG。
- 不把 C 全局 `STNP_Notify_Callback` 改成可空函数指针（那是 0.9.2）。
