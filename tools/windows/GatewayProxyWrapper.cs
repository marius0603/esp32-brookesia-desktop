using System;
using System.Diagnostics;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

class GatewayProxyWrapper {
    const int ProxyPort = 7890;

    static void WaitForProxy() {
        var wait = Stopwatch.StartNew();
        while (wait.ElapsedMilliseconds < 30000) {
            using (var socket = new TcpClient()) {
                try {
                    var connection = socket.ConnectAsync("127.0.0.1", ProxyPort);
                    if (connection.Wait(300) && socket.Connected) return;
                } catch (AggregateException) {
                    // The desktop proxy may still be starting at Windows login.
                }
            }
            Thread.Sleep(450);
        }
        Console.Error.WriteLine("Local proxy not ready at startup; gateway will continue connecting.");
    }

    static string Quote(string value) {
        var text = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value) {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') { text.Append('\\', slashes * 2 + 1); text.Append(c); }
            else { text.Append('\\', slashes); text.Append(c); }
            slashes = 0;
        }
        text.Append('\\', slashes * 2);
        return text.Append('"').ToString();
    }
    static int Main(string[] args) {
        const string root = @"D:\chatgpt_data\tools\openclaw-runtime\";
        // The native task supervisor requires its immediate parent to be CMD.
        // Keep that verified lifetime owner instead of placing this EXE there.
        string command = Quote(root + @"node-v24.22.3-win-x64\node.exe") + " " +
            Quote(root + @"cli\node_modules\openclaw\openclaw.mjs");
        foreach (var argument in args) {
            // This wrapper accepts service switches, not arbitrary CMD text.
            if (!Regex.IsMatch(argument, @"\A[a-zA-Z0-9:_./=-]+\z")) {
                Console.Error.WriteLine("Unsupported gateway launcher argument");
                return 2;
            }
            command += " " + argument;
        }
        if (args.Length > 0 && args[0] == "gateway" &&
            Array.Exists(args, arg => arg == "run" || arg == "--port" || arg.StartsWith("--port=", StringComparison.Ordinal))) {
            WaitForProxy();
        }
        var start = new ProcessStartInfo(Environment.GetFolderPath(Environment.SpecialFolder.System) + @"\cmd.exe");
        start.Arguments = "/d /s /c \"" + command + "\"";
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        start.RedirectStandardOutput = true;
        start.RedirectStandardError = true;
        start.EnvironmentVariables["HTTPS_PROXY"] = "http://127.0.0.1:" + ProxyPort;
        start.EnvironmentVariables["HTTP_PROXY"] = "http://127.0.0.1:" + ProxyPort;
        // Resolve and reach WeChat through the proxy as well. Its direct Windows
        // lookup has repeatedly failed even with a healthy local gateway.
        start.EnvironmentVariables["NO_PROXY"] = "localhost,127.0.0.1,::1";
        start.EnvironmentVariables["PATH"] = root + @"node-v24.22.3-win-x64;" + Environment.GetEnvironmentVariable("PATH");
        start.EnvironmentVariables["OPENCLAW_WINDOWS_TASK_HIDDEN_LAUNCHER"] = "cmd";
        using (var child = Process.Start(start)) {
            child.OutputDataReceived += (sender, line) => { if (line.Data != null) Console.Out.WriteLine(line.Data); };
            child.ErrorDataReceived += (sender, line) => { if (line.Data != null) Console.Error.WriteLine(line.Data); };
            child.BeginOutputReadLine();
            child.BeginErrorReadLine();
            child.WaitForExit();
            return child.ExitCode;
        }
    }
}
