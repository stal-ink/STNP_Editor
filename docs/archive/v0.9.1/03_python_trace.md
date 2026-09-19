# 03 Python Trace

Python 本端观察面只有一棵树：`stnp.trace`。下面两支，都不是日志系统。禁止在文档、符号、yaml 键里使用「日志」作为产品名。

```text
stnp.trace
  ├─ debug     关键路径打点：链路有没有走到     ← 切片 C
  └─ format    业务帧语义化：这条 MOVE / DATA 字段是什么  ← 切片 D
```

C 没有终端，对应的只是 [04 断点宏](04_c断点宏.md)，不做 format。  
C 诊断信封 / `STNP_LOGx` **禁止做**。

旁路、只读、默认关。format **不是** Notify 认领者，禁止改变 [01 独占](01_notify独占分发.md)。

新文件：`templates/python/stnp/core/trace.py.j2`、`templates/python/config/trace.yaml.j2`。  
生成路径：`stnp/core/trace.py`、`config/trace.yaml`。

默认全部关闭，现有测试在 emitter 尚未接入这些文件前行为不变。一旦 emitter 接入，必须同步 golden（见 05）。

---

## 0. 模块边界（硬规则）

- 实现放在 `stnp/core/trace.py`。
- `stnp/core/runtime.py.j2` **必须**写这一行，禁止改名、禁止拆开、禁止「或等价」：

```python
from .trace import debug as trace_debug, format as trace_format
```

  调用 **必须**是 `trace_debug.bp(...)` 与 `trace_format.maybe(...)`。切片 C 即使尚未调用 `maybe`，**禁止**删掉 `format as trace_format` 这一半。**禁止** `import stnp`（会与包入口循环导入）。
- `stnp/core/__init__.py.j2` 必须 `from . import trace` 并导出 `trace`。
- `stnp/__init__.py.j2` 必须 `from .core import trace`，使 `stnp.trace.debug` / `stnp.trace.format` 成立。禁止再导出 `stnp.debug` / `stnp.log`。
- `trace.py` **禁止**导入 `runtime`。

切片 C **必须**实现：`debug`、各 `bp` 站点、`TraceCmd`、模块级 `format = Format()`（含 `should`/`maybe`/`__call__`）、`configure()`、`load()`（找不到文件则保持默认）。`format.enabled` 默认 `False`。这样 `from .trace import debug as trace_debug, format as trace_format` **禁止** `ImportError`。

切片 D **必须**：把 `trace_format.maybe` 插入 runtime、生成 `config/trace.yaml`、payload `to_display()`、`stnp.init()` 调用 `trace.load()`。**禁止**把 `trace.py` 推迟到 D 才加入 emitter。

切片 C **允许** `stnp.init()` 暂不调用 `load()`。`stnp.init()` **必须**从切片 D 开始调用 `trace.load()`（无参，走查找链）。D 之前打开 `debug.enabled` **必须**只通过 `stnp.trace.configure()` 或直接写 `stnp.trace.debug.enabled`。**禁止**在 C 的 `init()` 里读 `trace.yaml`。

---

## 1. `trace.debug`：验证链路（切片 C）

与 C `STNP_BP_*` 同一意图。Python 没有预编译宏，用运行时开关（默认关）。

```python
stnp.trace.debug.enabled = False   # 默认
stnp.trace.debug.trap = None       # Callable[[str], None] | None

def bp(site: str) -> None:
    if stnp.trace.debug.enabled and stnp.trace.debug.trap is not None:
        stnp.trace.debug.trap(site)
```

`enabled` 也可由 `trace.yaml` 的 `trace.debug.enabled` 在 `stnp.init()` → `trace.load()` 时写入（**仅切片 D 开始**；C 禁止走这条）。

**禁止**默认 `breakpoint()`。测试赋值 `trap` 做计数。联调可自己：

```python
stnp.trace.debug.enabled = True
stnp.trace.debug.trap = print
```

`trap is None` 时 `bp` 必须是空操作，即使 `enabled is True`。

### 站点（对照 `python_runtime.md`；插入用函数名）

