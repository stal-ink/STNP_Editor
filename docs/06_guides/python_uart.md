# Python UART SDK

本页说明 `stnp.sdk.uart` 的生成条件、pyserial 检查、配置与高频发送。它属于统一 `stnp` 命名空间。

## 1. 生成条件

在 `stnp.build.json` 的 `python_sdks` 中选择 `uart` 后生成：

```text
stnp/sdk/uart/
├─ __init__.py
├─ config.py
├─ transport.py
└─ uart.yaml
```

协议配置仍位于：

```text
stnp/protocol/protocol.yaml
```

两者不可混为一份配置。

## 2. pyserial 检查

SDK 不用单纯 `import serial` 判断依赖，而先检查发行包：

```python
importlib.metadata.version("pyserial")
```

只有确认 `pyserial` 安装后才：

```python
import serial
from serial.tools import list_ports
```

这样可以避免系统里安装了另一个名为 `serial` 的包而误判。

缺失时抛出 `TransportError`，提示：

```text
STNP UART SDK requires the 'pyserial' distribution. Install it with: pip install pyserial
```

## 3. UART YAML

默认：

```yaml
port: auto
baudrate: 115200
timeout: 0.02
write_timeout: 1.0
```

文件位置：

```text
stnp/sdk/uart/uart.yaml
```

这是**用户可配置的 UART SDK 配置**，不是协议事实源。

## 4. 初始化

最简单：

```python
import stnp
stnp.init()
```

显式覆盖 port / baudrate：

```python
stnp.init(port="COM7", baudrate=921600)
```

参数优先于 `uart.yaml`。

## 5. 自动扫描串口

当 `port` 为 `auto` / 空值，并且没有传 `port=`：

```python
serial.tools.list_ports.comports()
```

扫描可用串口。

当前实现选择扫描结果中的第一个端口，并打印：

```text
[STNP] Auto selected serial port: COM5, baudrate: 115200
```

没有检测到串口时抛出 `TransportError`，要求用户连接设备或显式指定 port。

## 6. 高频发送设计

TX 位于用户调用线程：

```text
stnp.task / stnp.notify
      ↓
encode
      ↓
write lock
      ↓
UARTTransport.write()
```

UART SDK 不为每帧执行 flush。

TaskSet：

```python
stnp.task(
    MotorLeft.task.MOVE(speed=1000, direction=0),
    MotorRight.task.MOVE(speed=1000, direction=1),
)
```

会先把多帧拼接，再执行一次 `serial.write(data)`，减少多帧调用开销。

## 7. RX

Runtime 的 `stnp-rx` 线程调用：

```python
transport.read(4096)
```

UARTTransport 根据 `in_waiting` 读取当前可用数据；没有数据时依赖 pyserial timeout 阻塞/返回。

RX 线程只负责读取、Stream Parser、CRC 和入队，不直接执行用户 callback。

## 8. 自定义 UARTTransport

高级用户可显式创建：

```python
from stnp.sdk.uart import UARTTransport

transport = UARTTransport(
    port="COM7",
    baudrate=921600,
    timeout=0.01,
    write_timeout=0.5,
)

stnp.init(transport=transport)
```

当传入 `transport=` 时，`stnp.init()` 不再自动创建 UART Transport。

## 9. 配置边界

```text
stnp/protocol/protocol.yaml
    Editor 生成协议事实，C/Python 同源

config/stnp.yaml
    Python Runtime 设置，例如 dispatch queue

stnp/sdk/uart/uart.yaml
    UART 端口/波特率/timeout
```

协议配置不要放 port / baudrate；UART 配置也不要复制 SOF / CRC / Module 等协议字段。

自定义 Transport：继承 `stnp.core.Transport`，实现 `open/close/read/write`，再 `stnp.init(transport=...)`。传入 `transport=` 时不会自动创建 UART。

---

[← Python 使用](python_usage.md) | [文档目录](../README.md) | [多实例 →](multi_instance.md)
