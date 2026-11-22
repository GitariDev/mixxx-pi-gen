#!/usr/bin/env python3
"""Measure how tall Mixxx draws the decks' main waveforms (wave J13, spec 2h).

Reads a Mixxx library database and its analysis folder (both given as
arguments; no library data lives in this repository) and prints, per analysed
track and per gain option, the height the main waveform's peaks reach as a
share of half the waveform's height (1.0 = the top or bottom edge).

The model follows the all-shader RGB renderer (WaveformType 17,
src/waveform/renderers/allshader/waveformrendererrgb.cpp) with the EQ knobs
at 0 dB:
  height = gain x VisualGain_0 x maxAll / 255
where maxAll is the largest filtered.all value of the visual frames under one
pixel column (DefaultZoom 3: three visual frames per pixel), top half from the
left channel, bottom half from the right.

Options:
  today   gain = pregain x ReplayGain correction (Mixxx's total_gain)
  A       gain = pregain only (the ReplayGain left out of the height)
  B       gain = total_gain, with a larger VisualGain_0

Stdlib only.  Usage:
  waveform-height.py DB ANALYSIS_DIR [--a-gain 1.0] [--b-gain 2.6] [--csv OUT]
"""
import argparse
import csv
import math
import sqlite3
import struct
import sys
import zlib
from pathlib import Path

MAIN_WAVEFORM = 1          # AnalysisDao::TYPE_WAVEFORM
VISUAL_FRAMES_PER_PIXEL = 3  # DefaultZoom 3 at 441 visual frames/s
DEFAULT_BOOST_DB = -6.0    # [ReplayGain] InitialDefaultBoost (card)
REPLAYGAIN_BOOST_DB = 0.0  # [ReplayGain] InitialReplayGainBoost (card)


def db_to_ratio(db):
    return 10.0 ** (db / 20.0)


