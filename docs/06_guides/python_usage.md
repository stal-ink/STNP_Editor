# Python 使用指南

本页给第一次把 Python target 用起来的人：从生成到实现 CMD、校验函数、发送与监听 Notify。标准签名见 [Python API](../04_api/python/README.md)。仓库里可复制的双端工程是 `examples/dual_multi_c_py`。

## 生成 Python target

```bash
stnpe generate examples/dual_multi_c_py/dual_multi.stnp examples/dual_multi_c_py/stnp.build.python.json -o _out/python
```

生成根：`_out/python/dual_multi_STNP_Python/`。该示例 `emit_examples=false`，需要自己写上位机脚本；`python_sdks` 含 `uart`。

若把 `python.emit_examples` 设为 `true`，生成目录会有 `Example/main.py`，可用 MockSerial 在无串口时跑通装饰器与 TaskSet。C 回归夹具对应的 Python golden 在 `tests/golden/python/regression_py/regression_py_STNP_Python/`。

## 生成目录怎么读

```text
<stem>_STNP_Python/
├─ stnp/core/              Runtime、帧、编解码
├─ stnp/sdk/uart/          可选 UART SDK
├─ stnp/protocol/          Module / Instance / Payload（不要手改）
├─ config/stnp.yaml        运行时用户配置
├─ Example/                emit_examples 时
├─ User/                   emit_user_scaffold 时（create-once）
├─ pyproject.toml          生成包元数据（始终写出）
├─ .stnp-manifest.json     生成器清单（始终写出）
└─ README.md
```

业务代码放在任意会被 import 的 `.py` 文件，不必放在 `User/`。`stnp.protocol` 随 `.stnp` 重新生成；手改会在下次 `generate` 丢失。

## Module / Instance

Module 描述协议能力（命令、通知、结果码）；Instance 携带线上 ID。

```python
from stnp import Led, LedFront, LedRear, Motor, MotorLeft

LedFront.module is Led
MotorLeft.id
```

发送给谁、通知从谁来，都由 Instance 决定。同一个 Module 可以有多个 Instance。Python 侧没有 C 的 `STNP_INSTANCE_*_ID` 宏，直接使用生成的 Instance 对象。

## 实现 CMD

```python
@Led.cmd.SET.func
def led_set(self, payload):
    print(self.name, payload.state, payload.brightness)

@Led.cmd.GET.func
def led_get(self):
    print(self.name)
```

有 Payload 的 handler 签名是 `(self, payload)`；无 Payload 只有 `(self)`。Instance 级覆盖：`@LedFront.cmd.SET.func`。`CallbackSlot` 先查实例级，没有再回落到模块级。`stnp.init()` 默认会 `check_implementations()`：Module 与其全部 Instance 都没有 `.func` 时打 warning。

## 校验函数

仅 `validate_hook: true` 的命令可注册；否则 `@...validate` 抛 `RuntimeError`：

```python
@Led.cmd.SET.validate
def validate_set(self, payload):
    if payload.brightness > 100:
        return Led.REJECTED if hasattr(Led, "REJECTED") else Led.OK
    return Led.OK
```

未注册时走生成的 `module.validator`（按命令码分派字段范围）。非 `Module.OK` 时不执行 `.func`。自动通知（若 `auto_notify_enabled`）由装饰器包装层发送，不在 Runtime dispatch 里直接发：

```text
decode
  → 校验函数（用户或生成的 validate_<module>）
      非 OK → notify_on_reject（若 auto_notify_enabled）
  → notify_on_accept（若开启）
  → CMD .func
  → notify_on_done（若开启）
```

自动通知只能引用零 Payload Notify。带 Payload 的完成通知必须由业务 `stnp.notify...` 显式发送。

## 发送 CMD（三种方式）

立即发送：

```python
stnp.task.LedFront.SET(state=1, brightness=40)
```

动态：

```python
stnp.task(LedFront, Led.cmd.SET, state=1, brightness=40)
```

TaskSet（先构造 `TaskSpec`，一次 write）：

```python
stnp.task(
    LedFront.task.SET(state=1, brightness=40),
    LedRear.task.GET(),
)
```

发送发生在调用线程，持有 write lock 做一次 `transport.write`。回调内可以再发送（不持有该锁）。尚未 `stnp.init()` 会抛 `TransportError`。

## 监听 Notify

```python
@Led.notify.STATE_CHANGED.func
def on_led(instance, result, payload):
    print(instance.name, result, payload.state)

@stnp.on_notify
def on_any(instance, notification, result, payload):
    print(instance, notification, result, payload)
```

无 Payload 通知的 callback 只有 `(instance, result)`。本端接收分发可被 `stnp.notify_dispatch_receive_disable()` 关掉：帧仍会解析入队，但不进入 Module callback。未知 Instance/code 时全局回调收到更原始的 id/code/bytes。

## 发送 Notify

```python
stnp.notify.MotorLeft.REACHED(Motor.OK, position=100)
stnp.notify(MotorLeft, Motor.notify.REACHED, Motor.OK, position=100)
```

`Instance.notify.NAME(...)` 只构造 `NotifySpec`，交给 `stnp.notify(n1, n2)` 可批量一次写出。`RESULT` 用 Module 的 `ResultCode`（IntEnum）；未知值保持为 int。

## UART 联调

```python
import stnp
stnp.init(port="COM7", baudrate=115200)
```

详见 [Python UART](python_uart.md)。缺少 `pyserial` 发行包会在打开串口前失败。关闭时调用 `stnp.shutdown()`。用 `print(stnp.stats)` 观察 `crc_errors`、`dropped_frames`、`callback_errors`。

## 应用文件组织

推荐：一个 `app.py` import `stnp` 并注册全部装饰器，然后 `stnp.init()`。协议 YAML、`config/stnp.yaml`、`uart.yaml` 不要混用。可选 `User/` scaffold 只创建一次，重新生成永不覆盖。

线程模型：调用线程负责 TX；`stnp-rx` 读串口并解析；`stnp-dispatch` 跑用户函数。不要在回调里做长时间阻塞读。分层原因见 [Python 运行时](../05_architecture/python_runtime.md)。

## 推荐的双端测试顺序

1. 跑 `examples/dual_multi_c_py/run.ps1`，确认两端生成目录出现。
2. STM32 按 [STM32 HAL UART](stm32_hal_uart.md) 集成并烧录。
3. PC 写上位机：先 `@notify.func` 打印，再 `stnp.task...` 下发。
4. 用 `print(stnp.stats)` 观察 CRC 与丢帧。
5. 需要关接收分发时调用 `stnp.notify_dispatch_receive_disable()`，确认本端不再进入 Notify callback。

---

[← 指南索引](README.md) | [文档目录](../README.md) | [Python UART →](python_uart.md)
