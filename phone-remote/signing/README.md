# 安卓原签名的加密备份

`development-signing.jks.enc` 是“小马遥控”现有签名文件的加密副本，使用随机密码、scrypt和AES-256-GCM；原JKS及加密密码均不入Git。现有APK的证书SHA256见`manifest.json`，可公开用于核对。

原JKS内部开发口令仍为构建脚本使用的`android`；**这不是备份的加密密码**。加密密码是独立生成的强随机值，仅保存在原电脑仓库外：`F:/codex_data/private_signing/esp32_touch_AMOLED/signing-password.txt`。原电脑该目录已限制为当前Windows账号及SYSTEM访问。请把密码文件另存到自己的密码管理器或私有备份，不能随密文提交到公共仓库；仅有GitHub仓库无法恢复签名。

## 换电脑后恢复

安装Python并准备安卓工具链，密码从自己的私有备份取回。以下示例在仓库根目录执行，盘符和私有目录可按新电脑调整：

```powershell
python -m pip install -r phone-remote/tools/requirements-signing.txt
python phone-remote/tools/bootstrap_android.py --cache D:/codex/android-remote-build
python phone-remote/tools/signing_backup.py decrypt --input phone-remote/signing/development-signing.jks.enc --output D:/codex/android-remote-build/app/development-signing.jks
```

恢复工具交互式询问加密密码，不显示输入内容；也支持`--password-file <仓库外的密码文件>`，不会把密码写在命令行。工具拒绝覆盖已有文件，恢复结果必须在仓库外。密码错误或密文损坏时不写出签名文件。

随后使用原签名构建：

```powershell
python phone-remote/tools/build_android.py --tools D:/codex/android-remote-build/tools.json --work D:/codex/android-remote-build/app
```

也可用`--keystore <仓库外的原JKS路径>`。缺少原签名时构建脚本先退出，避免无意生成不兼容的新身份。只有确实需要创建独立测试身份时，才使用`--generate-development-key`；新签名不能直接覆盖原签名APK。`--output <仓库外的测试APK路径>`可验证构建而不替换已发布安装包。

## 生成新加密备份

```powershell
python phone-remote/tools/signing_backup.py encrypt --input D:/codex/android-remote-build/app/development-signing.jks --output D:/private-backups/new-signing.jks.enc
```

交互输入不少于20个字符的加密密码并确认。此工具不覆盖原文件；加密副本带认证标签，恢复时核对完整性。新备份及密码需单独保存。

## 已完成验证

2026-11-01：实际签名文件解密前后字节一致；使用恢复文件构建的APK签名校验通过，证书与已发布0.2.0一致。单元检查覆盖随机加密、往返恢复、错误密码、密文篡改、过短密码、过大输入、失败时无明文输出及不覆盖已有签名；缺少原签名时构建会在编译前停止。验证未修改现有APK、固件或设备。

```powershell
python phone-remote/tests/test_signing_backup.py
```
