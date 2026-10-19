# 吃豆人额度 App

local.codex.quota 0.2.2，独立安装到 Brookesia s3.2；无需重刷系统。
源码：D:/chatgpt_data/brookesia-apps/codex-quota。

短周期、每周额度分别显示一条豆子轨道。每颗完整豆子代表 5% 剩余额度，
部分豆子以透明度表示不足 5% 的部分；吃豆人的位置随真实已用比例前进。
数字百分比和重置倒计时保留。嘴巴每 240 ms 开合，并有 1 像素轻微摆动，
动画本身不减少豆子、不改变额度；过期数据停止动画，切到后台停掉动画定时器。

两个 App 都使用函数作用域，修复重复打开时 QuickJS 顶层 let/const 重复声明的错误。
额度包仅依赖 Storage 0.8.3，沿用电脑端每 60 秒采集、每 15 秒推送的数据源。

构建：.venv/Scripts/python.exe tools/build_quota_bpk.py
安装：停止采集器后执行 tools/install_runtime_app.py ../brookesia-apps/codex-quota/dist/local.codex.quota.debug.0.2.2.bpk

回归覆盖正确百分比、部分豆子、动画不改变额度、过期/后台暂停、同一 VM 重复加载。
0.2.1 同时兼容框架先移除定时器、再调用 on_stop 的生命周期顺序。
额度与天气各连续重开 6 次，共 12 次全部通过；真实额度与动画更新检查通过。
用户实屏确认“显示正常，动画正常”。设备验证文件：runtime/runtime-reopen-verification.json。

0.2.2 按用户要求移除页面标题“Codex 额度”和同步时间，两条重置倒计时字号由 17 增至 30。
安装完成后再次重开两次通过，真实数据与动画检查通过；见 runtime/quota-layout-verification-0.2.2.json。