| site | 位置（必须） |
|---|---|
| `rx_read` | `_rx_loop`：`transport.read` 得到非空 `chunk` 之后、`parser.feed` 之前 |
| `parse_ok` | `_rx_loop`：对 `feed` 产出的每个 `TaskFrame`/`NotifyFrame`，在 `rx_frames++` 之前 |
| `parse_resync` | 见下 |
| `enqueue` | `Dispatcher.put` 返回 `True` 之后（失败走现有 `dropped_frames`，禁止打 `enqueue`） |
| `dispatch` | `_dispatch_task` 与 `_dispatch_notify` **入口第一句** |
| `on_task` | `_dispatch_task`：即将调用 CMD `.func` 之前（`fn is None` 则禁止打） |
| `on_notify` | `_dispatch_notify`：即将调用 **实际走的那条**（模块 `.func` 或全局 fallback）之前；独占后禁止两条都打；无人认领（连全局都没有）禁止打 |
| `seq_reserve` | `_next_seq`：取出当前 seq、即将返回之前 |
| `transport_write` | `_write_many`：调用 `transport.write` **之前**（已持有 `_write_lock`） |

与 format 正交：debug 开了只报站点名，禁止打印 payload。format 开了只打字段，禁止报站点。

### `parse_resync`

含义：LEN/CRC 类失步。**禁止**对每字节 SOF 猎寻打点。**禁止** C 路径与 B 路径叠加。

- **切片 C（B 尚未落地）必须**用计数器增量，对本轮 `feed()` **恰好一次**（不是每个错误字节一次）：

```python
crc_before = parser.crc_errors
proto_before = parser.protocol_errors
frames = parser.feed(chunk)
# ... 现有 stats 累加 ...
if (parser.crc_errors - crc_before) + (parser.protocol_errors - proto_before) > 0:
    trace_debug.bp("parse_resync")   # 本轮 feed 一次
```

  **禁止**用累计 `parser.crc_errors > 0 or parser.protocol_errors > 0`（第一次出错后，后续干净 feed 会误打）。**禁止**按 buffer 字节循环打。

- **切片 B 必须**删除上面的计数器路径，改为：对每个 `ParseError` 且 `reason in ("len", "crc")` 打一次 `parse_resync`。SOF `ParseError` **禁止**打 `parse_resync`。B 落地后 **禁止**再保留 C 的增量路径（会加倍）。

### 输出示例

```python
hits = []
stnp.trace.debug.enabled = True
stnp.trace.debug.trap = hits.append
# 收一帧合法 MOVE
# hits == ["rx_read", "parse_ok", "enqueue", "dispatch", "on_task"]
```

CRC 错一帧：含 `rx_read`、`parse_resync`；无 `parse_ok` / `on_task`。

---

## 2. `trace.format`：语义化字段（切片 D）

挂在 Dispatch 上。依赖切片 A 的 Notify 独占路径：只对 **实际走的那条** 打一次。

0.9.0 `_dispatch_task`（`runtime.py.j2` 约 L222–247）：

```text
decode -> validate（失败直接 return）-> 检查 fn is None -> func
```

0.9.1 Task **必须**是：

```text
decode -> validate（失败：禁止 format，禁止 func）-> format.maybe -> 若 fn is None：warning 并 return；否则 func
```

`format.maybe` **必须**在 `fn is None` 检查 **之前**。无 `.func` 仍必须能 format（看见对端在打、本地还没实现）。

Notify 无 validate。模块认领路径：`decode -> format.maybe -> debug.bp("on_notify") -> func -> return`。  
全局 fallback：**必须**调用 `format.maybe`（在 `debug.bp("on_notify")` 与 `_notify_callback` 之前）。是否输出由 `maybe` 内部 `should()` 决定。**禁止**调用方先判断 `should()` 再决定是否 maybe。  
无人认领（连全局都没有）：**禁止** format，**禁止** `on_notify` 打点。

`payload is None`（无 payload 字段的 Notify）：`format.maybe` **必须**仍调用。**禁止**因 payload 为 None 跳过 maybe。`default_format` **必须**省略字段段。

validate 失败：不 format、不 func。format 或 sink 抛错：隔离后 **仍必须** func。

### 配置

`config/trace.yaml`，**禁止**塞进 `stnp.yaml`。禁止配置 logging handler。

```yaml
# config/trace.yaml
trace:
  debug:
    enabled: false
  format:
    enabled: false
    commands: []          # MODULE.COMMAND
    notifications: []     # MODULE.NOTIFY
```

| `format.enabled` | 列表 | 行为 |
|---|---|---|
| `true` | 忽略 | 全部走到 `maybe` 的 Task / Notify 都 format（**含**全局 fallback；无人认领除外） |
| `false` | 非空 | 只打列表内 path |
| `false` | 空 | 全不打 |

查找顺序（`stnp.init()` 加载一次；先命中先用，不再继续）：

1. 显式 `stnp.trace.load(path)`
2. 环境变量 `STNP_TRACE_CONFIG`
3. cwd `config/trace.yaml`
4. 生成包旁 `config/trace.yaml`（与 `stnp.yaml` 相同的包旁规则：`Path(stnp.__file__).resolve().parents[1] / "config" / "trace.yaml"`）
5. 内存默认全关

