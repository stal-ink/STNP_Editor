# 01 Notify 独占分发

0.9.0 把「全局 + 模块同时收到」写成了设计。0.9.1 改为 **module XOR global**：模块认领后全局禁止再收。这是破坏性语义，禁止写成静默 bugfix。

发送路径、wire、`STNP_Notify_Send` / `stnp.notify` **禁止改**。只改接收分发。

切片 **A** 只落地本文件的分发语义。`format.maybe` 与 `STNP_BP_ON_NOTIFY` 分别属于 D / C，A 禁止插入。

## 0.9.0 现状（对照用，禁止保留）

### C（并行）

模板 `src/stnp_editor/resources/templates/c/Instance/stnp_instances.c.j2`，函数 `STNP_Notify_Dispatch`。

0.9.0 锚点（约 L21–32）：先无条件调用 `STNP_Notify_Callback`，再在 `STNP_NotifyDispatchReceive_IsEnabled() != 0` 时按 `source == STNP_INSTANCE_*_ID` **直接 `return <Module>_NotifyDispatch(...)`**。

模块 `NotifyCallbackEnable(STNP_ENABLE)` 之后，全局仍先跑。

`<Module>_NotifyDispatch`（`templates/c/Module/module/module.c.j2`，0.9.0 锚点约 L286–338）：VTL 命中且 Decode 成功后，无论 `g_notify_callback_enabled` 是否为 `STNP_ENABLE`，都 **`return STNP_OK`**。enable 只包住 `<Module>_NotifyCallback` 调用。因此「只把全局/模块对调顺序」**不等于**独占。

Core `templates/c/Core/stnp_notify.c.j2`（0.9.0 锚点约 L94–117）保留 `STNP_WEAK void STNP_Notify_Callback` 空实现，以及 weak 版 `STNP_Notify_Dispatch`（只调全局）。Implementation `stnp_notify_callback.c.j2` 提供用户可填的强符号 `STNP_Notify_Callback`。生成工程链接后全局回调恒可调用。

### Python（并行，且 DR 语义与 C 不一致）

模板 `src/stnp_editor/resources/templates/python/stnp/core/runtime.py.j2`，方法 `Runtime._dispatch_notify`。

0.9.0 锚点（约 L249–271）：

1. `notify_dispatch_receive_is_enabled()` 为假 → **函数开头直接 `return`**（模块 typed 与 `@stnp.on_notify` 都不跑）。
2. 为真 → 先 `@Notification.func`，再 `@stnp.on_notify`。已知码时全局收到的是 **解码后的** `(instance, notification, result, payload)`。

### 0.9.0 输出示例（并行问题）

假设：模块已 `NotifyCallbackEnable`，且注册了 `@stnp.on_notify`。对端发一帧 `SENSOR.DATA`。

```text
# C / Python 都会发生（顺序两端相反，结果都是双收）
[module] SENSOR.DATA value=1234
[global] SENSOR.DATA value=1234     ← 0.9.1 禁止再有
```

回归 `tests/test_generate_multi.py`::`test_notify_global_and_typed_callbacks_are_deferred_and_enable_semantics_hold` 在 enable 后断言 `g_raw_count==2 && g_typed_count==1`，把并行写进了测试。0.9.1 必须改断言。

## 「模块认领」定义（两端不得混用）

### C 认领（同时成立）

1. `STNP_NotifyDispatchReceive_IsEnabled() != 0`
2. `source` 命中已登记 Instance（`source == STNP_INSTANCE_<MACRO>_ID`）
3. `<Module>_NotifyCallbackIsEnabled() != 0`（0.9.1 新增；读的就是现有 `g_notify_callback_enabled == STNP_ENABLE`）
4. 该 Module 的 Notify VTL 找到 `notify_code`（`<Module>_NotifyDispatch` 返回值 **不是** `STNP_ERR_COMMAND`）
5. Decode 成功（返回 `STNP_OK`）→ 只调 `<Module>_NotifyCallback`，禁止再调全局

Decode 失败（已知码，返回值不是 `STNP_OK` 也不是 `STNP_ERR_COMMAND`）：算 **模块路径错误**。禁止落入全局。`STNP_Notify_Dispatch` 必须把该错误码原样返回。

未知码（VTL 未命中 / `switch` default）：`<Module>_NotifyDispatch` 返回 `STNP_ERR_COMMAND`。这是 **唯一** 允许落入全局的模块返回值。

