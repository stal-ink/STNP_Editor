# 1. 快速开始

本页给第一次使用者：两文件工程模型、安装、三条可复制命令、生成树怎么读，以及 `stnpe` 退出码。

## 两文件与 `stnpe`

0.9 起一个工程由两份文件组成，各自独立校验、互不引用：

- `<project>.stnp`：协议定义（Module / Instance / Protocol / `global_results`）。
- `stnp.build.json`：生成配置（单一 `target`、构建系统、SDK、输出布局、校验清单）。

命令名为 `stnpe`（不是历史名 `snpe`）。`generate` 与 `check` 都需要这两个文件参数：

```bash
stnpe generate <project.stnp> <stnp.build.json> -o <输出父目录> [-list]
stnpe check    <project.stnp> <stnp.build.json> --golden <golden 根>
stnpe version
```

- `-list` 只作用于 `generate`：逐文件打印 `[N/M] path`。不指定时只打印生成根目录。
- 最终工程文件夹名为 `{output_stem}_{layout.output_dir_names[target]}`，默认后缀 `STNP_C` / `STNP_Python`。
- 源码树内等价：`python main.py generate ...`。

字段细节见 [3. JSON 与生成配置](03_json_format.md)。从 0.9.0 迁过来见 [7. 迁移指南](07_migration.md) §7.0；从 0.8.x 迁过来见同页 §7.1。

## 环境准备

只使用 `stnpe` 时从 GitHub 安装：

```bash
python -m pip install "git+https://github.com/stal-ink/STNP_Editor.git"

# 钉住分支或提交
python -m pip install "git+https://github.com/stal-ink/STNP_Editor.git@main"
python -m pip install "git+https://github.com/stal-ink/STNP_Editor.git@<commit>"
```

在仓库根做开发（可编辑安装，含测试依赖）：

```bash
python -m pip install -e ".[dev]"
```

两者都要求 `git` 在 PATH 上；私有仓库用 `git+https://<token>@github.com/stal-ink/STNP_Editor.git`。

### 工具链解析顺序

仓库不捆绑编译器。`scripts/test.ps1`、`scripts/build_exe.ps1` 与 `examples/*/run.ps1` 共用同一套解析顺序（`scripts/toolchain.ps1` 与 `tests/_toolchain.py` 是同一顺序的两个实现，一致性由 `tests/test_toolchain.py` 锁定）：

1. **环境变量**（可选覆盖）：`STNP_PYTHON` / `STNP_MINGW_BIN` / `STNP_CMAKE_BIN` / `STNP_GIT` —— 值不可用时直接报错，不回退；
2. **`PATH` 查找**：取第一个命中并采用，同时列出其余全部候选；
3. **明确失败**：打印一行安装指引并非 0 退出。

解析器只做"按顺序查找 + 最低可用性校验 + 来源打印"：候选要能运行并通过最低检查（`gcc -dumpmachine` 可执行、`cmake --version` 可执行且不低于最低版本、python 版本符合 `requires-python` 且能 `import stnp_editor`），但**采用哪个工具、它是否适合你的目标平台，由你自行确认**。每次运行都打印实际使用的工具：`工具 : <路径> (from <来源>, <版本/三元组>)`。

`pytest` 由根 `conftest.py` 自举：把解析到的 gcc / cmake 目录前置到 `PATH`，并设置 `CMAKE_GENERATOR=MinGW Makefiles`；找不到就只报警告，不伪造路径，相关用例随之 skip 并被 `scripts/test.ps1 -FailOnSkip` 判为**非预期**。

### 工具链不在标准位置时

仓库内**不保存任何机器路径**。若你的编译器不在 `PATH` 上，做一次**用户级声明**（之后新开的 shell 都生效）：

```powershell
setx STNP_MINGW_BIN "<你的 MinGW-w64 bin 目录>"
setx STNP_CMAKE_BIN "<你的 CMake bin 目录>"
setx STNP_PYTHON    "<你的 Python 解释器路径>"
setx STNP_GIT       "<你的 git 可执行文件路径>"
```

也可只对当前会话生效：`$env:STNP_MINGW_BIN = "<...>"`。

**不声明会怎样**：`PATH` 上也没有时，解析器明确报错并打印安装指引（脚本非 0 退出；`pytest` 侧的相关用例 skip 会被 `-FailOnSkip` 判为非预期）。**不做任何静默回退。**

最小 C 示例还需要 `gcc` 与 `objcopy`（同样走上面的解析顺序；找不到会以非 0 退出并提示）。Python UART 路径另需发行包 `pyserial`（不是只 `import serial`）。

> 工具链由本机环境决定，软件不保证其正确或匹配；请自行确认。

## 最小 C 示例（`examples/handshake_c`）

覆盖：一个 Module `LINK`、一个 Instance `LinkPeer`；typed Payload 握手；mock transport 把 TX 帧回环给 STNP，因此不需要硬件。ACK / 握手完全由用户业务层实现：Core 不绑定 Task SEQ 与 Notify，也不保存握手状态。

```powershell
.\examples\handshake_c\run.ps1
```

脚本顺序：生成 → gcc 编译（含 `objcopy --weaken-symbol`）→ 运行 → 校验输出。生成侧 `Implementation/link_impl.c` 里的 `Link_ConnectReq` / `Link_ConnectConfirm` 是 weak 兜底；链接前用 `objcopy` 降级，由手写 `handshake_user.c` 的同名强符号覆盖。`Link_ValidateGenerated()` 保持强符号。生成的 `Examples/main.c` 不参与该示例编译——`main()` 在 `handshake_user.c`。

预期：

```text
user handshake ok: token=4660
```

（token 取 `0x1234` = 4660；进程退出码 0。）

单独生成：

