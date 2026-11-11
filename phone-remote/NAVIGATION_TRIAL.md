# 手机导航免费配额试验

这是先验证账号权限和手机SDK的试验阶段，私有安装包版本为`0.4.1-trial`，仍使用`com.xiaoma.remote`及原签名，可覆盖现有0.4.0。ESP32固件、设备界面和BLE协议未改动，目前不向ESP32发送导航信息。

## 操作与范围

在手机打开“小马遥控 → 导航免费试验”：

1. “离线演示”仅显示本地模拟箭头和文字，不加载/初始化高德SDK。
2. 核对账号当月个人学习减免和剩余配额，再勾选页面确认框。
3. “在线定位一次”经独立隐私说明及Android位置授权后获取一次位置，显示高德坐标与精度；关闭地址反查，使用HTTPS，完成/超时15秒/离开页面即停止定位。不调用“智能硬件定位”服务。
4. “算路并模拟60秒”请求一条固定上海样例步行路线，成功后使用SDK模拟导航。它不会按手机当前位置导航，不是可用于实际出行的导航产品。样例坐标是`31.230416,121.473701 → 31.240000,121.490000`。

算路与定位合计每天最多5次主动尝试（北京时间自然日，失败也计次）。无自动重试，不启用后台定位、实时GPS导航、地点搜索、地图图面或车载模式。页面离开即关闭已创建的导航/定位对象；导航总时限75秒，算路成功后的模拟最多60秒。

**本地5次限制只约束本App的主动尝试，不是高德账户的费用硬上限**，SDK自身的初始化、遥测及服务内部请求不由该计数器逐项计量，也不涵盖同一账号其他应用的调用。免费依据账号实际生效的个人学习减免、服务类别与余额/账单规则；月配额外仍可能收费。未确认免费权益时保持离线演示。试验不执行充值、购买、开通计费或余额操作。

## 隐私与凭据

打开试验页不初始化SDK。真实调用前明确说明高德SDK和相关隐私政策，由手机使用者点击同意；单次定位还需要系统位置授权。代码不记录坐标、Key或SDK原始错误信息，仅在手机上显示结果/错误码。

Key、原签名、SDK缓存、生成Manifest、构建日志、APK均在仓库外或忽略的私有runtime中。**含Key的APK不能上传GitHub**；当前私有成品为`D:/chatgpt_data/private/amap/xiaoma-remote-0.4.1-trial.apk`。试验构建器拒绝仓库内的Key、签名、工作目录和输出路径，核对原证书后才复制成品。公开稳定版Manifest和APK0.4.0不变，普通构建不会显示试验入口。

当前打包原生库仅包含`arm64-v8a`，需要64位ARM安卓手机。导航SDK11.3.100、定位SDK11.3.101来自官方一键下载；公开下载里的内层SDK压缩包MD5与官方值一致，完整bundle/JAR/arm64库SHA256固定在`amap-sdk.json`，不把SDK二进制提交Git。

## 重建

先准备原有Android构建工具，再执行以下命令，所有实际路径可替换为仓库外目录：

```powershell
python phone-remote/tools/prepare_navigation_sdk.py --cache D:/chatgpt_data/tmp/amap-sdk-11.3.100
python phone-remote/tools/build_navigation_trial.py --tools D:/chatgpt_data/tmp/android-remote-build/tools.json --work D:/chatgpt_data/tmp/android-navigation-trial --key-file D:/chatgpt_data/private/amap/android-key.txt --sdk-libs D:/chatgpt_data/tmp/amap-sdk-11.3.100/libs --keystore <仓库外原签名路径> --output D:/chatgpt_data/private/amap/xiaoma-remote-0.4.1-trial.apk
```

签名解密规则见[原签名说明](signing/README.md)。申请Android Key时使用现有包名及原APK证书SHA1；不要改包名或换签名，否则Key鉴权和覆盖安装都会失效。

## 验证状态

构建/签名/ZIP完整性、固定SDK哈希、对应SDK API编译检查通过。Java限次测试覆盖五次边界、确认/忙碌状态、新一天和时间回拨；Python覆盖Key不回显、私有路径约束及定位权限仅注入试验Manifest。编译和测试没有使用用户Key调用高德服务器。

2026-11-11用户已安装私有试验包，确认单次定位成功并显示精度；随后确认固定路线算路成功，模拟转向、道路名和距离信息正常更新。Key鉴权、手机定位权限及SDK导航数据回调的核心链路已通过实机确认。

控制台本次实际用量/学习减免/实付金额仍待确认；不能把调用成功或尚无明细时的零金额当作本次免费已验证。下一阶段为设备端蓝牙显示，当前尚未接入。

官方参考：[计费说明](https://lbs.amap.com/pages/base_service_price)、[导航SDK下载](https://developer.amap.com/api/android-navi-sdk/download)、[步行/骑行算路](https://developer.amap.com/api/android-navi-sdk/guide/route-plan/ride-route-plan)、[模拟导航](https://developer.amap.com/api/android-navi-sdk/guide/navigation-map/gps-navi)、[定位隐私及初始化](https://lbs.amap.com/api/location-sdk-for-android/guide/create-project/dev-attention)。