C 全局 `STNP_Notify_Callback` 在生成工程里恒可调用（Core weak 空实现 + Implementation 强符号）。**禁止**增加 `STNP_Notify_CallbackEnable`。用户只实现 `stnp_notify_callback.c` 就必须能收未认领帧。

`<Module>_NotifyDispatch` 内部对 `g_notify_callback_enabled` 的判断 **必须保留**（防御直接调用）。独占路由 **禁止** 依赖这个内部判断来决定是否落入全局。

### Python 认领（同时成立）

1. `notify_dispatch_receive_is_enabled()` 为真
2. `SOURCE` 命中 `registry.instances_by_id`
3. `instance.module.notify.by_code(notify_code)` 不是 `None`
4. `notification._func.resolve(instance.id)` 不是 `None`

四条都成立之后才允许 `decode_payload`。然后 `format.maybe`（D 切片）、调用 typed func、**`return`**。禁止再调 `_notify_callback`。

Python **没有** C 那种模块 Enable。typed 路径的「handler」就是 `_func.resolve is not None`。Python **没有** `NotifyCallbackEnable`。

**必须**：C 模块 enable-off 与 Python「已有 typed func」**不是**同一行为。C：`IsEnabled()==0` 即使 typed callback 符号存在也落入全局。Python：`fn is not None` 即认领，禁止再走全局。测试 **禁止** 假设两端 enable-off / 有-func 行为相同。这是有意不对称，不是漏实现。

Python 全局已注册 = `_notify_callback is not None`。DR **禁止**门控全局。

### Python 已知码但 `fn is None`（硬顺序）

必须先 `resolve`。`fn is None` 时：

- 禁止为模块路径 decode
- 禁止把 dataclass / `NotificationDescriptor` 传给全局
- 落入全局，签名与「已知实例 + 未知码」相同：`(instance, code, result, raw bytes)`，其中 `code` 是 `int`（`frame.notify_code`），`raw bytes` 是 `frame.payload`

### Python `@stnp.on_notify` 签名（0.9.1 只剩两种 raw 形）

独占之后全局 **禁止** 再收到 `NotificationDescriptor` 或解码 dataclass。合法形只有：

| 条件 | 调用 |
|---|---|
| `instance is None` | `(source_id, code, result, raw bytes)` = `(frame.source, frame.notify_code, frame.result, frame.payload)` |
| `instance is not None`（未知码，或已知码但 `fn is None`） | `(instance, code, result, raw bytes)` = `(instance, frame.notify_code, frame.result, frame.payload)` |

## 决策表

记号：`DR` = `notify_dispatch_receive`。

| # | DR | SOURCE | notify_code | 模块 enable / handler | 全局 | 行为 |
|---|---|---|---|---|---|---|
| A | 关 | 任意 | 任意 | 忽略 | 任意 | **不投递**（模块 typed 与全局都不触发） |
| B | 开 | 未知 | 任意 | 否 | 有 | **只全局**（`(source_id, code, result, raw)`） |
| C | 开 | 已知 | 未知 | enable 开 / `by_code` 为 None | 有 | **只全局**（`(instance, code, result, raw)`） |
| D | 开 | 已知 | 已知 | C：`IsEnabled` 为 0；Python：`fn is None` | 有 | **只全局**（Python raw 形，禁止 decode） |
| E | 开 | 已知 | 已知 | **已认领** | 任意 | **只模块**；全局 0 次 |
| F | 开 | 已知 | 已知 | 已过 IsEnabled/fn 非 None，Decode 失败 | 任意 | 模块路径错误，禁止转全局 |
| G | 开 | 任意 | 任意 | 未认领 | 无（仅 Python） | 丢弃；未知回调两闸都开时见 02 |
| H | 开 | 已知 | 已知 | C enable 开，callback 仍是 weak 空实现 | 有 | 仍算认领 → 只调空模块 callback，禁止全局 |

行 G 的 Python 未知 Notify 属于切片 B，A 必须留出「全局也没有」的末端，禁止在 A 把帧默默吞掉之外再发明第三条业务路径。

## DR 管辖范围（服从冻结规范 §8.3，本批次不改）

`notify_dispatch_receive` 是 **整条 Notify 接收分发路径的总门**，不是 typed-only。C / Python 必须一致：

- DR 关：不认领模块、不进全局（`STNP_Notify_Callback` / `@stnp.on_notify` 都不触发）。帧仍解析并入队；发送与 wire 不受影响。
- DR 开：再按独占判定。认领成功只模块；未认领才全局。