`stnp.trace.load(path: str | Path | None = None)` **必须**仍按上面 1–5 加载 yaml（`path is None` 从步骤 2 起搜）。**禁止**用 `configure` 代替 `load` 读文件。

### `configure`（测试用，必须在切片 C 的 `trace.py` 就存在）

```python
def configure(*, debug_enabled=None, format_enabled=None, commands=None,
              notifications=None, sink=None, trap=None) -> None:
    ...
```

关键字参数 **必须**恰好这 6 个。任一参数为 `None` **必须**保持该字段现值（**禁止**当成「关闭」）。

| 参数 | `None` | 非 `None` |
|---|---|---|
| `debug_enabled` | 不动 `debug.enabled` | `debug.enabled = bool(...)` |
| `format_enabled` | 不动 `format.enabled` | `format.enabled = bool(...)` |
| `commands` | 不动 `format.commands` | `format.commands = set(commands)`（`[]` 就是空集） |
| `notifications` | 不动 `format.notifications` | `format.notifications = set(notifications)` |
| `sink` | 不动 `format.sink` | `format.sink = sink` |
| `trap` | 不动 `debug.trap` | `debug.trap = trap` |

把 `sink` / `trap` 清成 `None` **必须**直接写属性（`stnp.trace.format.sink = None`）。`configure(sink=None)` **必须**保持原 sink。

path 格式 `MODULE.NAME`（与 `.stnp` 模块名 + CMD/NOTIFY 名一致，如 `CHASSIS.MOVE`、`SENSOR.DATA`）。名单里的未知名字：加载时 `logging.getLogger("stnp.trace").warning`，**禁止**抛。

### 装饰器：只改字，不代替 yaml 总开关

`@stnp.trace.format("CHASSIS.MOVE")` **只登记** `path → (cmd, payload) -> str`。  
**禁止**自动写入 yaml 列表，禁止把该 path 加进 `commands`/`notifications`。  
要看见这条，仍然需要 `format.enabled is True`，或对应名单含该 path。

同一 path 后登记覆盖先登记。返回 `None` / `""`：这次禁止输出（禁止调用 sink）。

装饰器必须是 `Format.__call__(self, path: str)`，这样 `@stnp.trace.format("CHASSIS.MOVE")` 才能作用在 **实例** `format` 上。禁止再提供会与实例名冲突的 `.format()` 方法。

```python
@stnp.trace.format("CHASSIS.MOVE")
def fmt_move(cmd, payload):
    return f"MOVE {payload.direction} {payload.speed}"
```

### 默认字与 `to_display()`

`templates/python/stnp/protocol/payloads/module.py.j2`：每个生成的 payload dataclass **必须**有 `to_display(self) -> str`。字段顺序与 `.stnp` / 生成字段声明顺序相同，格式 `name=value`，空格分隔。无 payload 则默认行省略字段段。

无自定义 override 时：

```text
STNP TASK ChassisMain CHASSIS.MOVE direction=1 speed=40
STNP NOTIFY SensorFront SENSOR.DATA result=OK value=1234 status=0
```

`TraceCmd` **必须**是：

```python
@dataclass(frozen=True, slots=True)
class TraceCmd:
    kind: str                 # "task" | "notify"
    path: str                 # MODULE.NAME
    owner: str                # instance.name；未知 SOURCE 时见下
    instance: object          # InstanceDefinition | None
    descriptor: object        # CommandDescriptor | NotificationDescriptor | None
    result: object = None     # Notify：已映射的 module result；Task 保持默认 None
```

**禁止** `NamedTuple`。字段 **必须**恰好这 6 个，顺序同上，`result` **必须**默认 `None`。

### `default_format(cmd, payload) -> str`

**必须**拼出 §2 默认行，规则：

1. 前缀：`STNP TASK {owner} {path}` 或 `STNP NOTIFY {owner} {path}`。
2. `cmd.kind == "notify"` 且 `cmd.result is not None`：追加 `result={name}`。`name` **必须**是 `cmd.result.name`（IntEnum）；不是 IntEnum 时用 `str(cmd.result)`。`result is None` **必须**省略 result 段。
3. `payload is None`：**必须**省略字段段（仍然输出前缀 ± result）。
4. `isinstance(payload, (bytes, bytearray))`：字段段 **必须**是 `bytes(payload).hex()`（小写、无分隔、无 `0x`）。长度为 0 则省略字段段。
5. 否则：字段段 **必须**是 `payload.to_display()`；返回 `""` 则省略字段段。
6. 各段空格分隔。

