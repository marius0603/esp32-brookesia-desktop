# USB JSON Lines 协议 v1

USB 使用 ESP32-S3 内置 USB Serial/JTAG，电脑端串口参数为 115200 8N1。物理 USB 链路不依赖波特率。每个消息为单行 UTF-8 JSON，以 LF 结束；额度包上限 2048 字节。固件日志输出到 UART0，避免混入 USB 协议。

设备上电后及每 5 秒发送身份帧：

~~~json
{"type":"hello","device":"codex-quota-monitor","v":1}
~~~

电脑只自动探测 VID=0x303A 的 Espressif 设备；接收到匹配的身份帧后才发送额度。其他 USB 转串口设备需要在 config.json 显式指定端口。蓝牙串口不会自动打开。

电脑到设备的额度帧：

~~~json
{"type":"quota","v":1,"sampled_at":1792286000,"sent_at":1792286001,"status":"ok","plan":"plus","bucket":"codex","windows":[{"kind":"primary","minutes":300,"used":25,"reset_at":1792304055},{"kind":"secondary","minutes":10080,"used":10,"reset_at":1792890855}],"stale_after":180,"warning":20,"critical":10,"device":"COM9"}
~~~

- used 是已用百分比；屏幕显示 100-used。允许小数，范围 0–100。
- sampled_at 是最后一次真实查询成功的 Unix 秒时间戳。查询失败时保留原值及 windows。
- sent_at 是发送时的电脑时间。固件用它与单调时钟推算当前时间，无需连接互联网。
- reset_at 可以为 null，表示未知。到期后显示“等待同步”，不推算新额度。
- windows 最多两项，允许仅有一个窗口或为空。空窗口不表示 0%。
- status 是 ok、starting、error 或 auth_required。
- 首次查询前 sampled_at 为 null，windows 为空。
- 超过 stale_after 未查询成功，界面标记过期；超过 8 秒未收到电脑帧，标记电脑未连接。
- 新帧每 2 秒发送，真实查询默认每 60 秒一次。这两个周期相互独立。
- 身份帧、额度帧均不包含账号邮箱、账号 ID、访问令牌或刷新令牌。

设备请求刷新：

~~~json
{"type":"refresh","v":1}
~~~

固件和电脑端均设置 15 秒刷新节流。固件对超长消息丢弃至下一个 LF，防止后半截误当成新帧。
