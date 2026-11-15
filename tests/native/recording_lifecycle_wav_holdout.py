"""Reserved independent WAV boundary oracle, executed after main regression green."""
import argparse
import json
from pathlib import Path

from recording_lifecycle_wav_decode import assert_signal


def check(result_path):
    results = json.loads(result_path.read_text())
    assert len(results) == 1 and results[0]["mode"] == "holdout"
    result = results[0]
    assert result["failureStatus"] == 0
    assert result["failureNotifications"][-1] == {"recording": False, "error": True}
    assert sum(item["error"] for item in result["notifications"]) == 1
    assert result["notifications"][-1] == {"recording": False, "error": False}
    path = result_path.parent / (result_path.stem + "-output") / "holdout/recovery.wav"
    decoded = assert_signal(path, 1, frames_per_block=1025, rate=44100, bits=24)
    print(json.dumps({"holdout": "PASS", "decoded": decoded}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    check(parser.parse_args().result)