### 认领 Notify 的构造（typed 路径）

```python
cmd = TraceCmd(
    kind="notify",
    path=f"{instance.module.name}.{notification.name}",
    owner=instance.name,
    instance=instance,
    descriptor=notification,
    result=result,   # instance.module.result(frame.result)
)
trace_format.maybe(cmd, payload)   # decode 后的 dataclass，或无 payload 字段时 None
```

### 全局 fallback Notify 的构造

`format.maybe` **必须**仍调用（`should()` 为假则 maybe 内部直接 return）。

```python
if instance is not None and notification is not None:
    path = f"{instance.module.name}.{notification.name}"
elif instance is not None:
    path = f"{instance.module.name}.0x{frame.notify_code:02X}"
else:
    path = f"0x{frame.notify_code:02X}"
cmd = TraceCmd(
    kind="notify",
    path=path,
    owner=(instance.name if instance is not None else f"0x{frame.source:02X}"),
    instance=instance,          # 未知 SOURCE 时 None
    descriptor=None,            # 全局路径必须 None
    result=(instance.module.result(frame.result) if instance is not None else None),
)
trace_format.maybe(cmd, frame.payload)   # bytes（可长 0）；禁止改写成 dataclass
```

`frame.payload` **必须**原样传入（`bytes`）。`default_format` 按上面第 4 条 hex。

### 出口

format 得到非空字符串后交给 **可替换 sink**，默认 `print`。不是 logging 层。

```python
stnp.trace.format.sink = print          # 默认
stnp.trace.format.sink = my_write       # 测试换成 list.append
```

`sink is None`：`maybe` 必须直接返回（禁止调用）。  
`should()` 为假：禁止调用 override、禁止调用 sink。

异常：override 或 sink 内隔离。失败时允许 `sink("STNP TRACE format failed: {path}")` 一次；若这次 sink 再抛，吞掉。然后业务 `func` 必须仍执行。

### Dispatch 插入（Task，D）

`_dispatch_task` 在 validate 通过之后、`fn is None` 检查之前：

```python
cmd = TraceCmd(kind="task", path=f"{instance.module.name}.{command.name}",
               owner=instance.name, instance=instance, descriptor=command)
trace_format.maybe(cmd, payload)
fn = command._func.resolve(instance.id)
if fn is None:
    LOG.warning("received unimplemented command %s.%s on %s", instance.module.name, command.name, instance.name)
    return
```

warning 文本 **必须**保持 0.9.0 `runtime.py.j2` 这一行，禁止改字、禁止改成 f-string。

Notify 模块认领路径（A 已 `return` 之前）：decode 成功后、调用 typed fn 前，按「认领 Notify 的构造」`maybe` 一次，然后 `trace_debug.bp("on_notify")`。

Notify 全局 fallback：按「全局 fallback Notify 的构造」`maybe` 一次，然后 `trace_debug.bp("on_notify")`，再调 `_notify_callback`。**禁止**跳过 maybe。

无人认领：**禁止** maybe，**禁止** `bp("on_notify")`。

---

## 3. 代码形状（`stnp/core/trace.py`）

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class TraceCmd:
    kind: str
    path: str
    owner: str
    instance: object
    descriptor: object
    result: object = None

class Debug:
    enabled = False
    trap = None
    def bp(self, site: str) -> None:
        if self.enabled and self.trap is not None:
            self.trap(site)

class Format:
    enabled = False
    commands: set[str] = set()
    notifications: set[str] = set()
    overrides: dict = {}
    sink = print

    def __call__(self, path: str):
        def deco(fn):
            self.overrides[path] = fn
            return fn
        return deco

    def should(self, cmd) -> bool:
        if self.enabled:
            return True
        if cmd.kind == "notify":
            return cmd.path in self.notifications
        return cmd.path in self.commands

    def maybe(self, cmd, payload) -> None:
        if not self.should(cmd):
            return
        if self.sink is None:
            return
        fn = self.overrides.get(cmd.path, default_format)
        try:
            text = fn(cmd, payload)
            if text:
                self.sink(text)
        except Exception:
            try:
                self.sink(f"STNP TRACE format failed: {cmd.path}")
            except Exception:
                pass

debug = Debug()
format = Format()

def configure(*, debug_enabled=None, format_enabled=None, commands=None,
              notifications=None, sink=None, trap=None) -> None:
    if debug_enabled is not None:
        debug.enabled = bool(debug_enabled)
    if format_enabled is not None:
        format.enabled = bool(format_enabled)
    if commands is not None:
        format.commands = set(commands)
    if notifications is not None:
        format.notifications = set(notifications)
    if sink is not None:
        format.sink = sink
    if trap is not None:
        debug.trap = trap