def _varint(buffer, offset):
    result = shift = 0
    while True:
        byte = buffer[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if byte < 0x80:
            return result, offset
        shift += 7


def _fields(buffer):
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


def signal_all(blob):
    """filtered.all values (interleaved left, right) of a Waveform-5.0 file.

    The file is qCompress()ed (4-byte big-endian size, then zlib) protobuf
    mixxx.track.io.Waveform (src/proto/waveform.proto): field 3 signal_all,
    whose field 1 holds the values.
    """
    size = struct.unpack('>I', blob[:4])[0]
    data = zlib.decompress(blob[4:])
    if len(data) != size:
        raise ValueError('Waveform size does not match its header')
    for number, wire, value in _fields(data):
        if number == 3 and wire == 2:
            values = []
            for inner, inner_wire, item in _fields(value):
                if inner != 1:
                    continue
                if inner_wire == 0:
                    values.append(item)
                else:  # packed
                    offset = 0
                    while offset < len(item):
                        number_value, offset = _varint(item, offset)
                        values.append(number_value)
            return values
    raise ValueError('Waveform has no signal_all')


def pixel_peaks(values, frames=VISUAL_FRAMES_PER_PIXEL):
    """Per pixel column, the top (left) and bottom (right) maxAll values."""
    peaks = []
    left, right = values[0::2], values[1::2]
    for start in range(0, min(len(left), len(right)) - frames + 1, frames):
        peaks.append(max(left[start:start + frames]))
        peaks.append(max(right[start:start + frames]))
    return peaks


def replaygain_correction(replaygain, default_boost_db=DEFAULT_BOOST_DB,
                          replaygain_boost_db=REPLAYGAIN_BOOST_DB):
    """EnginePregain::process: the ReplayGain part of total_gain."""
    if replaygain == 0:
        return db_to_ratio(default_boost_db)
    return min(max(replaygain * db_to_ratio(replaygain_boost_db), 0.0), 10.0)


def option_gains(replaygain, a_gain, b_gain, pregain=1.0):
    total = pregain * replaygain_correction(replaygain)
    return {'today': total, 'A': pregain * a_gain, 'B': total * b_gain}


KEYS = ('p50', 'p90', 'p99', 'max', 'edge_pct', 'clip_pct')


def quantile(sorted_values, q):
    if not sorted_values:
        return float('nan')
    index = min(len(sorted_values) - 1, max(0, int(math.ceil(q * len(sorted_values))) - 1))
    return sorted_values[index]


def stats(peaks, gain):
    """Height shares (median, 90th and 99th percentile, max) and the % of pixel
    columns that reach the edge (edge_pct, height >= 0.995) or pass it
    (clip_pct, height > 1).  The analyser clamps filtered.all at 255, so at a
    gain of 1 a column at 255 sits exactly on the edge."""
    heights = sorted(gain * value / 255.0 for value in peaks)
    if not heights:
        return {key: float('nan') for key in KEYS}
    edge = sum(1 for height in heights if height >= 0.995)
    over = sum(1 for height in heights if height > 1.0)
    return {'p50': quantile(heights, 0.5), 'p90': quantile(heights, 0.9),
            'p99': quantile(heights, 0.99), 'max': heights[-1],
            'edge_pct': 100.0 * edge / len(heights), 'clip_pct': 100.0 * over / len(heights)}


def tracks(db, analysis):
    connection = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    rows = connection.execute(
        'SELECT a.id, l.id, IFNULL(l.replaygain, 0), IFNULL(l.artist, ""), '
        'IFNULL(l.title, "") FROM track_analysis a JOIN library l ON l.id = a.track_id '
        'WHERE a.type = ? ORDER BY l.id', (MAIN_WAVEFORM,)).fetchall()
    connection.close()
    for analysis_id, track_id, replaygain, artist, title in rows:
        path = Path(analysis) / str(analysis_id)
        if path.is_file():
            yield track_id, float(replaygain), f'{artist} - {title}', path


def measure(db, analysis, a_gain, b_gain):
    results = []
    for track_id, replaygain, name, path in tracks(db, analysis):
        peaks = pixel_peaks(signal_all(path.read_bytes()))
        if not peaks:
            continue
        row = {'track_id': track_id, 'name': name, 'replaygain': replaygain}
        for option, gain in option_gains(replaygain, a_gain, b_gain).items():
            row[option] = stats(peaks, gain)
        results.append(row)
    return results


def summary(results, option):
    lines = []
    for key in KEYS:
        values = sorted(row[option][key] for row in results)
        lines.append((key, quantile(values, 0.1), quantile(values, 0.5),
                      quantile(values, 0.9), values[-1]))
    return lines


def quarters(results):
    """The loudest-mastered and the quietest-mastered quarter of the tracks
    with a ReplayGain (a loud master gets the smallest ReplayGain)."""
    rated = sorted((row for row in results if row['replaygain'] > 0),
                   key=lambda row: row['replaygain'])
    size = len(rated) // 4
    return (rated[:size], rated[-size:]) if size else ([], [])


def mean(rows, option, key):
    return sum(row[option][key] for row in rows) / len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('db')
    parser.add_argument('analysis')
    parser.add_argument('--a-gain', type=float, default=1.0)
    parser.add_argument('--b-gain', type=float, default=2.6)
    parser.add_argument('--csv', type=Path)
    args = parser.parse_args(argv)
    results = measure(args.db, args.analysis, args.a_gain, args.b_gain)
    if not results:
        parser.exit(1, 'No analysed tracks found\n')
    print(f'{len(results)} analysed tracks, '
          f'{sum(1 for row in results if row["replaygain"] > 0)} with a ReplayGain')
    for option in ('today', 'A', 'B'):
        label = {'today': 'today', 'A': f'A (VisualGain {args.a_gain:g}, no ReplayGain)',
                 'B': f'B (VisualGain {args.b_gain:g}, with ReplayGain)'}[option]
        print(f'\n{label}: share of half height, across tracks (10%/median/90%/max)')
        for key, q10, q50, q90, top in summary(results, option):
            print(f'  {key:8s} {q10:6.2f} {q50:6.2f} {q90:6.2f} {top:6.2f}')
        loud, quiet = quarters(results)
        if loud:
            print('  loudest-mastered quarter (lowest ReplayGain) vs quietest quarter, mean:')
            for key in ('p99', 'edge_pct', 'clip_pct'):
                print(f'  {key:8s} {mean(loud, option, key):6.2f} {mean(quiet, option, key):6.2f}')
    if args.csv:
        with args.csv.open('w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['track_id', 'name', 'replaygain'] +
                            [f'{o}_{k}' for o in ('today', 'A', 'B')
                             for k in KEYS])
            for row in results:
                writer.writerow([row['track_id'], row['name'], f'{row["replaygain"]:.4f}'] +
                                [f'{row[o][k]:.4f}' for o in ('today', 'A', 'B')
                                 for k in KEYS])
    return 0


if __name__ == '__main__':
    sys.exit(main())
