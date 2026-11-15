"""Run current-recipe EngineRecord with real Qt/QFile and labelled external doubles.

This diagnostic does not compile EncoderWave, libsndfile, real controls, the
RecordingManager, the sidechain scheduler, or the full application. Raw output
must never be reported as production WAV lifecycle acceptance. Only --baseline
uses historical frozen source for the genuine negative control.
"""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native.library_interface_runner import reconstruct, populate_pinned, qt_flags, moc_path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "deploy/recovery-20261111/interface-recording-slice/recording"
PRODUCTION = EVIDENCE / "before/production"
SOURCE_PATHS = (
    "src/engine/sidechain/enginerecord.cpp",
    "src/engine/sidechain/enginerecord.h",
    "src/engine/sidechain/sidechainworker.h",
    "src/encoder/encoder.h",
    "src/encoder/encodercallback.h",
    "src/encoder/encodersettings.h",
    "src/encoder/encoderrecordingsettings.h",
    "src/recording/defs_recording.h",
    "src/library/media/mediauseregistry.h",
)
DOUBLE_HEADERS = (
    "audio/types.h", "util/types.h", "util/assert.h", "preferences/usersettings.h",
    "control/controlproxy.h", "control/pollingcontrolproxy.h", "track/track_decl.h",
    "track/track.h", "mixer/playerinfo.h", "util/event.h",
)
MODES = ("normal", "split", "invalid-destination", "encoder-failure",
         "write-failure", "shutdown", "interruption", "lease-denial", "split-init-failure",
         "qdatastream-recovery")


def run(output, baseline=False):
    with tempfile.TemporaryDirectory(prefix="recording-lifecycle-") as temporary:
        scratch = Path(temporary)
        if baseline:
            manifest = json.loads((EVIDENCE / "before-manifest.json").read_text())
            for relative in SOURCE_PATHS:
                source = PRODUCTION / relative
                expected = manifest["files"]["deploy/recovery-20261110/full-native-build/source/" + relative]
                if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                    raise RuntimeError("Frozen production identity changed: " + relative)
                destination = scratch / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
        else:
            reconstruct(scratch)
            populate_pinned(scratch, SOURCE_PATHS)
        doubles = scratch / "doubles"
        for relative in DOUBLE_HEADERS:
            destination = doubles / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text('#pragma once\n#include "recording_lifecycle_doubles.h"\n')
        moc = [moc_path(), "-I" + str(doubles),
               "-I" + str(scratch / "src"),
               str(scratch / "src/engine/sidechain/enginerecord.h"),
               "-o", str(scratch / "moc_enginerecord.cpp")]
        command = ["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                   "-I" + str(doubles), "-I" + str(scratch / "src"),
                   "-I" + str(ROOT / "tests/native"), "-I" + str(scratch)]
        command += [str(scratch / "src/engine/sidechain/enginerecord.cpp"),
                    str(ROOT / "tests/native/recording_lifecycle_test.cpp"),
                    "-o", str(scratch / "recording-test"), *qt_flags(('QtCore',))]
        print("MOC", repr(moc), flush=True)
        subprocess.run(moc, check=True, timeout=30)
        print("COMPILE", repr(command), flush=True)
        subprocess.run(command, check=True, timeout=90)
        results = []
        for mode in MODES:
            directory = scratch / "output" / mode
            directory.mkdir(parents=True)
            invocation = [str(scratch / "recording-test"), mode, str(directory)]
            print("RUN", repr(invocation), flush=True)
            completed = subprocess.run(invocation, check=False, text=True,
                                       capture_output=True, timeout=15)
            print(completed.stderr, end="", flush=True)
            completed.check_returncode()
            result = json.loads(completed.stdout)
            result["outputs"] = [
                {"name": path.name, "bytes": path.stat().st_size,
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in sorted(directory.glob("*.raw"))
            ]
            if output:
                retained = output.parent / "synthetic-outputs" / mode
                retained.mkdir(parents=True, exist_ok=True)
                for path in directory.glob("*.raw"):
                    shutil.copyfile(path, retained / path.name)
            print(json.dumps(result, sort_keys=True), flush=True)
            results.append(result)
        if output:
            output.write_text(json.dumps(results, indent=2) + "\n")
        return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    run(arguments.output)
