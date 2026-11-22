"""Read a Mixxx Waveform-5.0 analysis file into its four signals (R&D, three-band waveforms).

Stdlib only. The file is qCompress()ed protobuf mixxx.track.io.Waveform
(src/proto/waveform.proto at the pinned Mixxx commit):
  3 signal_all            Signal  (field 1: repeated int32 value)
  4 signal_filtered       FilteredSignal (1 low, 2 mid, 3 high: each a Signal)
  1 visual_sample_rate    double
Values are interleaved left, right, as in WaveformData (filtered.all, .low,
.mid, .high), each 0..255 after analyzerwaveform.h's scaleSignal
(pow(x, 0.632)).
"""
import struct
import zlib


def _varint(buffer, offset):
    result = shift = 0
    while True:
        byte = buffer[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if byte < 0x80:
            return result, offset
        shift += 7


def fields(buffer):
    """Yield (field number, wire type, value) of one protobuf message."""
    offset, end = 0, len(buffer)
    while offset < end:
        key, offset = _varint(buffer, offset)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, offset = _varint(buffer, offset)
        elif wire == 1:
            value, offset = buffer[offset:offset + 8], offset + 8
        elif wire == 2:
            length, offset = _varint(buffer, offset)
            value, offset = buffer[offset:offset + length], offset + length
        elif wire == 5:
            value, offset = buffer[offset:offset + 4], offset + 4
        else:
            raise ValueError(f'Unsupported protobuf wire type {wire}')
        yield number, wire, value


def _signal_values(message):
    values = []
    for number, wire, item in fields(message):
        if number != 1:
            continue
        if wire == 0:
            values.append(item)
        else:  # packed
            offset = 0
            while offset < len(item):
                value, offset = _varint(item, offset)
                values.append(value)
    return values


def decode(blob):
    """{'all', 'low', 'mid', 'high': interleaved values, 'rate': visual frames/s}."""
    size = struct.unpack('>I', blob[:4])[0]
    data = zlib.decompress(blob[4:])
    if len(data) != size:
        raise ValueError('Waveform size does not match its header')
    out = {'rate': None}
    for number, wire, value in fields(data):
        if number == 1 and wire == 1:
            out['rate'] = struct.unpack('<d', value)[0]
        elif number == 3 and wire == 2:
            out['all'] = _signal_values(value)
        elif number == 4 and wire == 2:
            for inner, inner_wire, band in fields(value):
                name = {1: 'low', 2: 'mid', 3: 'high'}.get(inner)
                if name and inner_wire == 2:
                    out[name] = _signal_values(band)
    for name in ('all', 'low', 'mid', 'high'):
        if name not in out:
            raise ValueError(f'Waveform has no {name} signal')
    return out
