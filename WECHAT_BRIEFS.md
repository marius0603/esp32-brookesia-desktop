# 工作完成后的微信简报

用户授权每完成一项功能或App、验证并同步GitHub后，向本人绑定的微信发送一条中文简报：完成内容、验证结论、待确认事项和提交链接。普通问答与中间日志不逐条推送。

使用腾讯官方`@tencent-weixin/openclaw-weixin`插件和本机OpenClaw，通过直接消息发送，无需另一次模型调用。电脑需联网；登录失效或微信拒收时仍可能失败，不保证永久绑定或无限量发送。不得自动购买套餐。

本机升级采用独立Node.js/OpenClaw目录，旧配置已备份，账号凭证留在用户OpenClaw目录。默认私有配置在仓库外`../private/openclaw-binding/brief-config.json`：`node`、`cli`为绝对执行路径，`channel`为`openclaw-weixin`，`account`和`target`为已扫码绑定的账号/接收者。这些值及二维码、日志、发送账本均不得提交。另一台电脑需自行安装、绑定并配置，不能只克隆仓库即获得微信授权。

正文先写到本地runtime文件，避免命令行转义损坏。示例（项目根目录）：

```powershell
python tools/wechat_brief.py --body-file codex-quota-monitor/runtime/work-brief.txt --id <已推送的完整提交SHA> --dry-run
python tools/wechat_brief.py --body-file codex-quota-monitor/runtime/work-brief.txt --id <已推送的完整提交SHA>
```

工具必须读取平台`payload.deliveryStatus=sent`才确认成功，不能仅凭CLI退出码。相同工作ID不会自动重发；请求前先记录未确认状态，超时或进程中断时避免重复发送，应先现场检查微信再决定是否用新的ID重发。发送状态本地保存，不保存正文，不自动重试。

2026-11-16本机验证：扫码凭证保存、微信通道运行，用户发送“测试”后收到直接测试回复。初次尚无会话上下文时发送被拒绝；不将绑定成功等同所有情况下均可主动推送。OpenClaw默认模型未登录曾返回AI服务错误，直接发送工具不依赖此模型；Codex双向对话桥接尚未配置，微信尚不能直接控制当前Codex桌面对话。

官方流程：https://github.com/Tencent/openclaw-weixin