0.9.0 Python 已在 `_dispatch_notify` 开头 `return`。0.9.1 **禁止**把该早退删掉，也禁止把 DR 收窄成只门控 typed。C 必须把早退放在 `STNP_Notify_Dispatch` **最前**（纠正 0.9 把全局回调放在 DR 判断之前的偏离）。

## 0.9.1 目标代码（必须按此语义实现）

### C `STNP_Notify_Dispatch`

文件：`templates/c/Instance/stnp_instances.c.j2`。替换整个函数体。禁止只把 0.9.0 的「全局在前」改成「模块在前」。

```c
STNP_Result STNP_Notify_Dispatch(STNP_U8 source, STNP_U8 notify_code,
                                 STNP_U16 result, const STNP_U8 *payload, STNP_U8 length)
{
    if (STNP_NotifyDispatchReceive_IsEnabled() == 0U)
    {
        return STNP_OK;   /* DR 关：不认领、也不进全局 */
    }
    /* 按 source 命中 Instance；ID 唯一，命中后禁止继续扫后续 instance */
    if (命中 && <Module>_NotifyCallbackIsEnabled() != 0U)
    {
        STNP_Result r = <Module>_NotifyDispatch(...);
        if (r != STNP_ERR_COMMAND)
        {
            /* 仅当 r==STNP_OK 时，在本 return 之前打一次 STNP_BP_ON_NOTIFY()。 */
            return r;   /* 已知码独占结束（含 decode 失败） */
        }
        /* 未知码：落入全局 */
    }
    STNP_BP_ON_NOTIFY();
    STNP_Notify_Callback(source, notify_code, result, payload, length);
    return STNP_OK;
}
```

硬约束：

0. **DR 关必须函数最前 `return STNP_OK`。** 禁止只把 DR 包住模块段、让全局落在 DR 块外面。
1. **必须**在调用 `<Module>_NotifyDispatch` **之前**检查 `<Module>_NotifyCallbackIsEnabled()`。
2. **禁止**用「模块 Dispatch 返回 `STNP_OK`」反推认领：enable 关闭且码已知时 Dispatch 仍返回 `STNP_OK` 且不调 callback。
3. source 命中但 `IsEnabled()==0`：禁止调用 `NotifyDispatch`，直接落入全局。
4. 切片 C 才允许在「即将 `return r`（模块独占成功路径，`r==STNP_OK`）」以及「调用 `STNP_Notify_Callback` 之前」插入 **一次** `STNP_BP_ON_NOTIFY()`。A 禁止插入。模块 decode 失败（`r` 既非 OK 也非 `STNP_ERR_COMMAND`）禁止打 `ON_NOTIFY`。

### C 新增 `<Module>_NotifyCallbackIsEnabled`

- `templates/c/Module/module/module.h.j2`：紧挨现有 `{{ m.notify_callback_enable_fn }}` 声明之后，增加  
  `STNP_U8 {{ m.pascal }}_NotifyCallbackIsEnabled(void);`
- `templates/c/Module/module/module.c.j2`：与 `{{ m.notify_callback_enable_fn }}` 读写 **同一** `g_notify_callback_enabled`。必须返回 `(STNP_U8)(g_notify_callback_enabled == STNP_ENABLE)`（1 或 0）。禁止第二份 flag。
- IR：`ModuleIR` 增加 `notify_callback_is_enabled_fn`；`ir/builder.py` 赋值为 `f"{pascal}_NotifyCallbackIsEnabled"`；`_validate_c_symbols` 的 `claim_public` 必须登记该符号。

### Python `_dispatch_notify`

文件：`templates/python/stnp/core/runtime.py.j2`。

**必须保留**函数开头的早退（在 trace / 认领 / 全局之前）：

```python
if not self.notify_dispatch_receive_is_enabled():
    return
```

目标顺序：

```python
def _dispatch_notify(self, frame: NotifyFrame) -> None:
    if not self.notify_dispatch_receive_is_enabled():
        return
    instance = self.registry.instances_by_id.get(frame.source)
    notification = None
    fn = None
    if instance is not None:
        notification = instance.module.notify.by_code(frame.notify_code)
        if notification is not None:
            fn = notification._func.resolve(instance.id)

    if fn is not None:
        payload = decode_payload(notification, frame.payload)  # 认领之后才 decode
        result = instance.module.result(frame.result)
        # D：此处插入 format.maybe；C：调用 typed fn 前 debug.bp("on_notify")
        if payload is None:
            fn(instance, result)
        else:
            fn(instance, result, payload)
        return

    if self._notify_callback is not None:
        # C：debug.bp("on_notify") 必须在调用全局 _notify_callback 之前（与 03/04 一致）。
        # D：format.maybe 仍必须跑（见 03 全局 fallback；descriptor=None）。A 禁止插入。
        if instance is None:
            self._notify_callback(frame.source, frame.notify_code, frame.result, frame.payload)
        else:
            self._notify_callback(instance, frame.notify_code, frame.result, frame.payload)
        return

    # B：无人认领 → unknown reason="notify"（两闸都开才报）
```

