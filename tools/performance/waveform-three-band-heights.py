#!/usr/bin/env python3
"""How tall each three-band style draws the main waveforms, over a whole library (R&D).

Per analysed track, per pixel column (four visual frames, as on the card),
the height each style reaches as a share of the space it draws into (1.0 =
the edge), with the main waveforms' m_gain = pregain x kMainWaveformGain (0.90 since
2026-11-23, fd1e940; 0.80 before; --gain), pregain 1, VisualGain_0 1:
  today/B  filtered.all x G (B keeps today's outline exactly)
  A        each band x G (getGain(true)'s x2 dropped for the main rows);
           A-stock: x 1.60 (stock Filtered with J15)
  C        top half: low x G; bottom half: max(mid, high) x G
  D        each lane: its band x G (bar from the lane floor)
  A Loop   the Loop panel's waveform under A (type 19 is global), the
           tallest band at total_gain (pregain x ReplayGain correction; no
           ReplayGain: the -6 dB default), the height of RGB there (owner,
           2026-11-23: "Same height as RGB"); A-stock Loop: stock Filtered at
           2 x total_gain, which MixPi no longer draws
and the ratio of the three band levels' sum to filtered.all (how much the
bands co-occur, which is why an RGB mix turns pastel),
and the pixels a frame fills per deck (overdraw counted), from the same
geometry as waveform-three-band-sim.py. Prints medians across tracks; names
no track. Needs numpy.

Usage: waveform-three-band-heights.py DB ANALYSIS_DIR [--gain 0.90]
"""
import importlib.util
import sqlite3
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('waveform_bands', HERE / 'waveform_bands.py')
wb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wb)

FPP, HALF, LANE = 4, 64.0, (128 - 4) / 3.0
G = 0.90  # kMainWaveformGain (mixxx-waveform-height-gain.patch); --gain to change


def columns(path):
    d = wb.decode(path.read_bytes())
    n = min(len(d[k]) for k in ('all', 'low', 'mid', 'high')) // (2 * FPP) * (2 * FPP)
    return {k: np.array(d[k][:n], dtype=np.float64).reshape(-1, FPP, 2).max(axis=1) for k in ('all', 'low', 'mid', 'high')}


def replaygain_correction(replaygain):
    """EnginePregain: the ReplayGain part of total_gain (card: -6 dB default boost)."""
    return 10 ** (-6.0 / 20) if replaygain == 0 else min(max(replaygain, 0.0), 10.0)


def styles(c, replaygain=0.0):
    l, m, h, a = c['low'], c['mid'], c['high'], c['all']
    l1, m1, h1 = l.max(1), m.max(1), h.max(1)
    s = np.maximum(l + m + h, 1)
    heights = {
        'today/B outline': a * G / 255,
        'A outer (bands xG)': np.maximum(np.maximum(l, m), h) * G / 255,
        'A-stock outer (x2G)': np.maximum(np.maximum(l, m), h) * 2 * G / 255,
        'C top: low': l1 * G / 255,
        'C bottom: max(mid,high)': np.maximum(m1, h1) * G / 255,
        'D low lane': l1 * G / 255,
        'D mid lane': m1 * G / 255,
        'D high lane': h1 * G / 255,
        'A Loop panel (total_gain)': np.maximum(np.maximum(l, m), h) * replaygain_correction(replaygain) / 255,
        'A-stock Loop (2 x total_gain)': np.maximum(np.maximum(l, m), h) * 2 * replaygain_correction(replaygain) / 255,
        'ratio (low+mid+high)/all': (l + m + h) / np.maximum(a, 1),
    }
    clipped = lambda x: np.minimum(x, 1.0)
    fill = {
        'today': (clipped(a * G / 255) * HALF).sum(1),
        'A': sum((clipped(b * G / 255) * HALF).sum(1) for b in (l, m, h)),
        'B': (clipped(a * G / 255) * HALF).sum(1) * (1 + ((l + m) / s).mean(1) + (l / s).mean(1)),
        'C': (clipped(l1 * G / 255) + clipped(m1 * G / 255) + clipped(h1 * G / 255)) * HALF,
        'D': sum(clipped(b * G / 255) * LANE for b in (l1, m1, h1)),
    }
    return heights, fill


def main(argv):
    global G
    args = list(argv[1:])
    if '--gain' in args:
        i = args.index('--gain')
        G = float(args[i + 1])
        del args[i:i + 2]
    db, analysis = args[0], Path(args[1])
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    ids = con.execute('SELECT a.id, IFNULL(l.replaygain, 0) FROM track_analysis a '
                      'JOIN library l ON l.id = a.track_id WHERE a.type = 1').fetchall()
    con.close()
    rows, fills = {}, {}
    count = 0
    for aid, replaygain in ids:
        path = analysis / str(aid)
        if not path.is_file():
            continue
        c = columns(path)
        if c['all'].shape[0] < 708:
            continue
        count += 1
        heights, fill = styles(c, replaygain)
        for k, v in heights.items():
            v = v.ravel()
            rows.setdefault(k, []).append((np.quantile(v, .5), np.quantile(v, .99), (v >= 0.995).mean() * 100))
        for k, v in fill.items():
            fills.setdefault(k, []).append(v.mean() * 708)
    print(f'{count} analysed tracks, 4 visual frames per column, m_gain {G:.2f}')
    print('(the ratio row is a ratio, not a height; its edge columns mean ratio >= 0.995)')
    print(f'{"height (share of its space)":30s} {"p50":>6s} {"p99":>6s} {"p99 max":>8s} {"edge% med":>10s} {"edge% p90":>10s}')
    for k, v in rows.items():
        v = np.array(v)
        print(f'{k:30s} {np.median(v[:, 0]):6.2f} {np.median(v[:, 1]):6.2f} {v[:, 1].max():8.2f} '
              f'{np.median(v[:, 2]):10.2f} {np.quantile(v[:, 2], .9):10.2f}')
    print('\npixels filled per deck per frame (overdraw counted), median track')
    base = np.median(fills['today'])
    for k, v in fills.items():
        print(f'  {k:6s} {np.median(v):9.0f}  x{np.median(v) / base:4.2f}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
