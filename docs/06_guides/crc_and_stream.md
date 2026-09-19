# CRC 与流式接收

本页说明如何开启 CRC，以及如何把 UART 碎片喂给运行时。协议槽位见 [协议格式](../02_protocol.md)。

## 开启 CRC

```json
"features": {
  "crc": {
    "enabled": true
  }
}
```

启用后，Task / Notify 帧尾部增加 2 字节 CRC16-Modbus（初值 `0xFFFF`、多项式 `0xA001`），覆盖 SOF 到 Payload 的 body，自身以 u16 小端追加。C 仅在此时生成 `Core/stnp_crc.h` 与 `stnp_crc.c`（`STNP_CRC16`）。Python 使用 `crc16_modbus()`。

0.9 没有运行期 CRC 开关：CRC 槽存在性只由 `features.crc.enabled` 在生成期决定，两端必须由同一份配置生成。关闭时尾部完全不存在该槽。

## Stream RX

不要假设一次 UART callback 正好对应一帧。将当前收到的 bytes 直接喂入。

C：

```c
STNP_Transport_Receive(data, length);
```

随后在非中断上下文调用 `STNP_Process()` 推进协议（单次至多一帧）；收到完整帧后再由 `STNP_Dispatch()` 执行业务。Receive 整块能放下才提交；放不下返回 `STNP_ERR_BUFFER`，不做部分写入。

Python：把 `transport.read()` 得到的 chunk 交给 `StreamParser.feed()`。一次 `feed` 可吐出多帧，SOF 猎寻与 C 一样 **每次只滑 1 字节**（不是一次丢掉整段前缀）。

Core 自动处理：

- 一帧拆成多次输入；
- 一次输入包含多帧；
- 帧前噪声（不是协议 SOF 则每次丢掉 1 字节）；
- Task / Notify 混合（只认两个协议 SOF，**没有**第三 SOF / log skip）；
- `LEN > max_payload`；
- CRC 错误后的重新同步。

结构或 CRC 错误使用 **1 字节滑动重同步**，不会按错误候选帧的推测长度整段丢弃，从而避免吞掉嵌套在错误候选中的后续有效帧。`LEN` 下标随 SEQ 开关变化（Task 为 4 或 6，Notify 为 6 或 8），解析器按 Capability 先算头长。详见冻结规范 §3.8 / §3.10。

未知帧用户回调默认关：须 `SetCallback` **并且** `Enable`（Python 为 `@stnp.on_unknown_frame` 再 `unknown_frame_callback_enable()`）。SOF 噪声另有第二开关，默认不上报。运行时不自动打印、不跳过「log 信封」。

---

[← 多实例](multi_instance.md) | [文档目录](../README.md) | [USER CODE →](user_code.md)
