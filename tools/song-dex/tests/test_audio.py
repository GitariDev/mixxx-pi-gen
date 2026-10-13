import base64
import hashlib
import subprocess

import imageio_ffmpeg
import mutagen
import pytest
from songdex import audio


def pcm(path):
    result = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-",
        ],
        capture_output=True,
        check=True,
    )
    return hashlib.sha256(result.stdout).hexdigest()


@pytest.mark.parametrize("ext", ["mp3", "flac", "aiff", "m4a"])
def test_tag_roundtrip_preserves_audio_and_unrelated_tags(audio_file, ext):
    path = audio_file(ext)
    image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jN1kAAAAASUVORK5CYII="
    )
    tagged = mutagen.File(path)
    if tagged.tags is None:
        tagged.add_tags()
    if ext == "flac":
        from mutagen.flac import Picture

        picture = Picture()
        picture.data, picture.mime, picture.type = image, "image/png", 3
        tagged.add_picture(picture)
        tagged["bpm"], tagged["initialkey"] = ["123.4"], ["F#m"]
    elif ext == "m4a":
        from mutagen.mp4 import MP4Cover, MP4FreeForm

        tagged["covr"] = [MP4Cover(image, imageformat=MP4Cover.FORMAT_PNG)]
        tagged["tmpo"] = [123]
        tagged["----:com.apple.iTunes:initialkey"] = [MP4FreeForm(b"F#m")]
    else:
        from mutagen.id3 import APIC, TBPM, TKEY

        tagged.tags.add(APIC(encoding=3, mime="image/png", type=3, data=image))
        tagged.tags.add(TBPM(encoding=3, text=["123.4"]))
        tagged.tags.add(TKEY(encoding=3, text=["F#m"]))
    tagged.save()
    before = pcm(path)
    tags_before = dict(mutagen.File(path).tags or {})
    changes = dict(
        title="長い名前 — Café (Extended Mix)",
        artist="Björk & Test",
        album="A new album",
        album_artist="Various Artists",
        year="2001",
        label="Test label",
        genre="House",
        version="Extended Mix",
    )
    audio.write(path, changes)
    after = audio.read(path)
    assert all(after[k] == v for k, v in changes.items())
    assert pcm(path) == before
    assert audio.artwork(path) == (image, "image/png")
    tags_after = dict(mutagen.File(path).tags or {})
    editable = set(audio.mapping(mutagen.File(path)).values())
    for key, value in tags_before.items():
        if key not in editable:
            assert tags_after[key] == value


def test_rejects_analysis_fields(audio_file):
    with pytest.raises(ValueError):
        audio.write(audio_file(), {"bpm": "180"})
