using System;
using System.Diagnostics;
using System.Text;
using System.Text.RegularExpressions;

class GatewayProxyWrapper {
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
        var start = new ProcessStartInfo(Environment.GetFolderPath(Environment.SpecialFolder.System) + @"\cmd.exe");
        start.Arguments = "/d /s /c \"" + command + "\"";
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        start.RedirectStandardOutput = true;
        start.RedirectStandardError = true;
        start.EnvironmentVariables["HTTPS_PROXY"] = "http://127.0.0.1:7890";
        start.EnvironmentVariables["HTTP_PROXY"] = "http://127.0.0.1:7890";
        start.EnvironmentVariables["NO_PROXY"] = "localhost,127.0.0.1,::1,.qq.com,.weixin.qq.com";
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