```bash
stnpe generate examples/handshake_c/handshake.stnp examples/handshake_c/stnp.build.json -o _out
```

生成目录：`_out/handshake_STNP_C/`（该示例 `output_stem=handshake`，`build_system=mdk_arm`，`sdks=[]`，`emit_examples=true`）。

用户只需改 `handshake_user.c`：`Link_ConnectReq` 收到请求后显式 `STNP_Notify_Send(CONNECT_ACCEPT)`；`Link_NotifyCallback` 收到后发送 `CONNECT_CONFIRM` Task；`Link_ConnectConfirm` 校验 token 并推进状态机。

## Python 双端示例（`examples/dual_multi_c_py`）

一份 `.stnp`、两份 build：C 下位机（`stm32_hal_uart` + CMake）与 Python 上位机（`python_sdks=["uart"]`）。PC 上 `run.ps1` 只生成两端，不伪造串口运行。

```bash
stnpe generate examples/dual_multi_c_py/dual_multi.stnp examples/dual_multi_c_py/stnp.build.c.json -o _out/c
stnpe generate examples/dual_multi_c_py/dual_multi.stnp examples/dual_multi_c_py/stnp.build.python.json -o _out/python
```

或：

```powershell
.\examples\dual_multi_c_py\run.ps1
```

生成目录：`_out/c/dual_multi_STNP_C/` 与 `_out/python/dual_multi_STNP_Python/`。Python 侧完整签名见 [Python API](04_api/python/README.md)。联调步骤见 [Python 使用指南](06_guides/python_usage.md)。

第三个示例 `examples/stm32_hal_uart_c` 面向 CubeMX 集成，PC 上 `run.ps1` 只生成。见 [STM32 HAL UART 指南](06_guides/stm32_hal_uart.md)。

## C 生成树逐目录说明

以 C 期望产物（golden）`tests/golden/C/regression_c/regression_c_STNP_C/` 与模板 `src/stnp_editor/resources/templates/c/README.md.j2` 为准：

```text
<stem>_STNP_C/
├─ Core/                 帧、Task/Notify、Router、VTL、Process/Dispatch
├─ Platform/             类型、宏、工程配置（含 STNP_RX_RING_SIZE / STNP_JOB_QUEUE_DEPTH）
├─ Module/               每个 Module 的头/源与 VTL metadata
├─ Instance/             STNP_INSTANCE_*_ID 与 STNP_Instances_Init
├─ Implementation/       用户代码区：*_impl.c、stnp_notify_callback.c
├─ SDK/                  仅当 sdks 选中官方 SDK
├─ Examples/             仅当 c.emit_examples=true
├─ Embedded/             仅当 `.stnp` 含 `embedded_files`（不参与 USER CODE 合并）
├─ CMakeLists.txt        仅当 c.build_system=cmake
├─ .stnp-manifest.json   生成器清单（始终写出）
└─ README.md
```

`Implementation/*.c` 自动包含 `Instance/stnp_instances.h`。用户代码区三类标记（`Includes` / `Private` / 函数体）在重新生成时合并。`Examples/` 仅当 `c.emit_examples=true` 时出现。CMake 模式下 `Implementation` 源作为 `stnp` 的 `INTERFACE_SOURCES` 编进应用目标，不进入 `libstnp.a`，以便强符号覆盖 weak 兜底。

公共入口头 `Core/stnp.h` 再导出 Module/Instance 与已选 SDK。移植层可以只包含它。接收路径是 `STNP_Transport_Receive` → `STNP_Process` → `STNP_Dispatch`；发送走 `STNP_Task_Send` / `STNP_Notify_Send`。

## Python 生成树逐目录说明

以 Python 期望产物 `tests/golden/python/regression_py/regression_py_STNP_Python/` 为准：

```text
<stem>_STNP_Python/
├─ stnp/
│  ├─ core/              Runtime、帧、编解码、descriptor
│  ├─ sdk/uart/          仅当 python_sdks 含 uart
│  └─ protocol/          Module / Instance / Payload / Registry
├─ config/stnp.yaml      运行时用户配置
├─ Example/              仅当 python.emit_examples=true
├─ User/                 仅当 python.emit_user_scaffold=true（create-once）
├─ pyproject.toml        生成包元数据（始终写出）
├─ .stnp-manifest.json   生成器清单（始终写出）
└─ README.md
```

`stnp/protocol/` 是生成协议代码，不要手改；从 Editor 重新生成。业务实现用装饰器挂到任意会被 import 的 `.py`。协议 YAML、`config/stnp.yaml`、UART `uart.yaml` 三份配置不要混用。`User/` scaffold 只创建一次，重新生成永不覆盖。

## 退出码

定义于 `src/stnp_editor/errors.py`，由 CLI 映射：

| 码 | 符号 | 含义 |
|---:|---|---|
| 0 | `EXIT_OK` | 成功 |
| 1 | `EXIT_FAILURE` | 出现 E1/E2/E3/E4 段 error 级诊断，或 `check` 与 golden 不一致 |
| 2 | `EXIT_USAGE` | 命令行用法错误（argparse） |
| 3 | `EXIT_INTERNAL` | E9 段内部缺陷 |

诊断走 stderr，生成路径与 `-list` 走 stdout。详见 [生成器架构](05_architecture/generator.md)。

## 下一步

- 协议槽位：[2. 协议格式](02_protocol.md)
- C 集成：[C API](04_api/c/README.md)
- Python 集成：[Python API](04_api/python/README.md) 与 [Python 使用指南](06_guides/python_usage.md)
- 从 0.8.2 迁过来：[7. 迁移指南](07_migration.md)

---

[← 文档目录](README.md) | [文档目录](README.md) | [协议格式 →](02_protocol.md)
