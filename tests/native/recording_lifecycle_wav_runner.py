"""Production EngineRecord + EncoderWave/settings + real libsndfile, external UI doubles."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import reconstruct, populate_pinned, qt_flags, moc_path, sndfile_flags

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "deploy/recovery-20261111/native-completion-slice/recording"
PRIOR = ROOT / "deploy/recovery-20261111/interface-recording-slice/recording"
PATCH = ROOT / "stage3/01-install-packages/files/mixxx-recording-lifecycle.patch"
EXTRA = ("src/encoder/encoderwave.cpp", "src/encoder/encoderwave.h",
         "src/encoder/encoderwavesettings.cpp", "src/encoder/encoderwavesettings.h")


def run(output=None, baseline=False, holdout=False):
    spec = importlib.util.spec_from_file_location("diagnostic", ROOT / "tests/native/recording_lifecycle_runner.py")
    diagnostic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diagnostic)
    dependency_flags = sndfile_flags()
    with tempfile.TemporaryDirectory(prefix="recording-wav-") as temporary:
        scratch = Path(temporary)
        if baseline:
            manifest = json.loads((PRIOR / "before-manifest.json").read_text())["files"]
            for relative in (*diagnostic.SOURCE_PATHS, *EXTRA):
                source = diagnostic.PRODUCTION / relative
                if hashlib.sha256(source.read_bytes()).hexdigest() != manifest["deploy/recovery-20261110/full-native-build/source/" + relative]:
                    raise RuntimeError("Frozen source changed: " + relative)
                target = scratch / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        else:
            reconstruct(scratch)
            populate_pinned(scratch, (*diagnostic.SOURCE_PATHS, *EXTRA))
        doubles = scratch / "doubles"
        for relative in diagnostic.DOUBLE_HEADERS:
            target = doubles / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('#pragma once\n#include "recording_lifecycle_doubles.h"\n')
        moc = [moc_path(), "-I" + str(doubles), "-I" + str(scratch / "src"),
               str(scratch / "src/engine/sidechain/enginerecord.h"), "-o", str(scratch / "moc_enginerecord.cpp")]
        command = ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                   "-I" + str(doubles), "-I" + str(scratch / "src"), "-I" + str(ROOT / "tests/native"),
                   "-I" + str(scratch)]
        command += [str(scratch / relative) for relative in
                    ("src/engine/sidechain/enginerecord.cpp", "src/encoder/encoderwave.cpp", "src/encoder/encoderwavesettings.cpp")]
        command += [str(ROOT / "tests/native/recording_lifecycle_wav_test.cpp"), "-o", str(scratch / "wav-test"),
                    *qt_flags(('QtCore',)), *dependency_flags]
        for invocation in (moc, command):
            print("COMMAND", repr(invocation), flush=True)
            subprocess.run(invocation, check=True, timeout=90)
        results = []
        modes = ("holdout",) if holdout else ("normal", "write-failure", "stop-failure", "split", "destructor", "invalid-destination", "seek-failure", "split-stop-failure")
        for mode in modes:
            directory = (output.parent / (output.stem + "-output") / mode) if output else scratch / mode
            directory.mkdir(parents=True, exist_ok=True)
            invocation = [str(scratch / "wav-test"), mode, str(directory)]
            print("RUN", repr(invocation), flush=True)
            completed = subprocess.run(invocation, text=True, capture_output=True, timeout=15, check=True)
            print(completed.stderr, end="", flush=True)
            result = json.loads(completed.stdout)
            result["files"] = [{"path": str(path), "bytes": path.stat().st_size,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(directory.glob("*.wav"))]
            print(json.dumps(result), flush=True)
            results.append(result)
        if output:
            output.write_text(json.dumps(results, indent=2) + "\n")
        return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output, args.baseline, args.holdout)
