# 4. API

本页给需要调用生成代码的集成者：按语言进入 C 或 Python 参考。两种语言共用同一份 IR，执行模型不同。

## 语言索引

| 语言 | 入口 | 执行模型要点 |
|---|---|---|
| C | [C API](c/README.md) | Handle + 用户代码区（USER CODE）+ `Process`/`Dispatch` 延迟分发 |
| Python | [Python API](python/README.md) | descriptor + dataclass + 装饰器 + RX/Dispatch 双线程 |

## 两语言模型差异

C 生成物以 `Core/stnp.h` 为公共入口，业务实现放在 `Implementation/*.c` 的用户代码区。接收路径是传输层（Transport）写入 RX Ring，再由 `STNP_Process()` 推进至多一帧、`STNP_Dispatch()` 执行至多一个 Job。发送走 `STNP_Task_Send()` / `STNP_Notify_Send()`，内部经 Router → VTL → Frame。

Python 生成物是 `stnp` 包：`stnp.core` / `stnp.sdk` / `stnp.protocol`。命令与通知用装饰器挂到 Module 或 Instance；发送可用 `stnp.task(...)` 或 `stnp.task.<Instance>.<CMD>(...)`。运行时默认在调用线程发送，另起 RX 线程与 Dispatch 线程。C 的 `STNP_Process` / `STNP_Dispatch` 每次最多一帧 / 一 Job；Python `StreamParser.feed()` 一次可解析多帧，但 Dispatch 仍按队列逐项执行。两端 wire 由同一份 `.stnp` 生成，执行模型不必相同。

签名以本目录各页为准。架构页解释为什么这样分层；指南页给可复制的集成步骤。不要从 `archive/` 抄现行 API。

## 与架构、指南的分工

- 符号与签名以本目录为准，取证于生成模板与期望产物（golden）。
- 分层原因与数据流见 [5. 架构说明](../05_architecture/README.md)。
- 操作步骤（UART、FreeRTOS、USER CODE、构建系统）见 [6. 使用指南](../06_guides/README.md)。
- 字段与 schema 见 [3. JSON 与生成配置](../03_json_format.md)。

---

[← JSON 与生成配置](../03_json_format.md) | [文档目录](../README.md) | [C API →](c/README.md)
