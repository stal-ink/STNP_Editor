# Python API

本页给 Python 使用者：STNP Editor 0.9.0 生成包的标准签名来源。示例以生成后的顶层包 `stnp` 为准，取证于 `tests/golden/python/regression_py/regression_py_STNP_Python/stnp/**` 与对应模板。

Python 与 C 共用同一份 IR 和相同的 wire 协议，但执行模型面向有操作系统的环境：descriptor、dataclass、装饰器、调用线程 TX + RX 线程 + Dispatch 线程。不要用 C 的 `Implementation/` 或裸机 `Process`/`Dispatch` 循环去理解本页。

## 1. 生成包与公开命名空间

Python Target 生成后使用统一顶层命名空间：

```text
stnp
├─ core        Runtime / frame / codec / descriptor / transport
├─ sdk         官方 SDK，例如 stnp.sdk.uart
└─ protocol    Editor 生成的 Module / Instance / Payload / Registry
```

常用导入：

```python
import stnp
from stnp import Motor, MotorLeft, MotorRight
```

`stnp` 会重新导出当前协议的 Module 与 Instance，因此普通业务代码不需要从内部路径读取 registry。

---

## 2. Module 与 Instance

这是 Python Target 最重要的概念之一。

### 2.1 Module：协议定义

Module 描述一类设备/功能的协议能力：

```python
Motor.cmd.MOVE
Motor.cmd.STOP

Motor.notify.REACHED
Motor.notify.ERROR

Motor.OK
Motor.OVERLOAD
```

一个 Module 只生成一份 Command / Notify / Result / Payload 定义。

### 2.2 Instance：可路由实体

Instance 是线上真正携带 Instance ID 的实体：

```python
MotorLeft.id
MotorRight.id

MotorLeft.module is Motor
MotorRight.module is Motor
```

例如 `MotorLeft` 和 `MotorRight` 可以共享 `Motor.cmd.MOVE`，但它们拥有不同的 Instance ID。

**Module 决定“能做什么”，Instance 决定“消息发给谁/来自谁”。**

---

## 3. Payload：生成的 dataclass

有 Payload 的 Command / Notify 会生成 `dataclass(frozen=True, slots=True)`。

例如：

```python
from stnp.protocol.payloads.motor import MovePayload, ReachedNotifyPayload

move = MovePayload(speed=1200, direction=0)
reached = ReachedNotifyPayload(position=1200)
```

通常不需要手动创建 Payload，以下调用会自动构造：

```python
stnp.task.MotorLeft.MOVE(speed=1200, direction=0)
```

也可以显式传生成的 Payload 对象：

```python
payload = MovePayload(speed=1200, direction=0)
stnp.task.MotorLeft.MOVE(payload)
```

当前 Python codec 对协议字段提供 `u8 / u16 / u32 / i32` 编解码，并使用 little-endian。发送时会检查：

- Python 值是否可转换为整数；
- 基础类型范围；
- `.stnp` 中配置的 `min / max`。

接收时首先检查 Payload 长度并反序列化为生成 dataclass；业务范围检查应通过 Command 校验函数完成。

---

## 4. Task / Command 发送

Task 表示“向某个 Instance 发送某个 Command”。Python 提供三种入口，它们最终都进入同一 Runtime。

### 4.1 立即发送：推荐用于普通单帧

```python
written = stnp.task.MotorLeft.MOVE(
    speed=1200,
    direction=0,
)
```

语义：

```text
Instance + Command + Payload
        ↓
编码 Task Frame
        ↓
Transport.write()
```

返回值 `written` 是本次 Transport 写出的字节数。

无 Payload Command：

```python
stnp.task.MotorLeft.STOP()
```

### 4.2 动态路由：适合框架/通用代码

Descriptor 方式：

```python
stnp.task(
    MotorLeft,
    Motor.cmd.MOVE,
    speed=1200,
    direction=0,
)
```

Command 还可以使用名称或 code：

```python
stnp.task(MotorLeft, "MOVE", speed=1200, direction=0)
stnp.task(MotorLeft, 1, speed=1200, direction=0)
```

Runtime 会检查 Command 是否属于该 Instance 的 Module。

