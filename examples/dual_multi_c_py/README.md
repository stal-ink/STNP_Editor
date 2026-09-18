# dual_multi_c_py —— 一个协议、两种 target 的双端示例

## 架构

```text
dual_multi.stnp                       ← 协议唯一事实源（LED / MOTOR，2 个 Module，4 个 Instance）
├─ stnp.build.c.json                  ← target=c：STM32 下位机（cmake + stm32_hal_uart SDK）
└─ stnp.build.python.json             ← target=python：PC 上位机（python_sdks=["uart"]）

STM32（下位机）                               PC（Python 上位机）
  接收 Task，路由到 Implementation/*_impl.c      stnp.task(...) 下发 Task（TaskSet 合并为一次 write）
  业务实现用 STNP_Notify_Send() 发 typed Notify   装饰器回调反序列化并打印 Notify
                    └──────────── UART 115200 8N1 ────────────┘
```

本示例由原先的 `dual_STM32_Python_integration.zip` 双端联调工程整理而来：现在有正式的
`.stnp` 与两份 build 配置，可以直接重新生成，不再依赖预生成目录。

## 生成（两条命令）

```bash
# C 端（STM32 下位机）
stnpe generate examples/dual_multi_c_py/dual_multi.stnp examples/dual_multi_c_py/stnp.build.c.json -o _out/c

# Python 端（PC 上位机）
stnpe generate examples/dual_multi_c_py/dual_multi.stnp examples/dual_multi_c_py/stnp.build.python.json -o _out/python
```

或一次生成两端（不运行）：

```powershell
.\examples\dual_multi_c_py\run.ps1
```

生成目录分别为 `_out/c/dual_multi_STNP_C/` 与 `_out/python/dual_multi_STNP_Python/`。

- C 配置：`build_system=cmake`、`emit_examples=false`、`sdks=["stm32_hal_uart"]`
  ——没有预生成 Example，工程直接进 CubeMX；
- Python 配置：`emit_examples=false`、`emit_user_scaffold=true`、`python_sdks=["uart"]`
  ——生成 `User/` create-once 脚手架与 UART SDK，但上位机主程序由你编写（见下文片段）。

## 模块与实例语义

| Module | Command | Payload | 完成 Notify (`notify_on_done`) | `validate_hook` |
|---|---|---|---|---|
| LED | `SET` | `state` u8(0..1), `brightness` u8(0..100) | `STATE_CHANGED`（`state`, `brightness`） | 是 |
| LED | `GET` | 无 | `STATE_CHANGED` | 否 |
| LED | `BLINK` | `period_ms` u16(10..5000) | `STATE_CHANGED` | 是 |
| MOTOR | `MOVE` | `speed` i32(-3000..3000), `direction` u8(0/1) | `REACHED`（`position` i32） | 是 |
| MOTOR | `STOP` | 无 | `REACHED` | 否 |
| MOTOR | `SET_LIMIT` | `limit` u16(0..10000) | —（指挥） | 是 |

Notify 另有 `MOTOR.ERROR`（`error_code` u8，PUSH），用于运行时故障。

| Instance | Module | ID | 说明 |
|---|---|---|---|
| `LedFront` | LED | 1 | 与 `LedRear` 共享 LED 协议、各自路由 |
| `LedRear` | LED | 2 | |
| `MotorLeft` | MOTOR | 16 | 与 `MotorRight` 共享 MOTOR 协议 |
| `MotorRight` | MOTOR | 17 | |

返回码按 0.9 的模块分段规则：LED（第 0 个模块）`OK=0x0100`、MOTOR（第 1 个模块）`OK=0x0200`。
协议开启 CRC（`features.crc.enabled=true`），两端由同一 `.stnp` 生成，天然一致。

## PC 侧怎么起（需要串口）

`emit_examples=false`，因此生成目录里没有现成 `main.py`；请自己写一个上位机脚本，例如：

