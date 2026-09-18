# STNP 0.9 文档目录

本文档集是 STNP Editor 0.9.0 的唯一中文索引：给第一次使用者、集成移植者与维护生成器的人，按章节阅读现行协议、API、架构与指南。

## 适用版本与状态

- 适用版本：**STNP Editor 0.9.0**。
- 冻结规范正文见 [5. 架构说明 / spec_0.9.md](05_architecture/spec_0.9.md)；本目录其余非 `archive/` 页面按该规范与当前生成物撰写。
- `archive/` 只作历史追溯，其中旧设计可能与现行行为冲突，不能当作开发接口依据。

## 阅读目录

| 章节 | 文档 | 用途 |
|---|---|---|
| 1 | [快速开始](01_getting_started.md) | 两文件模型、`stnpe`、可复制命令与生成树 |
| 2 | [协议格式](02_protocol.md) | Task / Notify 的 wire 槽位、SEQ、CRC、Stream |
| 3 | [JSON 与生成配置](03_json_format.md) | `.stnp` 与 `stnp.build.json` 字段参考 |
| 4 | [API](04_api/README.md) | C 与 Python 生成 API |
| 5 | [架构说明](05_architecture/README.md) | 生成器、C/Python 运行时与冻结规范 |
| 6 | [使用指南](06_guides/README.md) | 集成、联调、USER CODE、SDK、构建系统 |
| 7 | [迁移指南](07_migration.md) | 0.8.2 → 0.9 破坏性迁移与历史记录 |
| 8 | [变更记录](08_changelog.md) | 版本变更 |
| 附录 | [归档登记表](archive/README.md) | 历史资料登记；正文只追溯、不作为现行依据 |

## 阅读路径

### 首次使用

1. [快速开始](01_getting_started.md)
2. 需要协议细节时读 [协议格式](02_protocol.md)
3. 按语言进入 [C API](04_api/c/README.md) 或 [Python API](04_api/python/README.md)
4. 动手联调时打开 [使用指南](06_guides/README.md)

### 集成移植

1. [JSON 与生成配置](03_json_format.md)
2. [C API](04_api/c/README.md) 与 [STM32 HAL UART](06_guides/stm32_hal_uart.md) / [FreeRTOS](06_guides/freertos.md)
3. [构建系统](06_guides/build_systems.md)、[USER CODE](06_guides/user_code.md)
4. 运行时分层见 [C 运行时架构](05_architecture/c_runtime.md)

### 维护生成器

1. [冻结规范](05_architecture/spec_0.9.md)
2. [生成器架构](05_architecture/generator.md)
3. [迁移指南](07_migration.md) 与 [变更记录](08_changelog.md)
4. 过程资料仅在 [归档](archive/README.md) 中追溯

## 文档规则

- 非 `archive/` 的目录与文件名使用小写加下划线；章节文件带 `01_`…`08_` 前缀。目录索引固定为 `README.md`。
- 正文为中文；标识符、API 名、JSON 字段名、文件名、命令名保留英文。
- 相对链接指向本仓库现存文件；禁止为修链而恢复已删除的历史文档。
- `archive/` 正文不改写，只通过本页与 [归档登记表](archive/README.md) 导航。

## 术语

首次出现时中文后可括注英文。全篇统一如下：

| 英文 | 统一用法 |
|---|---|
| generator | 生成器 |
| instance | 实例（Instance） |
| module | 模块（Module） |
| task | 任务（Task） |
| notify / notification | 通知（Notify） |
| dispatch | 分发 |
| validation / validate | 校验（校验函数） |
| golden | 期望产物（golden） |
| fixture | 回归夹具（fixture） |
| frozen spec | 冻结规范 |
| USER CODE | 用户代码区 |
| transport | 传输层（Transport） |
| frame | 帧（Frame） |
| global result | 工程级结果码（Global Result） |
| build config | 生成配置（`stnp.build.json`） |

---

[下一章：快速开始 →](01_getting_started.md)
