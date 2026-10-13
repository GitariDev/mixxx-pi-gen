import subprocess

import imageio_ffmpeg
import pytest
from songdex.db import Store
from songdex.service import Service


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "dex")


@pytest.fixture
def service(store):
    return Service(store)


@pytest.fixture
def audio_file(tmp_path):
    def make(ext="flac"):
        path = tmp_path / f"track.{ext}"
        codec = {
            "mp3": "libmp3lame",
            "flac": "flac",
            "aiff": "pcm_s16be",
            "m4a": "aac",
        }[ext]
        subprocess.run(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=2",
                "-c:a",
                codec,
                "-metadata",
                "title=Original",
                "-metadata",
                "artist=Artist",
                "-metadata",
                "comment=keep me",
                str(path),
            ],
            check=True,
            capture_output=True,
        )
        return path

    return make


def ingest(service, path, source="test", source_id="1", **metadata):
    service.ingest(
        source,
        {
            "source_id": source_id,
            "path": str(path),
            "metadata": {
                "title": "Original",
                "artist": "Artist",
                "album": "Album",
                **metadata,
            },
            "playlists": [{"name": "Warm up", "position": 1}],
        },
    )
    return service.store.tracks()[-1]