### 4.3 `Instance.task.CMD(...)`：只构造 TaskSpec，不立即发送

```python
item = MotorLeft.task.MOVE(speed=1200, direction=0)
```

此时 `item` 是 `TaskSpec`。

它的用途是 TaskSet / 批量发送：

```python
stnp.task(
    MotorLeft.task.MOVE(speed=1200, direction=0),
    MotorRight.task.MOVE(speed=900, direction=1),
    MotorLeft.task.STOP(),
)
```

Runtime 会先编码全部 TaskFrame，然后：

```text
frame1 + frame2 + frame3
          ↓
一次 Transport.write()
```

这就是 Python 端的多帧任务集，适合高频连续发送。

> `Instance.cmd.CMD(...)` 与 `Instance.task.CMD(...)` 指向同一 `BoundCommand`；面向发送语义时推荐写 `.task`。

---

## 5. Command 实现：`@Module.cmd.CMD.func`

Python 不要求 C 风格 `Implementation/` 目录。只要用户文件在 `stnp.init()` 前被 import，装饰器就会完成注册。

### 5.1 有 Payload 的 CMD

标准签名：

```python
@Motor.cmd.MOVE.func
def motor_move(self, payload):
    print(self.name)
    print(payload.speed)
    print(payload.direction)
```

参数含义：

| 参数 | 含义 |
|---|---|
| `self` | 实际收到 Task 的具体 Instance，例如 `MotorLeft` |
| `payload` | 已经反序列化的生成 Payload dataclass |

它对应 C 端的语义：

```c
void Motor_Move(MotorHandle *self, const Motor_MovePayload *payload);
```

### 5.2 无 Payload 的 CMD

标准签名只有一个参数：

```python
@Motor.cmd.STOP.func
def motor_stop(self):
    print(self.name)
```

不要写成：

```python
# 错误：STOP 没有 payload
def motor_stop(self, payload):
    ...
```

---

## 6. Instance 级 CMD Override

Module handler 是所有该 Module Instance 的默认实现：

```python
@Motor.cmd.MOVE.func
def default_move(self, payload):
    ...
```

某个 Instance 可以单独覆盖：

```python
@MotorLeft.cmd.MOVE.func
def left_motor_move(self, payload):
    ...
```

解析顺序固定为：

```text
Instance override
      ↓ 没有
Module implementation
      ↓ 没有
Missing implementation
```

因此：

```text
MotorLeft  -> left_motor_move()
MotorRight -> default_move()
```

这是 Python 多实例业务差异的推荐实现方式，不需要复制一套 Module。

---

## 7. Command 校验函数：`@...validate`

只有 `.stnp` 中 `validate_hook: true` 的 Command 才能注册校验函数。

### 7.1 有 Payload

```python
@Motor.cmd.MOVE.validate
def validate_move(self, payload):
    if abs(payload.speed) > 2000:
        return Motor.OVERLOAD
    return Motor.OK
```

### 7.2 无 Payload

```python
@Module.cmd.RESET.validate
def validate_reset(self):
    return Module.OK
```

### 7.3 Instance 级校验函数 Override

```python
@MotorLeft.cmd.MOVE.validate
def validate_left_move(self, payload):
    ...
```

校验函数解析顺序与 CMD implementation 相同：Instance override 优先于 Module 校验函数。

### 7.4 校验函数的执行行为

收到 Task 后：

```text
Frame / CRC
   ↓
Payload deserialize
   ↓
校验函数（如果注册）
   ↓ OK
CMD implementation
```

如果校验函数返回非 `Module.OK`，CMD implementation 不执行。Module 开启 `auto_notify_enabled` 后，自动通知由 Command 装饰器包装层完成：`.validate` 在非 OK 时发送 `notify_on_reject`；`.func` 在调用用户函数前发送 `notify_on_accept`，用户函数正常返回后发送 `notify_on_done`。Runtime dispatch 本身不包含 ACCEPT / REJECT / DONE 自动发送逻辑。

关闭 `auto_notify_enabled` 时，`notify_on_*` 仍只是 Descriptor 元数据；业务需要时可继续主动调用 `stnp.notify(...)`。自动通知引用必须是零 Payload Notify。

