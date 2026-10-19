"""Build ESP-IDF projects; standalone flashing requires a verified device backup."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from prepare_idf_metadata import prepare

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flash", action="store_true")
    parser.add_argument("--port")
    parser.add_argument("--reconfigure", action="store_true")
    parser.add_argument("--project", default="firmware", help="Project-relative build directory")
    args = parser.parse_args()
    if args.flash and not args.port:
        parser.error("--flash requires --port")
    if args.flash and args.project != "firmware":
        parser.error("Only the standalone firmware can be flashed; compile-check is not a runnable system.")
    project = (ROOT / args.project).resolve()
    if not project.is_relative_to(ROOT) or not (project / "CMakeLists.txt").is_file():
        parser.error("Invalid project directory")
    idf = ROOT / "tools/esp-idf-v5.5.5"
    if not (idf / "tools/idf.py").is_file():
        raise SystemExit("Install the toolchain using tools/bootstrap_toolchain.py first.")
    prepare(idf)
    env = os.environ.copy()
    env.update(IDF_PATH=str(idf), IDF_TOOLS_PATH=str(ROOT / "tools/idf-tools"), IDF_TARGET="esp32s3")
    exported = subprocess.run(
        [sys.executable, str(idf / "tools/idf_tools.py"), "export", "--format", "key-value"],
        env=env, text=True, encoding="utf-8", capture_output=True,
    )
    if exported.returncode:
        sys.stderr.write(exported.stderr + exported.stdout)
        raise SystemExit("Toolchain incomplete. Run tools/bootstrap_toolchain.py.")
    for line in exported.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            env[key] = value.replace("%PATH%", env["PATH"])
    python = Path(env["IDF_PYTHON_ENV_PATH"]) / "Scripts/python.exe"
    command = [str(python), str(idf / "tools/idf.py"), "-C", str(project)]
    if args.reconfigure:
        subprocess.run(command + ["reconfigure"], env=env, check=True)
    subprocess.run(command + ["build"], env=env, check=True)
    if args.flash:
        subprocess.run([str(python), str(ROOT / "tools/flash_standalone.py"), "--port", args.port], env=env, check=True)


if __name__ == "__main__":
    main()
