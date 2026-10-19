"""Avoid hashing the entire extracted SDK during CMake's Git version detection on Windows."""
from pathlib import Path


def prepare(idf):
    path = Path(idf) / "tools/cmake/third_party/GetGitRevisionDescription.cmake"
    source = path.read_text(encoding="utf-8")
    marker = '        "--dirty"\n'
    if marker in source:
        source = source.replace(marker, "        # Quota monitor: skip archive-wide dirty scan; SDK sources are project-local.\n", 1)
        path.write_text(source, encoding="utf-8")
        print("Prepared Windows SDK metadata lookup (no SDK driver or compiler code changed).", flush=True)