未注册用户校验函数时，Runtime 调用模块生成的 `validator`（例如 `validate_link(instance, code, payload)`），按命令码分派并检查字段范围。用户 `@Module.cmd.CMD.validate` 覆盖该生成入口。`.stnp` 里 `validate_hook` 仍是布尔，不携带命令码。

---

## 8. Notify：与 Command 独立的协议原语

Notify 不是某个 Command 的成员动作。它本身由：

```text
Source Instance
Notify Code
Result Code
Payload
```

组成。

这与 C Core：

```c
STNP_Notify_Send(source, notify_code, result, payload);
```

保持一致。

### 8.1 立即发送 Notify

```python
stnp.notify.MotorLeft.REACHED(
    Motor.OK,
    position=1200,
)
```

无 Payload Notify：

```python
stnp.notify.LinkMain.READY(Link.OK)
```

### 8.2 动态发送 Notify

```python
stnp.notify(
    MotorLeft,
    Motor.notify.REACHED,
    Motor.OK,
    position=1200,
)
```

也可用 notify 名称/code：

```python
stnp.notify(MotorLeft, "REACHED", Motor.OK, position=1200)
stnp.notify(MotorLeft, 1, Motor.OK, position=1200)
```

### 8.3 NotifySpec 与批量发送

`Instance.notify.NOTIFY(...)` 只构造 `NotifySpec`：

```python
n1 = MotorLeft.notify.REACHED(Motor.OK, position=1200)
n2 = MotorRight.notify.REACHED(Motor.OK, position=900)

stnp.notify(n1, n2)
```

多个 NotifySpec 同样会合并为一次 Transport write。

---

## 9. Notify callback：为什么是 `instance, result, payload`

Notify 帧天然携带 Source Instance 与 ResultCode，因此 callback 与 CMD handler 的参数不同。

### 9.1 有 Payload 的 Notify

标准 Module callback：

```python
@Motor.notify.REACHED.func
def on_motor_reached(instance, result, payload):
    print(instance.name)
    print(result)
    print(payload.position)
```

参数：

| 参数 | 类型/语义 |
|---|---|
| `instance` | 发送 Notify 的具体 Instance，例如 `MotorLeft` |
| `result` | 已识别时为 `MotorResult` IntEnum，例如 `Motor.OK`；未知值保持为 `int` |
| `payload` | 已反序列化的 `ReachedNotifyPayload` 等生成 dataclass |

例如线上收到：

```text
MotorLeft + REACHED + MOTOR.OK + payload
```

Runtime 调用：

```python
on_motor_reached(
    MotorLeft,
    Motor.OK,
    ReachedNotifyPayload(position=1200),
)
```

### 9.2 无 Payload 的 Notify

标准签名只有两个参数：

```python
@Link.notify.READY.func
def on_ready(instance, result):
    print(instance.name, result)
```

### 9.3 Instance 级 Notify callback

Module 默认：

```python
@Motor.notify.REACHED.func
def on_reached(instance, result, payload):
    ...
```

只处理 `MotorLeft` 的特殊 callback：

```python
@MotorLeft.notify.REACHED.func
def on_left_reached(instance, result, payload):
    ...
```

解析顺序仍然是 Instance callback → Module callback。

### 9.4 为什么 CMD 用 `self`，Notify 用 `instance`

两者本质上都是 `InstanceDefinition`，只是语义不同：

```text
CMD:
“这个实例被要求执行一件事”
→ handler(self, payload)

Notify:
“某个实例向我报告一件事”
→ callback(instance, result, payload)
```

参数名不是 Runtime 强制的；写成别的名字也能运行。但官方文档统一使用 `self` 和 `instance`，让语义更容易阅读。

---

## 10. 全局 Notify callback：`@stnp.on_notify`

如果需要观察所有 Notify，可以注册全局 callback：

```python
@stnp.on_notify
def on_any_notify(instance, notification, result, payload):
    print(instance, notification, result, payload)
```

对**已识别的 Instance + Notification**，参数为：

```text
InstanceDefinition
NotificationDescriptor
ModuleResult / int
生成 Payload dataclass / None
```

对于无法识别的路由，fallback 会保留更原始的信息：

