"""Independent little-endian RIFF/PCM validation; never calls libsndfile."""
from pathlib import Path
import struct


def decode(path):
    payload = Path(path).read_bytes()
    if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise AssertionError("Missing finalized RIFF/WAVE header")
    if struct.unpack_from("<I", payload, 4)[0] + 8 != len(payload):
        raise AssertionError("RIFF length differs from physical length")
    offset = 12
    chunks = {}
    while offset + 8 <= len(payload):
        kind, size = struct.unpack_from("<4sI", payload, offset)
        end = offset + 8 + size
        if end > len(payload):
            raise AssertionError("Chunk length exceeds physical length")
        chunks[kind] = payload[offset + 8:end]
        offset = end + size % 2
    if offset != len(payload):
        raise AssertionError("Trailing unparsed WAV bytes")
    encoding, channels, rate, byte_rate, alignment, bits = struct.unpack_from("<HHIIHH", chunks[b"fmt "])
    if encoding != 1 or channels != 2 or bits not in (16, 24):
        raise AssertionError("Expected actual stereo PCM16/24 WAV")
    if alignment != channels * bits // 8 or byte_rate != rate * alignment:
        raise AssertionError("Invalid WAV format rate/alignment")
    data = chunks[b"data"]
    if len(data) % alignment:
        raise AssertionError("Incomplete PCM frame")
    width = bits // 8
    samples = [int.from_bytes(data[index:index + width], "little", signed=True)
               for index in range(0, len(data), width)]
    return {"rate": rate, "channels": channels, "bits": bits,
            "frames": len(data) // alignment, "samples": samples}


def assert_signal(path, blocks, frames_per_block=2048, rate=48000, bits=16):
    result = decode(path)
    assert (result["rate"], result["channels"], result["bits"], result["frames"]) == (
        rate, 2, bits, blocks * frames_per_block), result
    scale = 1 << (bits - 1)
    expected = [scale // 4, -scale // 2] * (blocks * frames_per_block)
    assert result["samples"] == expected, "Known-signal payload mismatch"
    return {key: value for key, value in result.items() if key != "samples"}
