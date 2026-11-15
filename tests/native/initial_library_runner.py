import importlib.util
import os
from pathlib import Path
import platform
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def build(target):
    specification = importlib.util.spec_from_file_location(
        "initial_library_reconstruct", ROOT / "tests/native/library_interface_runner.py")
    helper = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(helper)
    helper.reconstruct(target)
    binary = target / "initial-library-test"
    command = ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
               "-I" + str(target / "src"),
               str(ROOT / "tests/native/initial_library_test.cpp"), "-o", str(binary),
               *helper.qt_flags(('QtCore',))]
    subprocess.run(command, check=True, timeout=90)
    return binary
