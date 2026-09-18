# 5. 架构说明

本页给需要理解生成器与运行时分层的维护者：从两份输入文件到生成树的数据流，以及 C / Python 运行时为何如此切分。

## 端到端数据流

```text
.stnp + stnp.build.json
        ↓
JSON Schema（结构、required、additionalProperties: false）
        ↓
IR builder 语义校验 → ProjectIR
        ↓
按 build.target 单目标分派（c / python）
        ↓
target emitter（模板 + USER CODE merge + manifest）
        ↓
生成树（C：Platform/Core/Module/Instance/Implementation；
        Python：stnp.core / stnp.sdk / stnp.protocol）
```

冻结规范规定分层模型与 wire 槽位，见 [spec_0.9.md](spec_0.9.md)。

## 核心原则

- **单一事实源**：`.stnp` 只描述协议；`stnp.build.json` 只描述生成配置。
- **Schema / IR 分工**：schema 管结构；IR builder 管跨字段语义与 C 符号冲突。
- **VTL 只在 Core**：Module 只生成 typed Payload metadata，不生成 per-command Pack 函数。
- **用户代码分离**：C 写在 `Implementation/` 用户代码区；Python 用装饰器挂到任意用户文件。
- **执行模型不同、wire 相同**：C 是延迟 Process/Dispatch；Python 是调用线程 TX + RX/Dispatch 双线程。帧槽位由同一份 `.stnp` 生成。

## 章节索引

| 文档 | 内容 |
|---|---|
| [冻结规范 spec_0.9.md](spec_0.9.md) | STNP 0.9 权威目标态（规范正文不改写） |
| [生成器 generator.md](generator.md) | Schema/IR、单目标分派、安全写出、诊断与退出码 |
| [C 运行时 c_runtime.md](c_runtime.md) | Transport → Process → Dispatch；裸机与 FreeRTOS |
| [Python 运行时 python_runtime.md](python_runtime.md) | 双线程、TaskSet、校验顺序、异常隔离 |

---

[← API](../04_api/README.md) | [文档目录](../README.md) | [生成器 →](generator.md)
