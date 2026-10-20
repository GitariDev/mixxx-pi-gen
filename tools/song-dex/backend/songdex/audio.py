from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import Frames
from mutagen.mp4 import MP4, MP4FreeForm

MB = 1024 * 1024
RESERVE = 500 * MB
FIELDS = (
    "title",
    "artist",
    "version",
    "album",
    "album_artist",
    "year",
    "label",
    "genre",
)
ID3 = dict(
    zip(FIELDS, ("TIT2", "TPE1", "TIT3", "TALB", "TPE2", "TDRC", "TPUB", "TCON"))
)
VORBIS = dict(
    zip(
        FIELDS,
        (
            "title",
            "artist",
            "version",
            "album",
            "albumartist",
            "date",
            "label",
            "genre",
        ),
    )
)
MP4_KEYS = dict(
    zip(
        FIELDS,
        (
            "\xa9nam",
            "\xa9ART",
            "----:com.apple.iTunes:VERSION",
            "\xa9alb",
            "aART",
            "\xa9day",
            "----:com.apple.iTunes:LABEL",
            "\xa9gen",
        ),
    )
)
SUPPORTED = {".mp3", ".flac", ".aif", ".aiff", ".m4a"}
PLAYABLE = SUPPORTED | {".wav", ".mp4", ".m4v"}


def signature(path):
    p = Path(path)
    if not p.is_file():
        return "missing"
    s = p.stat()
    return f"{s.st_dev}:{s.st_ino}:{s.st_size}:{s.st_mtime_ns}"


def require_space(folder, *sources, copies=2):
    """Refuse a write whose backup and working copies would not fit on the disk.

    The reserve keeps the catalog itself writable; without it a full disk leaves a
    write half prepared and nothing able to record why.
    """
    needed = copies * sum(Path(s).stat().st_size for s in sources) + RESERVE
    free = shutil.disk_usage(folder).free
    if free < needed:
        raise ValueError(
            "Not enough free disk space to back up before writing: "
            f"{free // MB} MB free, {needed // MB} MB needed. "
            "Free up space, then try again."
        )


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def container(path):
    """Where the audio starts and its real type, for files named for another.

    Some downloads are MP4/AAC saved as .mp3, and rekordbox's key analysis can
    put an ID3 tag in front of one; browsers then refuse it as MPEG audio.
    Returns (offset, media type) for MP4 content, or (0, None) for anything else.
    """
    with open(path, "rb") as f:
        head = f.read(10)
        offset = 0
        if len(head) == 10 and head[:3] == b"ID3":
            size = 0
            for byte in head[6:10]:
                size = (size << 7) | (byte & 0x7F)
            offset = 10 + size + (10 if head[5] & 0x10 else 0)
        f.seek(offset)
        box = f.read(8)
    if box[4:8] == b"ftyp":
        return offset, "audio/mp4"
    return 0, None


def open_audio(path):
    audio = mutagen.File(path)
    if audio is None:
        raise ValueError("Unrecognized audio file")
    return audio


def mapping(audio):
    return (
        MP4_KEYS
        if isinstance(audio, MP4)
        else VORBIS
        if isinstance(audio, FLAC)
        else ID3
    )


def year_of(value):
    """The four-digit year inside a date tag such as 2019-11-08, or the value itself."""
    found = re.search(r"(?<!\d)[12]\d{3}(?!\d)", str(value or ""))
    return found.group() if found else str(value or "")


def read(path):
    audio = open_audio(path)
    data = {}
    for field, key in mapping(audio).items():
        value = (audio.tags or {}).get(key, [])
        if hasattr(value, "text"):
            value = value.text
        if value:
            v = value[0]
            data[field] = v.decode("utf8") if isinstance(v, bytes) else str(v)
    if "year" in data:
        # Files often hold a full release date; rekordbox and the Dex compare years.
        data["year"] = year_of(data["year"])
    if isinstance(audio, MP4):
        data["bpm"] = str((audio.tags or {}).get("tmpo", [""])[0])
        data["key"] = str(
            (audio.tags or {}).get("----:com.apple.iTunes:initialkey", [""])[0]
        )
    else:
        data["bpm"] = str(
            (audio.tags or {}).get("bpm" if isinstance(audio, FLAC) else "TBPM", "")
        )
        data["key"] = str(
            (audio.tags or {}).get(
                "initialkey" if isinstance(audio, FLAC) else "TKEY", ""
            )
        )
    data.update(
        duration=round(audio.info.length, 3),
        bitrate=getattr(audio.info, "bitrate", 0),
        format=Path(path).suffix[1:].upper(),
    )
    return data


def write(path, changes):
    if Path(path).suffix.lower() not in SUPPORTED:
        raise ValueError("This format is not enabled for writing")
    if not changes or set(changes) - set(FIELDS):
        raise ValueError("Unsupported metadata fields")
    audio = open_audio(path)
    if audio.tags is None:
        audio.add_tags()
    for field, value in changes.items():
        if not value or len(value) > 1000:
            raise ValueError("Metadata must be nonempty and at most 1000 characters")
        key = mapping(audio)[field]
        if field == "year":
            held = (audio.tags or {}).get(key, [])
            held = getattr(held, "text", held)
            if held and year_of(held[0]) == value:
                # Same year already: keep the file's fuller date.
                continue
        if isinstance(audio, MP4):
            audio[key] = (
                [MP4FreeForm(value.encode())] if key.startswith("----:") else [value]
            )
        elif isinstance(audio, FLAC):
            audio[key] = [value]
        else:
            audio.tags.setall(key, [Frames[key](encoding=3, text=[value])])
    audio.save()
    actual = read(path)
    for field, value in changes.items():
        if actual.get(field) != value:
            raise ValueError(f"Could not verify saved {field}")


def artwork(path):
    audio = open_audio(path)
    if isinstance(audio, FLAC) and audio.pictures:
        pic = audio.pictures[0]
        return pic.data, pic.mime
    if isinstance(audio, MP4):
        covers = (audio.tags or {}).get("covr", [])
        if covers:
            return bytes(covers[0]), "image/png" if covers[
                0
            ].imageformat == 14 else "image/jpeg"
    elif audio.tags:
        pics = audio.tags.getall("APIC")
        if pics:
            return pics[0].data, pics[0].mime
    return None
