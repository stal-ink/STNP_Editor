# Python 运行时架构

本页说明 Python 生成包的默认执行模型。取证于期望产物 `tests/golden/python/regression_py/regression_py_STNP_Python/stnp/core/runtime.py`、`dispatch.py`、`frame.py`、`model.py`、`stats.py` 与冻结规范 §8.3。

## 默认执行模型

```text
调用线程
  └─ stnp.task / stnp.notify
       └─ encode + SEQ
            └─ write lock
                 └─ 一次 Transport.write()

stnp-rx
  └─ Transport.read
       └─ StreamParser
            └─ 有界 dispatch 队列

stnp-dispatch
  └─ decode
       ├─ 校验函数 / 自动通知包装
       ├─ CMD implementation
       └─ Notify typed `.func` / `@stnp.on_notify`（独占，不并行）
```

没有 TX worker。发送发生在调用线程。`Runtime.init(transport, queue_size=1024, warn_missing=True)` 先 `transport.open()`，再启动 `Dispatcher` 线程（名 `stnp-dispatch`）与 RX 线程（名 `stnp-rx`，均为 daemon）。`shutdown()` 置停止事件、关闭 transport、join RX（超时 1 s）并停止 Dispatcher。

## 为什么 RX 与 Dispatch 分离

若 RX 线程直接跑用户回调，慢回调会堵住串口读取。分开后 RX 继续 `transport.read(4096)` 并喂 `StreamParser.feed()`；回调变慢只表现为 dispatch 队列堆积。`Dispatcher.put()` 使用 `put_nowait`：队列满则返回 `False`，RX 侧把该帧计入 `dropped_frames`，不阻塞读循环。默认 `max_queue=1024`。

`feed()` 一次可吐出多帧（`TaskFrame` / `NotifyFrame` / `ParseError`）。CRC 失败计入 parser 的 `crc_errors`，`LEN` 非法计入 `protocol_errors`；RX 循环把这两项累加进 `stnp.stats` 后清零 parser 计数器，避免重复累加。`ParseError` **禁止** `put` 进 Dispatcher，**禁止** `rx_frames++`。SOF 猎寻每次只滑 1 字节（与 C 对齐）；`unknown_report_sof` 默认关。

## TaskSet 一次 write

`stnp.task(spec1, spec2, ...)` 先对每个 `TaskSpec` 做 VTL 编码并 `build_task`，再 `b"".join` 后一次 `transport.write`。NotifySpec 批量同样合并。`_write_many` 持有 `_write_lock`；写出字节数不足则抛 `TransportError`。适合高频连续发送，避免每帧一次系统调用。

动态发送 `stnp.task(instance, command, ...)` 先解析 CommandDescriptor（对象 / 名字 / 码值），再构造单条 `TaskSpec` 走同一路径。命令必须属于该 Instance 所绑 Module，否则 `ProtocolError`。

## callback 锁边界

Dispatch 执行用户函数时不持有 TX `_write_lock`，因此回调内可以再次 `stnp.task` / `stnp.notify`（可重入发送）。SEQ 另有 `_seq_lock`：`_next_seq()` 在锁内读取当前值并推进（`0xFFFF` 回绕到 0，跳过 `seq_reserved`），与 C 的 reserve-before-write 对齐。不要在回调里做长时间阻塞读，那会堵住 Dispatch 线程。

尚未 `stnp.init()` 就发送会抛 `TransportError("stnp.init() has not configured a transport")`。

## CMD dispatch 与校验顺序

```text
按 TARGET 找 Instance
  → 按 CMD 找 CommandDescriptor
  → decode Payload dataclass
  → 若 validate_hook：
        Instance @validate → 否则 Module @validate
        → 否则 `module.validator`（生成的 `validate_<module>`，按命令码分派）
        → 非 OK 则停止（禁止 format、禁止 func；auto_notify 的 reject 由装饰器包装发出）
  → format.maybe（`stnp.trace.format`；validate 失败禁止走到这里）
  → CMD .func（Instance 覆盖优先于 Module；`fn is None` 则 warning 并 return）
```

`CallbackSlot.resolve(instance_id)` 先查实例级注册，没有再回落到模块级。有 Payload 的 handler 签名是 `(self, payload)`；无 Payload 只有 `(self)`。未实现的 CMD 记 warning 并跳过，不让 Dispatch 线程崩溃。

自动通知由 `CommandDescriptor._wrap_func` / `_wrap_validate` 包装层发送，Runtime dispatch 本身不直接发 ACCEPT/REJECT/DONE：

- 校验非 `Module.OK` 且 `auto_notify_enabled`：发 `notify_on_reject`（RESULT 为校验返回值）。
- `.func` 进入前发 `notify_on_accept`，返回后发 `notify_on_done`（RESULT 均为 `Module.OK`）。
- 引用的 Notify 必须存在；发送走 `runtime.send_notify`。自动通知只能引用零 Payload Notify。

`validate_hook` 为假时 `@...validate` 注册会抛 `RuntimeError`。

## Notify dispatch：独占（module XOR global）

`notify_dispatch_receive` 门控**整条** `_dispatch_notify`。DR 关 → 整条不投递（typed 与 `@stnp.on_notify` 都不跑）。DR 开才进入认领判定。

