"""
tests/host_test_helper.py - Shared Host-Test Build and Execution Helper

Locates an available C++ compiler, verifies source dependencies, rebuilds
the host firmware test executable whenever source files change, and reports
clear build failures.
"""

import os
import shutil
import subprocess
import unittest
from pathlib import Path
from typing import List, Optional

KNOWN_COMPILER_PATHS = [
    Path("C:/Program Files/Windhawk/Compiler/bin/clang++.exe"),
    Path("C:/msys64/ucrt64/bin/g++.exe"),
    Path("C:/msys64/mingw64/bin/g++.exe"),
    Path("C:/mingw64/bin/g++.exe"),
]

def find_cpp_compiler() -> Optional[Path]:
    """Locates an available C++ compiler from environment, PATH, or standard paths."""
    # 1. Check CXX environment variable
    cxx_env = os.environ.get("CXX")
    if cxx_env:
        candidate = Path(cxx_env)
        if candidate.exists():
            return candidate
        which_cxx = shutil.which(cxx_env)
        if which_cxx:
            return Path(which_cxx)

    # 2. Check standard compiler names in system PATH
    for name in ("clang++", "g++", "c++"):
        found = shutil.which(name)
        if found:
            return Path(found)

    # 3. Check known local installation paths
    for path in KNOWN_COMPILER_PATHS:
        if path.exists():
            return path

    return None

def get_source_files(root: Path) -> List[Path]:
    """Returns list of source files that affect host_firmware_test."""
    return [
        root / "tests" / "host_firmware_test.cpp",
        root / "firmware" / "src" / "camera" / "camera_manager.cpp",
        root / "firmware" / "src" / "transport" / "vision_transport.cpp",
        root / "firmware" / "src" / "transport" / "connectivity_manager.cpp",
        root / "firmware" / "src" / "safety" / "motor_safety.cpp",
        root / "firmware" / "src" / "display" / "display_interface.cpp",
        root / "firmware" / "src" / "display" / "ili9341_driver.cpp",
        root / "firmware" / "src" / "display" / "doruru_persona.cpp",
    ]

def get_header_files(root: Path) -> List[Path]:
    """Returns list of relevant header files."""
    headers = []
    include_dirs = [
        root / "firmware" / "include",
        root / "firmware" / "src" / "camera",
        root / "firmware" / "src" / "transport",
        root / "firmware" / "src" / "safety",
        root / "firmware" / "src" / "display",
    ]
    for d in include_dirs:
        if d.exists():
            headers.extend(d.glob("*.h"))
    return headers

def ensure_compiled_host_firmware_test() -> Path:
    """
    Ensures host firmware test binary is compiled and up-to-date.
    Rebuilds whenever any source or header file is newer than the binary.
    Raises RuntimeError with clear diagnostics if no compiler is found or compilation fails.
    """
    tests_dir = Path(__file__).resolve().parent
    root = tests_dir.parent
    exe_name = "host_firmware_test.exe" if os.name == "nt" else "host_firmware_test"
    exe_path = tests_dir / exe_name

    source_files = get_source_files(root)
    header_files = get_header_files(root)
    all_dependencies = source_files + header_files

    # Check if rebuild is needed
    rebuild_needed = not exe_path.exists()
    if not rebuild_needed:
        exe_mtime = exe_path.stat().st_mtime
        for dep in all_dependencies:
            if dep.exists() and dep.stat().st_mtime > exe_mtime:
                rebuild_needed = True
                break

    if not rebuild_needed:
        return exe_path

    # Locate C++ compiler
    compiler = find_cpp_compiler()
    if not compiler:
        raise RuntimeError(
            "Host test build failure: No C++ compiler found. "
            "Please install clang++ or g++, set the CXX environment variable, "
            "or add the compiler to your system PATH."
        )

    # Build command
    cmd = [str(compiler)]
    if os.name == "nt":
        cmd.append("-static")
    cmd.extend([
        *[str(src) for src in source_files],
        f"-I{root / 'firmware' / 'include'}",
        f"-I{root / 'firmware' / 'src' / 'camera'}",
        f"-I{root / 'firmware' / 'src' / 'transport'}",
        f"-I{root / 'firmware' / 'src' / 'safety'}",
        f"-I{root / 'firmware' / 'src' / 'display'}",
        "-o", str(exe_path)
    ])

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Host test compilation failed using compiler '{compiler}':\n"
            f"Command: {' '.join(cmd)}\n"
            f"Error Output:\n{e.stderr or e.stdout}"
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Failed to execute compiler '{compiler}': {str(e)}"
        ) from e

    return exe_path

def execute_host_firmware_test(exe_path: Path) -> subprocess.CompletedProcess:
    """
    Executes compiled host firmware test executable.
    If Windows Code Integrity / Smart App Control policy blocks running locally
    compiled unsigned binaries (WinError 4551), raises unittest.SkipTest.
    Preserves propagation of other OSError exceptions.
    """
    try:
        return subprocess.run([str(exe_path)], capture_output=True, text=True, check=True)
    except OSError as e:
        if getattr(e, "winerror", None) == 4551:
            raise unittest.SkipTest(
                "Windows Code Integrity policy blocked execution of unsigned local binary (WinError 4551)"
            )
        raise
