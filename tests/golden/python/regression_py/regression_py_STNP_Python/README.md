# regression_py — STNP Python

由 **STNP Editor 0.9.0** 生成。`stnp/protocol/` 树是生成的协议代码；需要修改时请从 Editor 重新生成，不要手工编辑。

## 快速使用

```python
import stnp
from stnp import *

stnp.init()  # UART SDK uses stnp/sdk/uart/uart.yaml when generated.
```

Task 构建与批量发送：

```python
items = []
# Instance.task.COMMAND(...) builds a TaskSpec without sending it.
# stnp.task(item1, item2, ...) sends the whole task set with one transport write.
```

也可直接使用生成的即时路由 `stnp.task.<Instance>.<Command>(...)`。

命令实现通过装饰器注册，例如 `@Module.cmd.COMMAND.func`；Instance 级覆盖使用 `@Instance.cmd.COMMAND.func`。

配置有意分离：

- `stnp/protocol/protocol.yaml`：Editor 生成的协议事实源；不要用于运行时调参。
- `config/stnp.yaml`：用户运行时设置。
- `stnp/sdk/uart/uart.yaml`：用户 UART/pyserial 设置。
在本目录运行生成的教程：`python Example/main.py`。
