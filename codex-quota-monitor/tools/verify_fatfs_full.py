"""Build a host regression from the pinned ESP-IDF FatFs using Zig cc."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--idf", type=Path, required=True)
    parser.add_argument("--zig", type=Path, required=True)
    args = parser.parse_args()
    source = args.idf.resolve() / "components/fatfs/src"
    compiler = args.zig.resolve()
    with tempfile.TemporaryDirectory(prefix="brookesia-fatfs-") as name:
        scratch = Path(name)
        for file in ("ff.c", "ff.h", "diskio.h"):
            shutil.copyfile(source / file, scratch / file)
        config = (source / "ffconf.h").read_text(encoding="utf-8")
        config = re.sub(r'^#include "(?:sdkconfig.h|freertos/[^"]+)"\n', "", config, flags=re.M)
        settings = {
            "FF_CODE_PAGE": 437, "FF_VOLUMES": 1, "FF_MIN_SS": 512, "FF_MAX_SS": 512,
            "FF_FS_LOCK": 4, "FF_FS_TINY": 0, "FF_FS_NOFSINFO": 0,
            "FF_MULTI_PARTITION": 0, "FF_FS_NORTC": 1, "FF_FS_REENTRANT": 0,
            "FF_USE_DYN_BUFFER": 0, "FF_USE_LABEL": 0, "FF_USE_FASTSEEK": 0,
        }
        for key, value in settings.items():
            config, count = re.subn(rf"^#define\s+{key}\s+[^\n]+", f"#define {key} {value}", config, count=1, flags=re.M)
            assert count == 1, key
        (scratch / "ffconf.h").write_text(config, encoding="utf-8")
        exe = scratch / "fatfs_full.exe"
        subprocess.run([str(compiler), "cc", "-std=c11", "-O2", "-I", str(scratch),
                        str(ROOT / "tests/fatfs_full.c"), str(scratch / "ff.c"),
                        "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
