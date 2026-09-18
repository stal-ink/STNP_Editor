# handshake_c —— 最小、可在 PC 上端到端运行的 C 示例

## 覆盖什么

- 一个 Module（`LINK`）、一个 Instance（`LinkPeer`）；
- `CONNECT_REQ` 使用 typed Payload，经统一 `STNP_Task_Send()` 发送，由 Core VTL 自动序列化；
- ACK / 握手完全由用户业务层实现，Core 不绑定 Task SEQ 与 Notify，也不保存握手状态：
  1. `Link_ConnectReq()` 收到请求后显式 `STNP_Notify_Send(CONNECT_ACCEPT)`；
  2. 用户 `Link_NotifyCallback()` 收到并解码 `CONNECT_ACCEPT` 后，显式发送 `CONNECT_CONFIRM` Task；
  3. `Link_ConnectConfirm()` 推进用户状态机到已连接。
- 生成的 `Examples/transport_mock.c` 把 TX frame 回环给 STNP，因此**不需要任何硬件**；
- 生成侧 `Implementation/link_impl.c` 里的 `Link_ConnectReq()` / `Link_ConnectConfirm()` 是 weak 兜底，
  链接前用 `objcopy --weaken-symbol` 降级，`handshake_user.c` 的同名强符号覆盖它们，
  `Link_ValidateGenerated()` 保持强符号。

## 生成

```bash
stnpe generate examples/handshake_c/handshake.stnp examples/handshake_c/stnp.build.json -o _out
# 源码运行时等价：python main.py generate examples/handshake_c/handshake.stnp examples/handshake_c/stnp.build.json -o _out
```

生成目录：`_out/handshake_STNP_C/`（`output_stem=handshake`，`build_system=mdk_arm`，`sdks=[]`，
`emit_examples=true`）。

## 在 PC 上怎么跑

```powershell
.\examples\handshake_c\run.ps1
```

脚本会：生成 → gcc 编译（含 objcopy 弱化）→ 运行 → 校验预期输出。
它用 `Get-Command` 查找 `python` / `gcc` / `objcopy`，找不到会给出提示并以非 0 退出。

等价的命令（Windows PowerShell 之外可自行翻译；生成目录记为 `_out/handshake_STNP_C`）：

```bash
gcc -std=c99 -Wall -Wextra -Werror -pedantic -I_out/handshake_STNP_C \
    -c _out/handshake_STNP_C/Implementation/link_impl.c -o _out/link_impl.o
objcopy --weaken-symbol=Link_ConnectReq --weaken-symbol=Link_ConnectConfirm _out/link_impl.o
gcc -std=c99 -Wall -Wextra -Werror -pedantic -I_out/handshake_STNP_C \
    _out/handshake_STNP_C/Core/*.c _out/handshake_STNP_C/Module/*.c _out/handshake_STNP_C/Module/*/*.c \
    _out/handshake_STNP_C/Instance/*.c _out/link_impl.o \
    _out/handshake_STNP_C/Implementation/stnp_notify_callback.c \
    _out/handshake_STNP_C/Examples/transport_mock.c examples/handshake_c/handshake_user.c \
    -o _out/handshake.exe
_out/handshake.exe
```

注意：生成的 `Examples/main.c` 不参与编译——本示例的 `main()` 在 `handshake_user.c` 中。

## 预期输出

```text
user handshake ok: token=4660
```

（token 取 `0x1234` = 4660；进程退出码 0。）

## 改哪里

`handshake_user.c` 是本示例唯一的用户实现文件：

- `Link_ConnectReq()`：收到 `CONNECT_REQ` 后决定接受/拒绝，并显式发送 `CONNECT_ACCEPT`；
- `Link_NotifyCallback()`：收到 `CONNECT_ACCEPT` 后发送 `CONNECT_CONFIRM`；
- `Link_ConnectConfirm()`：校验 token 并推进用户状态机；
- `main()`：初始化、注册校验回调、开启 Notify callback、发起第一次发送。

若要发送原始字节数组，可使用 `STNP_Task_SendBytes()` / `STNP_Notify_SendBytes()`。
