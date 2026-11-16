using System;
using System.Diagnostics;
using System.Text;

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
        var start = new ProcessStartInfo(root + @"node-v24.22.3-win-x64\node.exe");
        start.Arguments = Quote(root + @"cli\node_modules\openclaw\openclaw.mjs");
        foreach (var argument in args) start.Arguments += " " + Quote(argument);
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        start.RedirectStandardOutput = true;
        start.RedirectStandardError = true;
        start.EnvironmentVariables["HTTPS_PROXY"] = "http://127.0.0.1:7890";
        start.EnvironmentVariables["HTTP_PROXY"] = "http://127.0.0.1:7890";
        start.EnvironmentVariables["NO_PROXY"] = "localhost,127.0.0.1,::1,.qq.com,.weixin.qq.com";
        start.EnvironmentVariables["PATH"] = root + @"node-v24.22.3-win-x64;" + Environment.GetEnvironmentVariable("PATH");
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