```python
import stnp
from stnp import Led, LedFront, LedRear, Motor, MotorLeft, MotorRight

@Led.notify.STATE_CHANGED.func
def on_led_state(instance, result, payload):
    print(instance.name, "STATE_CHANGED", result, payload.state, payload.brightness)

@Motor.notify.REACHED.func
def on_motor_reached(instance, result, payload):
    print(instance.name, "REACHED", result, payload.position)

@Motor.notify.ERROR.func
def on_motor_error(instance, result, payload):
    print(instance.name, "ERROR", result, payload.error_code)

stnp.init(port="COM7", baudrate=115200)   # 省略则读取 stnp/sdk/uart/uart.yaml（port: auto）
stnp.task(                                # TaskSet：4 帧一次 Transport write
    LedFront.task.SET(state=1, brightness=60),
    LedRear.task.BLINK(period_ms=500),
    MotorLeft.task.MOVE(speed=800, direction=0),
    MotorRight.task.SET_LIMIT(limit=2400),
)
input("按回车退出...")
stnp.shutdown()
```

准备步骤：

```bash
pip install pyserial                        # 生成目录的 pyproject.toml 已声明依赖
pip install -e _out/python/dual_multi_STNP_Python   # 或把生成目录加入 PYTHONPATH
```

`led_logic.py` / `motor_logic.py` 是 create-once 用户脚手架（来自被删除的联调包，
与 `emit_user_scaffold=true` 生成物同构）：把它们放进 `<生成目录>/User/` 并在主程序里
`import`，上位机就能在需要时响应 LED/MOTOR 命令（例如回环自测）；纯上位机场景下不导入即可。

## STM32 侧怎么集成

1. 按 [`stm32_hal_uart_c/README.md`](../stm32_hal_uart_c/README.md) 接入生成目录：
   CubeMX UART 全局中断、`add_subdirectory(<生成目录>)`、`STNP_HAL_UART_Init(&huart1)` +
   `STNP_Instances_Init()`，裸机主循环跑 `STNP_Process()` / `STNP_Dispatch()`。
2. 在 `Implementation/led_impl.c` / `motor_impl.c` 的 `USER CODE` 区域填业务，
   用 `self->base.id` 区分同 Module 的不同 Instance：

```c
void Led_Set(LedHandle *self, const Led_SetPayload *payload)
{
    Led_StateChangedPayload out = { payload->state, payload->brightness };
    (void)STNP_Notify_Send(self->base.id, LED_NOTIFY_STATE_CHANGED, LED_OK, &out);
}

void Motor_Move(MotorHandle *self, const Motor_MovePayload *payload)
{
    Motor_ReachedPayload reached = { 0 };

    if (payload->speed >= 3000)              /* 确定性过载，便于验证 MOTOR.ERROR */
    {
        Motor_ErrorPayload error = { 1U };
        (void)STNP_Notify_Send(self->base.id, MOTOR_NOTIFY_ERROR, MOTOR_OVERLOAD, &error);
        return;
    }
    reached.position = payload->speed;
    (void)STNP_Notify_Send(self->base.id, MOTOR_NOTIFY_REACHED, MOTOR_OK, &reached);
}
```

## 端到端自查步骤

1. 跑 `run.ps1` 或上面两条 `stnpe generate`，确认两端生成目录都出现；
2. STM32：接入 CubeMX 工程，填好 `Implementation/led_impl.c` / `motor_impl.c`，编译烧录；
3. PC：安装依赖、确认 `uart.yaml` 的 `port`/`baudrate`（或脚本里显式传参），运行上位机脚本；
4. 逐项核对 Notify：`LedFront.SET` 只回 `LedFront` 的 `STATE_CHANGED`（`0x01`）、
   `MotorRight.MOVE` 只回 `MotorRight` 的 `REACHED`（`0x11`），验证实例路由；
5. 发送 4 条 Task 的 TaskSet，确认 PC 端一次 write、四条 Notify 按序返回；
6. 发 `MotorLeft.MOVE(speed=3000)`，确认收到 `MOTOR.ERROR` / `OVERLOAD`；
7. 没有真实板子时，可用虚拟串口对（如 com0com）只验证 PC 侧收发，但这不代表 C 端业务正确——
   脚本不会在没有串口时假装运行成功。