1. DR 关：立即 return（在 `trace.debug.bp("dispatch")` 之前）。
2. DR 开，按 SOURCE 找 Instance。Instance 已知：按 Notify code 找 descriptor；`_func.resolve` 非 None 才算认领 → decode → `format.maybe` → `debug.bp("on_notify")` → typed `.func` → **return**，禁止再调全局。
3. DR 开、未认领且已登记 `@stnp.on_notify`：`format.maybe`（`descriptor=None`，payload 为 `frame.payload` bytes）→ `debug.bp("on_notify")` → 全局，签名只有两种 raw 形：
   - 未知 Instance：`(source_id, code, result, raw bytes)`
   - 已知 Instance：`(instance, code, result, raw bytes)`（未知码，或已知码但 `fn is None`）
4. DR 开、连全局都没有：两闸都开时 `_report_unknown("notify", ...)`；禁止 format，禁止 `on_notify` 打点。

全局 **禁止**再收到 `NotificationDescriptor` 或解码 dataclass。Python 没有 C 的 `NotifyCallbackEnable`：有 typed `.func` 即认领。

开关 API：`stnp.notify_dispatch_receive_enable` / `disable` / `is_enabled`。初值来自 `.stnp` 的 `protocol.options.notify_dispatch_receive.enabled`。不改发送、不改 wire。

## `stnp.trace.debug` 站点

`from .trace import debug as trace_debug, format as trace_format`。`stnp.init()` 调用 `trace.load()`。默认关。站点：`rx_read`（非空 `read` 之后、`feed` 之前）、`parse_ok`（合法帧、`rx_frames++` 之前）、`parse_resync`（每个 `ParseError("len"|"crc")`）、`enqueue`（`Dispatcher.put` 成功）、`dispatch`（Task/Notify 入口第一句）、`on_task` / `on_notify`（即将调用实际 handler）、`seq_reserve`、`transport_write`。详见 [链路验证](../06_guides/trace_and_breakpoints.md)。

## 缺失实现处理

`stnp.init()` 默认 `check_implementations()`：某 CMD 在 Module 与其全部 Instance 都没有 `.func` 时 `logger.warning`，并返回缺失消息列表。收到未实现 CMD 时跳过业务并记 warning，不让 Dispatch 线程崩溃。可用 `warn_missing=False` 关闭启动检查。

## 异常隔离与 `stnp.stats`

`_dispatch_frame` 用 `try/except Exception` 包住 Task/Notify 分发：用户异常计入 `callback_errors` 并 `LOG.exception`，不撕毁运行时。未知 Instance / 未知 CMD **不再** `raise ProtocolError`：两闸都开时走 `_report_unknown("task", ...)`，且 **禁止**计入 `callback_errors`。用户 unknown 回调自身的异常在 `_report_unknown` 内隔离，同样不增加 `callback_errors`。

`stnp.stats`（`RuntimeStats`）字段：`rx_bytes` / `tx_bytes` / `rx_frames` / `tx_frames` / `crc_errors` / `protocol_errors` / `dropped_frames` / `callback_errors`。RX 读失败（且未处于 shutdown）记异常日志并结束 RX 循环。

## `stnp.init` 与配置边界

包入口 `stnp/__init__.py` 持有单例 `Runtime(PROTOCOL, REGISTRY)`。`stnp.init(...)` **先**调用 `trace.load()`（`config/trace.yaml` 查找链），再加载 `stnp.yaml`。配置查找顺序：显式 `config` 路径 → 环境变量 `STNP_CONFIG` → 当前工作目录 `config/stnp.yaml` → 生成包旁的 `config/stnp.yaml`。根必须是 mapping。

未传入 `transport` 时读取 YAML 的 `transport` 字段，仅内建 `"uart"`：先按 UART SDK 规则检查 `pyserial` 发行包，再构造 `UARTTransport(port=..., baudrate=...)`。其它名字抛 `RuntimeError`，要求调用方传入自定义 Transport。`queue_size` 默认取 YAML `runtime.dispatch_queue`（缺省 1024）；`warn_missing` 默认取 `runtime.warn_missing_implementation`（缺省 True）。

协议 YAML、运行时 YAML、UART YAML 三份文件不要混用。自定义 Transport 只需提供 `open` / `close` / `read` / `write`。

发送侧 codec（`core/codec.py`）在构帧前把字段转为整数，检查基础类型范围（`u8/u16/u32/i32`）以及 FieldSpec 的 min/max；失败抛 `ProtocolError`，不会写出半帧。无字段的命令若仍传入 payload 同样失败。

## 稳定性边界

Python 运行时不是硬实时：依赖 OS 线程、`queue.Queue` 与解释器 GIL。适合 PC 上位机与联调，不替代 MCU 上的 C Deferred Runtime。C 侧 `Process`/`Dispatch` 每次最多一帧/一 Job；Python 侧 RX 一次 `feed` 可解析多帧，但 Dispatch 仍按队列逐项执行。两端 wire 槽位由同一份 `.stnp` 生成，执行模型不必相同。

## `notify_dispatch_receive` 运行时门控

`stnp.notify_dispatch_receive_enable/disable/is_enabled` 对应协议选项初值，门控**整条 Notify 接收分发路径**（关闭时 typed 与 `@stnp.on_notify` 都不投递）。C 对等 API 为 `STNP_NotifyDispatchReceive_*`。两端独占语义对齐，但 C 另有模块 `NotifyCallbackEnable`，Python 以 `fn is not None` 为认领；测试禁止假设 C enable-off ≡ Python 有-func。

---

[← C 运行时](c_runtime.md) | [文档目录](../README.md) | [使用指南 →](../06_guides/README.md)