```

`default_format` **必须**实现 §2 的默认行（含 bytes hex、payload None 省略字段段）。`load` / `configure` 写在同一模块，经 `stnp.trace.load` / `stnp.trace.configure` 暴露。`load` 在 C 就必须定义（找不到文件则保持默认）；`stnp.init()` 从 D 才调用。

切片 C 的 `trace.py` **必须**含 `debug`、`format`、`TraceCmd`、`configure`（及 `Format.should`/`maybe`）。**禁止** C 只导出 `Debug` 而让 D 再补 `format` 对象。

---

## 4. 输出示例

### debug 开、format 关

```text
parse_ok
dispatch
on_task
# 无 STNP TASK 行
```

### format 全开（`enabled: true`）

```text
STNP TASK ChassisMain CHASSIS.MOVE direction=1 speed=40
STNP TASK MotorLeft MOTOR.SET_SPEED rpm=1200
STNP NOTIFY SensorFront SENSOR.DATA result=OK value=1234 status=0
```

### 只名单

```yaml
trace:
  format:
    enabled: false
    commands: [CHASSIS.MOVE]
```

```text
STNP TASK ChassisMain CHASSIS.MOVE direction=1 speed=40
```

只挂装饰器、名单为空且 `enabled: false`：**无输出**（装饰器不打开 path）。

### 自定义 format

名单含 MOVE 或 `enabled: true`：

```text
MOVE 1 40
```

### validate 失败

无 format 行，func 不跑。

### 独占 Notify

模块认领后只打一条 format，全局 `on_notify` 不跑，也不会第二条 format。

### 全局 fallback Notify（format.enabled true）

`descriptor is None`，payload 为 raw bytes 时默认行字段段为 hex，例如：

```text
STNP NOTIFY SensorFront SENSOR.DATA result=OK d204
```

无 payload 字段（认领路径 `payload is None`）：

```text
STNP NOTIFY SensorFront SENSOR.DATA result=OK
```

未知 SOURCE：`owner` 为 `0x09` 这种 `0x{source:02X}`，无 result 段。

---

## 5. 约束

| 项 | 规则 |
|---|---|
| 默认 | debug / format 都关 |
| debug | 只报 site 字符串，不碰 payload |
| format | 只读 cmd/payload，不改路由 |
| 装饰器 | 只覆盖格式，不改 yaml、不加名单 |
| 上下文 | Dispatch / 架构站点；不在 RX IRQ |
| 对功能 | format 异常不影响 func |
| 对资源 | 不占码表、SEQ、schema；不上 Transport |
| 与 C | 本端不上线；C 只有断点宏 |

## 6. 测试要点

1. 默认：sink / trap 次数为 0。现有无 trace 配置的测试 stdout 与 0.9.0 一致（除 A 造成的独占语义）。
2. debug 开：合法 Task 站点序列为 `rx_read, parse_ok, enqueue, dispatch, on_task`。
3. format `enabled: true`：每条 typed 一帧一行。
4. 名单只含 MOVE：其它 0 行。
5. 仅装饰器、未开 yaml：0 行。
6. validate 非 OK：format 0，func 0。
7. format 抛错：func 仍 1。
8. 模块认领 Notify：format 1，全局 0。
9. `to_display()` 在生成 dataclass 上，字段顺序同 schema。
10. `runtime.py` 源码 **必须**含 `from .trace import debug as trace_debug, format as trace_format`，禁止含 `import stnp`。
11. `configure(debug_enabled=True)` 打开 debug；随后 `configure(debug_enabled=None)` **必须**保持 True。`configure(commands=[])` **必须**把名单清空（与 `None` 不同）。
12. 全局 fallback：`format.enabled is True` 时 sink 1 次；`default_format` 对 `bytes` payload 输出 hex 字段段。
13. 认领路径 `payload is None`：maybe 仍 1 次，默认行无字段段。
14. 切片 C：一轮 `feed` 若 crc/protocol 计数增加，`parse_resync` 恰好 1 次，不是每个错误字节一次。切片 B 后改为每个 `len`/`crc` ParseError 一次，禁止与计数器路径叠加。

## 7. 明确禁止

- 不叫日志，不用 logging 作为产品层（测试可把 sink 换成 list；配置加载 warning 除外）。
- 不在 descriptor 上加 `.display()`。
- 不上 `STNP_Transport_Write`。
- 不在 C 做 yaml trace / format。
- 不把 `trace.debug` 做成 LOG 等级。