`decode_payload` 抛错：已经进入认领分支，禁止再调全局；异常仍由现有 `_dispatch_frame` 捕获并计入 `callback_errors`。

## 输出示例（0.9.1）

场景：`SensorFront`（id=3）发 `SENSOR.DATA`，payload `value=1234`。模块已 Enable 且有 typed handler；同时挂了全局。

```text
[module] SensorFront SENSOR.DATA result=OK value=1234
# 全局无输出
```

场景：同一工程，模块 **未** Enable（C）或 `fn is None`（Python）。

```text
[global] source=3 code=<DATA 的 notify_code> result=OK payload=<raw bytes>
# 模块无输出；Python 全局参数禁止出现 dataclass
```

场景：DR 关闭，Python 仍注册了 `@stnp.on_notify`。

```text
# typed 与全局均无输出（冻结规范 §8.3）
```

场景：未知 SOURCE `0x09`，有全局。

```text
[global] source_id=0x09 notify_code=0x02 result=0 payload=b'\xd2\x04'
```

## 默认与兼容

| 项 | 0.9.0 | 0.9.1 |
|---|---|---|
| `options.notify_dispatch_receive.enabled` | 默认随工程 | schema **禁止**改键 |
| C 模块 enable | 默认 `STNP_DISABLE` | 不变 |
| C 全局 | 每帧都调 | 未认领时才调 |
| Python 全局 | 与模块并行；被 DR 总门控 | 与模块独占；DR 仍是总门（关则全局也不投递） |
| 全局-only 用户 | 可用 | 可用（不要 Enable / 不要 `@notify.func`） |

## 禁止改的文件 / 符号

- `STNP_Notify_Send` / `SendBytes` / Python `stnp.notify`
- Job 入队 `STNP_Runtime_EnqueueNotify`（Notify 禁止在入队时 Router）
- Core weak `STNP_Notify_Callback` 与 Implementation 强符号 **都保留**
- `protocol.schema.json` 的 `notify_dispatch_receive` 字段
- 禁止新增 `STNP_Notify_CallbackEnable`

## 模板与测试落点

- `templates/c/Instance/stnp_instances.c.j2` — `STNP_Notify_Dispatch`
- `templates/c/Module/module/module.c.j2` / `module.h.j2` — `NotifyCallbackIsEnabled`
- `templates/c/Implementation/stnp_notify_callback.c.j2` — 文件头注释必须改为：已知码且模块 `IsEnabled` 则 **不进入** 本 fallback
- `templates/python/stnp/core/runtime.py.j2` — `_dispatch_notify`
- `src/stnp_editor/ir/models.py`、`src/stnp_editor/ir/builder.py` — 新符号
- 测试：`tests/test_generate_multi.py`::`test_notify_global_and_typed_callbacks_are_deferred_and_enable_semantics_hold`  
  **必须**与下列断言完全一致（禁止只改 enable 后半段）：  
  - 第一帧、未 Enable、`STNP_Dispatch` 之后：`g_raw_count==1 && g_typed_count==0`  
  - `Sensor_NotifyCallbackEnable(STNP_ENABLE)` 后再发一帧、`STNP_Dispatch` 之后：`g_raw_count==1 && g_typed_count==1 && g_value==0xBEEF`  
  禁止再断言 `raw==2`。该夹具依赖 regression 工程 DR 初值为开，禁止为此再插 `STNP_NotifyDispatchReceive_Enable`。  
  **禁止**把本 C 夹具的 enable-off 期望套到 Python（Python 无 `NotifyCallbackEnable`；有 typed `.func` 即认领）。
- 测试：`tests/test_generate_python.py`：DR **关闭** + 已注册 `@stnp.on_notify` 与 typed `.func` → 全局次数 0、typed 次数 0。DR 开再维持独占。
- golden：`stnp_instances.c`、各 `Module/*.c` / `*.h`、`runtime.py`（A 切片同步更新被改到的 golden）

现行文档改口列在 05，A 切片实现时改。