```text
未知 Instance:
(source_id, notify_code, result, raw_payload_bytes)

已知 Instance、未知 Notify code:
(instance, notify_code, result, raw_payload_bytes)
```

因此全局 callback 如果用于协议诊断，应允许 descriptor/int 与 dataclass/bytes 两种情况。

---

## 11. ResultCode

ResultCode 直接属于 Module，不使用冗长的：

```python
stnp.resultcode.MOTOR.OK
```

推荐：

```python
Motor.OK
Motor.OVERLOAD
Motor.NOT_READY
```

生成类型是 `IntEnum`，因此既有语义名称，也可作为整数写入 Notify Frame：

```python
int(Motor.OK)
```

收到 Notify 时，Runtime 会尝试把结果值恢复为该 Module 的 Result Enum；无法识别的数值保留为普通 `int`。

---

## 12. 缺失 CMD 实现检查

默认 `stnp.init()` 会扫描所有 Module/Instance：

```python
stnp.init()
```

如果某个 CMD 在 Module 和 Instance 两级都没有 `.func`：

```text
MOTOR.MOVE not implemented; instances: MotorLeft, MotorRight
```

会通过 logger 给出 warning。

也可主动检查：

```python
missing = stnp.check_implementations()
for item in missing:
    print(item)
```

关闭初始化 warning：

```python
stnp.init(warn_missing=False)
```

或在 `config/stnp.yaml`：

```yaml
runtime:
  warn_missing_implementation: false
```

收到一个未实现 CMD 时不会让 Dispatch Thread 崩溃；Runtime 会记录 warning 并跳过业务实现。

---

## 13. 初始化与关闭

### 13.1 UART SDK 已生成

```python
import stnp

stnp.init()
```

UART 参数可显式覆盖：

```python
stnp.init(
    port="COM7",
    baudrate=921600,
)
```

Linux 示例：

```python
stnp.init(port="/dev/ttyUSB0", baudrate=115200)
```

### 13.2 自定义 Transport

```python
from stnp.core import Transport

class MyTransport(Transport):
    def open(self):
        ...

    def close(self):
        ...

    def read(self, size=4096) -> bytes:
        ...

    def write(self, data: bytes) -> int:
        ...

stnp.init(transport=MyTransport())
```

如果传了 `transport=...`，Runtime 使用该对象，不会自动创建 UARTTransport。

### 13.3 关闭

```python
stnp.shutdown()
```

它会停止 RX/Dispatch，并关闭 Transport。

### 13.4 Notify 接收分发运行时门控（0.9）

初值来自 `protocol.options.notify_dispatch_receive.enabled`，可在运行时切换：

```python
stnp.notify_dispatch_receive_enable()
stnp.notify_dispatch_receive_disable()
enabled = stnp.notify_dispatch_receive_is_enabled()
```

关闭时，收到的 Notify 帧不进入 Module callback 与 `@stnp.on_notify`。发送 `stnp.notify...` 不受此开关影响。该门控不改变 wire 格式。

---

## 14. 配置文件与优先级

三类配置必须分开理解。

### 14.1 协议配置：Editor 生成，不手改

```text
stnp/protocol/protocol.yaml
```

包含 SOF、CRC、Module、Instance、Command、Notify、Result、字段等协议事实。

### 14.2 Python Runtime 用户配置

```text
config/stnp.yaml
```

例如：

```yaml
transport: uart
runtime:
  dispatch_queue: 1024
  warn_missing_implementation: true
```

Runtime 配置查找顺序：

1. `stnp.init(config="...")` 指定路径；
2. 环境变量 `STNP_CONFIG`；
3. 当前工作目录 `config/stnp.yaml`；
4. 生成工程自带 `config/stnp.yaml`。

显式 `queue_size=` / `warn_missing=` 参数优先于 YAML。

### 14.3 UART SDK 配置

```text
stnp/sdk/uart/uart.yaml
```

```yaml
port: auto
baudrate: 115200
timeout: 0.02
write_timeout: 1.0
```

`stnp.init(port=..., baudrate=...)` 会覆盖 UART YAML 的 port / baudrate。

---

## 15. UART / pyserial 行为

UART SDK 检查的是发行包 **`pyserial`**：

```python
importlib.metadata.version("pyserial")
```

