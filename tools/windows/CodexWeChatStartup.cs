using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;

class CodexWeChatStartup {
    static string FindDesktopLaunch(int session) {
        DateTime first = DateTime.MaxValue;
        int id = 0;
        foreach (var process in Process.GetProcessesByName("ChatGPT")) {
            using (process) {
                try {
                    if (process.SessionId != session) continue;
                    var image = process.MainModule.FileName;
                    if (!Regex.IsMatch(image, @"\\WindowsApps\\OpenAI\.Codex_[^\\]+\\app\\ChatGPT\.exe$", RegexOptions.IgnoreCase)) {
                        continue;
                    }
                    var started = process.StartTime.ToUniversalTime();
                    if (started < first) {
                        first = started;
                        id = process.Id;
                    }
                } catch (System.ComponentModel.Win32Exception) {
                    // Another session's process or a process that is exiting.
                } catch (InvalidOperationException) {}
            }
        }
        return id == 0 ? null : id + ":" + first.ToFileTimeUtc();
    }

    static string QuotePath(string path) {
        return "\"" + path + "\"";
    }

    static void Warn(string message) {
        var thread = new Thread(() => MessageBox.Show(message, "Codex 微信启动检查",
            MessageBoxButtons.OK, MessageBoxIcon.Warning));
        thread.IsBackground = true;
        thread.Start();
    }

    static void Check(string[] paths, string launch) {
        try {
            var start = new ProcessStartInfo(paths[0], QuotePath(paths[1]) +
                " --config " + QuotePath(paths[2]) + " --codex-launch " + launch);
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.RedirectStandardOutput = true;
            start.StandardOutputEncoding = Encoding.UTF8;
            start.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            using (var check = Process.Start(start)) {
                var message = check.StandardOutput.ReadToEnd().Trim();
                check.WaitForExit();
                if (check.ExitCode != 0) {
                    Warn(string.IsNullOrEmpty(message) ? "微信状态检查没有返回结果。" : message);
                }
            }
        } catch (System.ComponentModel.Win32Exception) {
            Warn("无法启动微信状态检查。");
        }
    }

    static int Main(string[] paths) {
        if (paths.Length != 3 || !Path.IsPathRooted(paths[0]) || !Path.IsPathRooted(paths[1])
            || !Path.IsPathRooted(paths[2])) return 2;
        using (var singleton = new Mutex(false, @"Local\CodexWeChatStartupCheck")) {
            if (!singleton.WaitOne(0)) return 0;
            var session = Process.GetCurrentProcess().SessionId;
            string checkedLaunch = null;
            while (true) {
                var launch = FindDesktopLaunch(session);
                if (launch != null && checkedLaunch != launch) {
                    checkedLaunch = launch;
                    Check(paths, launch);
                }
                Thread.Sleep(4000);
            }
        }
    }
}
