# OpenClaw登录启动包装器

`GatewayProxyWrapper.cs`为当前Windows开发电脑保存的可重建源码，不含微信凭证。它使用已有Node/OpenClaw，设置代理后运行传入的Gateway参数、转发标准输出与错误，并把子进程退出码交给OpenClaw服务管理器。

Windows监督器要求直接父进程为CMD。包装器因此通过系统`cmd.exe /d /s /c`启动Node，并将`OPENCLAW_WINDOWS_TASK_HIDDEN_LAUNCHER`设为`cmd`，让原有监督器继续核对真实CMD身份与生命周期，不删除或跳过验证。直接由EXE启动Node的旧版在真实电脑重启后报`Windows task supervisor lost its original CMD launcher`，已由本版修正。

由于使用CMD，包装器仅接受服务开关所需的安全字符，空白、引号、百分号和shell连接符均在启动前拒绝。`tests/test_gateway_wrapper.py`实际编译EXE，验证这些边界和通过CMD执行版本查询；另外必须从真正的Windows启动项验证网关监听、父进程链及微信回复，版本查询成功不等于自启动通过。

当前源码中的D盘路径、Node版本和7890代理属于本机部署参数。另一台电脑先核对并修改这些值，完成OpenClaw与官方插件安装/扫码，再编译注册；不要复制本机账号文件。需保留已有配置备份，若已有网关，先用官方服务命令检查其归属和运行状态，不删除锁文件或结束其他Codex进程。

本机编译命令（PowerShell，Windows .NET Framework编译器）：

```powershell
& 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe' /nologo /target:exe '/out:D:\chatgpt_data\tools\openclaw-runtime\gateway-with-proxy.exe' 'D:\chatgpt_data\esp32-brookesia-desktop\tools\windows\GatewayProxyWrapper.cs'
& 'D:\chatgpt_data\tools\openclaw-runtime\gateway-with-proxy.exe' --version
```

使用当前受支持的Node调用OpenClaw CLI，执行`gateway install --wrapper <包装器exe绝对路径> --runtime-path <Node绝对路径> --force`；批处理cmd不是此Windows直接spawn路径的可用替代。安装会启动服务或影响现有实例，失败时应先检查官方status，保留备份，不循环盲目重装。

验证startup文件、实际服务命令、RPC健康、网关及Codex子进程的代理环境、微信通道和真实投递；仅观察端口监听或CLI退出码不足以认定成功。不要回显服务环境文件，其中可能含令牌。本机的安装与重连结果见[微信简报说明](../../WECHAT_BRIEFS.md)。