确认成功后才：

```python
import serial
```

这样不会把另一个叫 `serial` 的发行包误认为 pyserial。

缺少依赖时会抛出清晰的 `TransportError`，并提示：

```text
pip install pyserial
```

当：

```yaml
port: auto
```

或没有显式 port 时，UART SDK 使用 `serial.tools.list_ports.comports()` 扫描可用串口，选择第一个并打印：

```text
[STNP] Auto selected serial port: COM5, baudrate: 115200
```

高频 TX 不会为每一帧主动 flush；TaskSet / NotifySet 会保持一次 `Serial.write()`。

---

## 16. Runtime 线程模型

Python 端主动利用 OS：

```text
用户/调用线程
  └─ Task / Notify encode
       └─ write lock
            └─ Transport.write()

stnp-rx
  └─ blocking read
       └─ stream parser / CRC
            └─ bounded dispatch queue

stnp-dispatch
  └─ payload decode
       ├─ 校验函数
       ├─ CMD implementation
       └─ Notify callback
```

只有两个后台线程：RX + Dispatch。没有额外 TX worker。

这样用户 callback 偶尔变慢时，RX 仍能继续从 OS/串口读取数据；callback 执行时也不持有 TX lock，因此 callback 内允许再次发送 Task/Notify。

---

## 17. Runtime Stats

可直接查看：

```python
print(stnp.stats)
```

字段：

```text
rx_bytes
tx_bytes
rx_frames
tx_frames
crc_errors
protocol_errors
dropped_frames
callback_errors
```

适合高频串口联调时观察 CRC、队列丢帧与用户 callback 异常。

---

## 18. 完整最小示例

```python
import time
import stnp
from stnp import Motor, MotorLeft, MotorRight


@Motor.cmd.MOVE.validate
def validate_move(self, payload):
    if abs(payload.speed) > 2000:
        return Motor.OVERLOAD
    return Motor.OK


@Motor.cmd.MOVE.func
def move(self, payload):
    print("TASK", self.name, payload)

    # CMD 完成后的 Notify 由业务明确发送。
    stnp.notify(
        self,
        Motor.notify.REACHED,
        Motor.OK,
        position=payload.speed,
    )


@Motor.notify.REACHED.func
def reached(instance, result, payload):
    print("NOTIFY")
    print(" instance:", instance.name)
    print(" result  :", result)
    print(" payload :", payload)
    print(" position:", payload.position)


stnp.init()

# 单帧立即发送
stnp.task.MotorLeft.MOVE(speed=1200, direction=0)

# TaskSet：一次 Transport.write()
stnp.task(
    MotorLeft.task.MOVE(speed=800, direction=0),
    MotorRight.task.MOVE(speed=900, direction=1),
)

time.sleep(0.2)
print(stnp.stats)
stnp.shutdown()
```

---

## 19. 常见误解

**`MotorLeft.task.MOVE(...)` 为什么没有立即发送？**  
因为它用于构造 `TaskSpec`，让 `stnp.task(spec1, spec2, ...)` 能形成任务集。立即发送使用 `stnp.task.MotorLeft.MOVE(...)`。

**Notify 为什么不是 `Motor.move.notify(...)`？**  
因为 Notify 是独立协议原语，不隶属于某个 Command。正确入口是 `Motor.notify.REACHED` / `MotorLeft.notify.REACHED` / `stnp.notify...`。

**CMD handler 为什么没有 result？**  
Task/CMD 是请求帧，没有 ResultCode 字段。ResultCode 属于 Notify。

**Notify callback 为什么比 CMD handler 多一个 result？**  
Notify Frame 本身携带 ResultCode，所以 Runtime 会把它传给 callback。

**装饰器文件必须放在 `User/` 吗？**  
不必须。业务文件可以放在任意用户目录；关键是必须在 `stnp.init()` 和接收业务帧前被 import。可选 `User/` scaffold 只是脚手架。

**`notify_dispatch_receive_disable()` 之后还能发 Notify 吗？**  
能。该开关只门控本端接收分发，不阻止发送。

---

[← API 索引](../README.md) | [文档目录](../../README.md) | [使用指南 →](../../06_guides/python_usage.md)
