# STNP Editor

**版本：0.9.1 — Notify 独占与运行时诊断**

STNP Editor 以一份 `.stnp` 协议工程加一份 `stnp.build.json` 生成配置作为所选 **C** 或 **Python** 生成目标的单一事实来源，二者共享同一套 IR。这两个文件各自独立校验，互不引用。桌面 GUI 已移除；`stnpe` 命令行工具是唯一入口。

0.9.1 把 Notify 接收改为模块与全局独占，并加上默认关闭的未知帧回调、C `STNP_DEBUG` 与 Python `stnp.trace`。0.8.2 在保持现有 C 运行时与 SDK 行为的前提下，增加了可选的自动生成 Command 通知。Python 使用单一公开命名空间（`stnp.core`、`stnp.sdk.*`、`stnp.protocol`），将 Module 定义与可路由 Instance 分离，支持基于装饰器的命令实现与校验函数，将 TaskSet 批量合并为一次传输写入，并在两个操作系统线程上运行 RX/分发。

## 安装

```bash
# 从 GitHub 直接安装
python -m pip install "git+https://github.com/stal-ink/STNP_Editor.git"

# 钉住分支或提交
python -m pip install "git+https://github.com/stal-ink/STNP_Editor.git@main"
python -m pip install "git+https://github.com/stal-ink/STNP_Editor.git@<commit>"

# 源码开发（可编辑安装，含测试依赖）
git clone https://github.com/stal-ink/STNP_Editor.git
cd STNP_Editor
python -m pip install -e '.[dev]'
```

要求 `git` 在 PATH 上；私有仓库请用 `git+https://<token>@github.com/stal-ink/STNP_Editor.git`。

## Python 快速开始

```bash
stnpe generate examples/dual_multi_c_py/dual_multi.stnp examples/dual_multi_c_py/stnp.build.python.json -o _out
cd _out/dual_multi_STNP_Python
# emit_examples=false：自行编写 PC 端脚本；参见 examples/dual_multi_c_py/README.md
```

示例 API：

```python
import stnp
from stnp import Link, LinkMain, SensorFront, SensorRear

@Link.cmd.HANDSHAKE.func
def handshake(self, payload):
    ...

stnp.init()
stnp.task(
    LinkMain.task.HANDSHAKE(token=1),
    SensorFront.task.READ(),
    SensorRear.task.READ(),
)
stnp.notify.LinkMain.READY(Link.OK)
```

Python 配置有意拆分为三部分：生成的协议真值（`stnp/protocol/protocol.yaml`）、运行时设置（`config/stnp.yaml`）以及 SDK 设置（`stnp/sdk/uart/uart.yaml`）。示例生成与用户脚手架生成是彼此独立的可选开关。

## C 快速开始

```bash
stnpe generate examples/handshake_c/handshake.stnp examples/handshake_c/stnp.build.json -o _out
```

C 目标保留现有的 Platform/Core/Module/Instance/Implementation/SDK 布局、延迟的 Process/Dispatch 运行时、可选 HAL/FreeRTOS SDK，以及 USER CODE 合并行为。

## 测试

```bash
pytest -q
```

含 C/Python golden 对照。Windows 上带 `-pthread` 的并发夹具用 `-static` 链接（不再依赖 `libwinpthread-1.dll`）；`conftest.py` 会按统一解析器把解析到的 `gcc` / `cmake` 目录前置到 `PATH`，不写死盘符路径。工具链解析顺序与覆盖方式见 [快速开始](docs/01_getting_started.md)「环境准备」。

## 文档

- [文档索引](docs/README.md)
- [快速开始](docs/01_getting_started.md) · [协议格式](docs/02_protocol.md) · [JSON 与生成配置](docs/03_json_format.md)
- [C API](docs/04_api/c/README.md) · [Python API](docs/04_api/python/README.md)
- [架构](docs/05_architecture/README.md) · [指南](docs/06_guides/README.md)
- [迁移](docs/07_migration.md) · [变更记录](docs/08_changelog.md)
- [**未来计划（TODO）**](docs/09_future_plan.md)
