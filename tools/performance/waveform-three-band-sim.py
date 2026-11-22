#!/usr/bin/env python3
"""Simulate the Decks page's main waveforms in three-band colour styles (R&D, 2026-11-22).

A SIMULATION, not a Mixxx render. Each style follows the code of the Mixxx
renderer it stands for (pinned Mixxx 3ebac449, src/waveform/renderers/allshader/
and res/shaders/), at the card's geometry: two 708 x 128 px rows (x 92..799,
y 48..175 and 176..303 of the 800 x 480 Decks page), four visual frames per
pixel column (fitted to the acceptance M screenshot 70-wf-1: the simulated
outline matches the card's best at 4 frames per column and the shown elapsed
time), the play marker at the centre.

Height: the main waveforms follow J13 and J15: m_gain = pregain x 0.80
(VisualGain_0 1). A renderer that asks for getGain(true) (Filtered, the
textured ones) gets 2 x m_gain, as stock Mixxx does.

Styles:
  rgb       allshader::WaveformRendererRGB (type 17), any three colours
  filtered  allshader::WaveformRendererFiltered (type 19; RGB Stacked, type 25,
            is the same with the SignalRGB colours; the enum's comment says 26,
            but the value follows 24): low, mid, high drawn over each other
  stack     MixPi idea: today's outline (filtered.all) split from the axis
            outward into low, mid and high in proportion to the band levels
  split     MixPi idea: bass above the axis, mids and highs below it (the
            larger of the two drawn behind, so both always show)
  lanes     MixPi idea: three lanes, high on top, low at the bottom, each a
            bar rising from its lane's floor
  tstacked  allshader::WaveformRendererTextured Stacked (type 24),
            res/shaders/stackedsignal.frag, 4x oversampled
  hsv       allshader::WaveformRendererHSV (type 21)

Needs numpy and Pillow. No library data lives in this repository: the
database, the analysis folder, the page screenshot and the track ids are
arguments, and the output names no track.

Usage:
  waveform-three-band-sim.py DB ANALYSIS_DIR PAGE_PNG OUT_DIR \
      --deck1 TRACK_ID:SECONDS --deck2 TRACK_ID:SECONDS [--styles a,b]
"""
import argparse
import importlib.util
import math
import sqlite3
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('waveform_bands', HERE / 'waveform_bands.py')
wb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wb)

ROW_X, ROW_W, ROW_H = 92, 708, 128
ROW_Y = (48, 176)
FRAMES_PER_PIXEL = 4  # fitted to the card's screenshot; see the docstring
MAIN_GAIN = 0.80          # J15 kMainWaveformGain (pregain 1)
AUDIO_FRAMES_PER_VISUAL = 100  # 44100 Hz / 441 visual frames per second
AXES = np.array([245, 245, 245]) / 255.0   # AxesColor default
BEAT_RGBA = (1.0, 1.0, 1.0, 0.9)  # BeatGridAlpha 90 % (the card's shot: 229 on black)
PLAYPOS_ALPHA = 0.375             # the card's shot: 2 px at 95 on black

QT_RGB = ('#ff0000', '#00ff00', '#0000ff')  # SignalRGB defaults (Pioneered sets none)
PIONEERED_FILTERED = ('#004ee4', '#c95a00', '#f6e9d3')  # Pioneered SignalLow/Mid/HighColor
TOKENS_3BAND = ('#5b95d4', '#d6784a', '#e4e7ec')  # tokens.css deck1, deck2, text


def hex_rgb(value):
    value = value.lstrip('#')
    return np.array([int(value[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64) / 255.0


# ---------------------------------------------------------------- data

def load_track(db, analysis, track_id):
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    row = con.execute(
        'SELECT a.id, IFNULL(l.replaygain, 0), l.beats, IFNULL(l.beats_version, ""), IFNULL(l.bpm, 0) '
        'FROM track_analysis a JOIN library l ON l.id = a.track_id '
        'WHERE a.type = 1 AND l.id = ?', (track_id,)).fetchone()
    con.close()
    if row is None:
        raise SystemExit(f'No waveform analysis for track {track_id}')
    analysis_id, replaygain, beats, beats_version, bpm = row
    data = wb.decode((Path(analysis) / str(analysis_id)).read_bytes())
    n = min(len(data[k]) for k in ('all', 'low', 'mid', 'high')) // 2 * 2
    signals = {k: np.array(data[k][:n], dtype=np.float64).reshape(-1, 2) for k in ('all', 'low', 'mid', 'high')}
    return {'signals': signals, 'rate': data['rate'] or 441.0, 'replaygain': replaygain,
            'beats': beat_frames(beats, beats_version, bpm)}


def beat_frames(blob, version, bpm):
    """Beat positions in audio frames (BeatMap-1.0 or BeatGrid-2.0 protobuf)."""
    if not blob:
        return []
    if version.startswith('BeatMap'):
        frames = []
        for number, wire, beat in wb.fields(blob):
            if number == 1 and wire == 2:
                for inner, inner_wire, value in wb.fields(beat):
                    if inner == 1 and inner_wire == 0:
                        frames.append(value if value < 2 ** 31 else value - 2 ** 32)
        return frames
    if version.startswith('BeatGrid'):
        first, grid_bpm = 0, bpm
        for number, wire, value in wb.fields(blob):
            if number == 1 and wire == 2:
                for inner, inner_wire, item in wb.fields(value):
                    if inner == 1 and inner_wire == 1:
                        grid_bpm = np.frombuffer(item, '<f8')[0]
            elif number == 2 and wire == 2:
                for inner, inner_wire, item in wb.fields(value):
                    if inner == 1 and inner_wire == 0:
                        first = item
        if grid_bpm <= 0:
            return []
        step = 44100 * 60.0 / grid_bpm
        return [first + i * step for i in range(int(4000 / step * 44100))]
    return []


def column_maxima(signals, play_frame, width=ROW_W):
    """Per pixel column and channel, the max of each signal over the column's
    visual frames (the loop in every allshader renderer). Returns dict of
    (width, 2) arrays; columns outside the track are zero."""
    total = signals['all'].shape[0]
    centre = width // 2
    out = {k: np.zeros((width, 2)) for k in signals}
    for col in range(width):
        x = play_frame + (col - centre) * FRAMES_PER_PIXEL
        start = int(round(x - FRAMES_PER_PIXEL / 2.0))
        stop = max(int(round(x + FRAMES_PER_PIXEL / 2.0)), start + 1)
        start, stop = max(start, 0), min(stop, total)
        if start >= stop:
            continue
        for k, values in signals.items():
            out[k][col] = values[start:stop].max(axis=0)
    return out


# ---------------------------------------------------------------- raster helpers

def fill_span(img, col, top, bottom, rgb, alpha=1.0):
    """Fill rows whose centre lies in [top, bottom) of one column (a GL rect)."""
    h = img.shape[0]
    r0 = max(int(math.ceil(top - 0.5)), 0)
    r1 = min(int(math.ceil(bottom - 0.5)), h)
    if r1 > r0:
        if alpha >= 1.0:
            img[r0:r1, col] = rgb
        else:
            img[r0:r1, col] = img[r0:r1, col] * (1 - alpha) + np.asarray(rgb) * alpha


def axis(img, rgb=AXES):
    half = img.shape[0] / 2.0
    fill_span(img, slice(None), half - 0.5, half + 0.5, rgb)


# ---------------------------------------------------------------- renderers

def render_rgb(cm, colors, m_gain, height=ROW_H):
    """allshader/waveformrendererrgb.cpp: height from filtered.all per channel,
    colour = sum(band x colour) over both channels, divided by its max part."""
    img = np.zeros((height, cm['all'].shape[0], 3))
    axis(img)
    half = height / 2.0
    hf = m_gain * half / 255.0  # getGain(false)
    lo, mi, hi = (hex_rgb(c) for c in colors)
    for col in range(img.shape[1]):
        l, m, h = cm['low'][col].max(), cm['mid'][col].max(), cm['high'][col].max()
        rgb = l * lo + m * mi + h * hi
        peak = rgb.max()
        rgb = rgb / peak if peak > 0 else rgb * 0
        fill_span(img, col, half - hf * cm['all'][col, 0], half + hf * cm['all'][col, 1], rgb)
    return img


def render_filtered(cm, colors, m_gain, compensation=True, height=ROW_H):
    """allshader/waveformrendererfiltered.cpp: low, then mid, then high, each an
    opaque mirrored bar at its own level (per channel); the axis drawn last."""
    img = np.zeros((height, cm['all'].shape[0], 3))
    half = height / 2.0
    hf = m_gain * (2.0 if compensation else 1.0) * half / 255.0
    for band, colour in zip(('low', 'mid', 'high'), colors):
        rgb = hex_rgb(colour)
        for col in range(img.shape[1]):
            fill_span(img, col, half - hf * cm[band][col, 0], half + hf * cm[band][col, 1], rgb)
    axis(img)
    return img


def render_stack(cm, colors, m_gain, height=ROW_H):
    """MixPi idea: the outline is exactly the RGB renderer's (filtered.all x
    m_gain); inside it, from the axis outward, low, mid and high take shares
    of the height in proportion to their levels (per channel)."""
    img = np.zeros((height, cm['all'].shape[0], 3))
    axis(img)
    half = height / 2.0
    hf = m_gain * half / 255.0
    rgbs = [hex_rgb(c) for c in colors]
    for col in range(img.shape[1]):
        for chn, sign in ((0, -1), (1, 1)):
            total = hf * cm['all'][col, chn]
            levels = np.array([cm['low'][col, chn], cm['mid'][col, chn], cm['high'][col, chn]])
            s = levels.sum()
            if total <= 0 or s <= 0:
                continue
            edge = 0.0
            for share, rgb in zip(levels / s, rgbs):
                a, b = edge, edge + total * share
                if sign < 0:
                    fill_span(img, col, half - b, half - a, rgb)
                else:
                    fill_span(img, col, half + a, half + b, rgb)
                edge = b
    return img


def render_split(cm, colors, m_gain, height=ROW_H):
    """MixPi idea: the low band rises above the axis, the mid and high bands
    hang below it (both channels merged by max). Below the axis the larger of
    mid and high is drawn first, so the smaller one always shows in front."""
    img = np.zeros((height, cm['all'].shape[0], 3))
    axis(img)
    half = height / 2.0
    hf = m_gain * half / 255.0
    lo, mi, hi = (hex_rgb(c) for c in colors)
    for col in range(img.shape[1]):
        fill_span(img, col, half - hf * cm['low'][col].max(), half, lo)
        m, h = cm['mid'][col].max(), cm['high'][col].max()
        for level, rgb in sorted(((m, mi), (h, hi)), key=lambda item: -item[0]):
            fill_span(img, col, half, half + hf * level, rgb)
    return img


def render_lanes(cm, colors, m_gain, height=ROW_H, gap=2):
    """MixPi idea: three lanes, high on top, mid, low at the bottom; each a
    bar rising from the lane's floor to m_gain x the band level (both
    channels merged by max), over a dim floor line."""
    img = np.zeros((height, cm['all'].shape[0], 3))
    lane = (height - 2 * gap) / 3.0
    for index, (band, colour) in enumerate((('high', colors[2]), ('mid', colors[1]), ('low', colors[0]))):
        top = index * (lane + gap)
        sub = img[int(round(top)):int(round(top + lane))]
        h = sub.shape[0]
        rgb = hex_rgb(colour)
        fill_span(sub, slice(None), h - 1, h, rgb * 0.35)
        hf = m_gain * h / 255.0
        for col in range(img.shape[1]):
            fill_span(sub, col, h - hf * cm[band][col].max(), h, rgb)
    return img


def render_hsv(cm, low_colour, m_gain, height=ROW_H):
    """allshader/waveformrendererhsv.cpp: hue of SignalLowColor, saturation
    1 - high share, value 1 - low share; height from filtered.all."""
    import colorsys
    img = np.zeros((height, cm['all'].shape[0], 3))
    axis(img)
    half = height / 2.0
    hf = m_gain * half / 255.0
    hue = colorsys.rgb_to_hsv(*hex_rgb(low_colour))[0]
    for col in range(img.shape[1]):
        lo, hi = 0.0, 0.0
        if cm['all'][col, 0] and cm['all'][col, 1]:
            total = (cm['low'][col].sum() + cm['mid'][col].sum() + cm['high'][col].sum()) * 1.2
            if total:
                lo = cm['low'][col].sum() / total
                hi = cm['high'][col].sum() / total
        rgb = np.array(colorsys.hsv_to_rgb(hue, 1 - hi, 1 - lo))
        fill_span(img, col, half - hf * cm['all'][col, 0], half + hf * cm['all'][col, 1], rgb)
    return img


def render_textured_stacked(signals, play_frame, colors, m_gain, width=ROW_W, height=ROW_H):
    """res/shaders/stackedsignal.frag in a 4x framebuffer, box-filtered down.
    One visual frame per fragment column (no max), allGain = 2 x m_gain."""
    over = 4
    W, H = width * over, height * over
    first = play_frame - (width / 2) * FRAMES_PER_PIXEL
    u = (np.arange(W) + 0.5) / W
    idx = np.floor(first + u * width * FRAMES_PER_PIXEL).astype(int)
    total = signals['all'].shape[0]
    valid = (idx >= 0) & (idx < total)
    idx_c = np.clip(idx, 0, total - 1)
    gain = 2.0 * m_gain
    lo_c, mi_c, hi_c = (hex_rgb(c) for c in colors)
    out = np.zeros((H, W, 4))
    ys = (np.arange(H) + 0.5) / H  # 0 at the top
    for row in range(H):
        # Screen top is uv.y = 1 (GL), the left channel.
        uv_y = 1.0 - ys[row]
        chn = 1 if uv_y < 0.5 else 0
        d = {k: signals[k][idx_c, chn] / 255.0 * gain for k in ('low', 'mid', 'high')}
        sf = 1.0 / math.sqrt(3.0)
        l, m, h = d['low'] * sf, d['mid'] * sf, d['high'] * sf
        dist = abs((uv_y - 0.5) * 2.0)
        colour = np.zeros((W, 3))
        showing = np.zeros(W, bool)
        a = dist <= l
        b = (~a) & (dist <= l + m)
        c = (~a) & (~b) & (dist <= l + m + h)
        colour[a], colour[b], colour[c] = lo_c, mi_c, hi_c
        showing = (a | b | c) & valid
        mix = l[:, None] * lo_c + m[:, None] * mi_c + h[:, None] * hi_c
        peak = mix.max(axis=1, keepdims=True)
        mix = np.divide(mix, peak, out=np.zeros_like(mix), where=peak > 0)
        px = np.zeros((W, 3))
        alpha = np.zeros(W)
        if abs(H / 2 - (H - row - 0.5)) <= 4:
            px[:] = AXES
            alpha[:] = 1.0
        shown = px * 0.25 + colour * 0.75
        shown = shown * 0.47 + mix * 0.53
        px[showing] = shown[showing]
        alpha[showing] = 1.0
        out[row, :, :3] = px * alpha[:, None]
        out[row, :, 3] = alpha
    small = out.reshape(height, over, width, over, 4).mean(axis=(1, 3))
    return small[..., :3]  # premultiplied over black


# ---------------------------------------------------------------- page

def overlay_marks(img, track, play_frame):
    """WaveformRenderBeat (BeatColor, 1 px) and the play marker (PlayPosColor)."""
    centre = ROW_W // 2
    r, g, b, a = BEAT_RGBA
    for frame in track['beats']:
        col = int(round(centre + (frame / AUDIO_FRAMES_PER_VISUAL - play_frame) / FRAMES_PER_PIXEL))
        if 0 <= col < img.shape[1]:
            img[:, col] = img[:, col] * (1 - a) + np.array([r, g, b]) * a
    for col in (centre - 1, centre):
        img[:, col] = img[:, col] * (1 - PLAYPOS_ALPHA) + PLAYPOS_ALPHA
    return img


STYLES = {
    'today-j15': ('Today with J15: RGB (type 17), stock red/green/blue', lambda cm, s, pf: render_rgb(cm, QT_RGB, MAIN_GAIN)),
    'build-m': ('Build M (J13, gain 1.0): RGB, stock red/green/blue', lambda cm, s, pf: render_rgb(cm, QT_RGB, 1.0)),
    'A-overlay': ('A Overlay: Filtered (type 19), height-matched', lambda cm, s, pf: render_filtered(cm, TOKENS_3BAND, MAIN_GAIN, compensation=False)),
    'A-overlay-stock-height': ('A Overlay at stock height (x2): clips', lambda cm, s, pf: render_filtered(cm, TOKENS_3BAND, MAIN_GAIN, compensation=True)),
    'A-overlay-pioneered': ('Filtered with Pioneered colours, height-matched', lambda cm, s, pf: render_filtered(cm, PIONEERED_FILTERED, MAIN_GAIN, compensation=False)),
    'B-stack': ('B Stack: today\'s outline split into bands (patch)', lambda cm, s, pf: render_stack(cm, TOKENS_3BAND, MAIN_GAIN)),
    'rgb-recolour': ('Dropped: RGB (type 17) with three-band colours', lambda cm, s, pf: render_rgb(cm, TOKENS_3BAND, MAIN_GAIN)),
    'C-split': ('C Split: bass up, mids and highs down (patch)', lambda cm, s, pf: render_split(cm, TOKENS_3BAND, MAIN_GAIN)),
    'D-lanes': ('D Lanes: one lane per band (patch)', lambda cm, s, pf: render_lanes(cm, TOKENS_3BAND, MAIN_GAIN)),
    'stock-25-rgbstacked': ('Stock type 25 (RGB Stacked): Filtered with SignalRGB red/green/blue', lambda cm, s, pf: render_filtered(cm, QT_RGB, MAIN_GAIN, compensation=True)),
    'stock-24-tstacked': ('Stock type 24: textured Stacked, three-band colours', lambda cm, s, pf: render_textured_stacked(s, pf, TOKENS_3BAND, MAIN_GAIN)),
    'stock-21-hsv': ('Stock type 21: HSV, Pioneered low colour', lambda cm, s, pf: render_hsv(cm, PIONEERED_FILTERED[0], MAIN_GAIN)),
}


def to_u8(img):
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def font(size):
    for path in ('/System/Library/Fonts/Supplemental/Arial.ttf', '/System/Library/Fonts/Helvetica.ttc',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def page(base, rows):
    """The Decks page screenshot with both main rows replaced and the track
    names masked (no track is named in an output)."""
    im = base.copy().convert('RGB')
    for y, rgb in zip(ROW_Y, rows):
        im.paste(Image.fromarray(to_u8(rgb)), (ROW_X, y))
    draw = ImageDraw.Draw(im)
    surface = (22, 26, 32)
    f = font(15)
    for x0, x1, text in ((28, 355, 'Track A'), (428, 757, 'Track B')):
        draw.rectangle((x0, 307, x1, 328), fill=surface)
        draw.text((x0 + 4, 309), text, fill=(148, 157, 171), font=f)
    return im


LABEL_H = 30
LABEL_BG, LABEL_SIM, LABEL_TEXT = (36, 40, 46), (236, 190, 90), (228, 231, 236)


def labelled(im, title):
    """The page under a strip that says SIMULATION and the style."""
    out = Image.new('RGB', (im.width, im.height + LABEL_H), LABEL_BG)
    out.paste(im, (0, LABEL_H))
    draw = ImageDraw.Draw(out)
    bold, regular = font(15), font(15)
    draw.text((8, 7), 'SIMULATION', fill=LABEL_SIM, font=bold)
    draw.text((8 + draw.textlength('SIMULATION', font=bold) + 10, 7), title, fill=LABEL_TEXT, font=regular)
    return out


def grid(images, columns=2, gap=12, background=(14, 16, 20)):
    w, h = images[0].size
    rows = (len(images) + columns - 1) // columns
    out = Image.new('RGB', (columns * w + (columns + 1) * gap, rows * h + (rows + 1) * gap), background)
    for index, im in enumerate(images):
        r, c = divmod(index, columns)
        out.paste(im, (gap + c * (w + gap), gap + r * (h + gap)))
    return out


def rows_only(decks, key):
    """Both main rows of one style, 708 x 256, under its label (no page chrome)."""
    title, fn = STYLES[key]
    im = Image.new('RGB', (ROW_W, 2 * ROW_H + 2), (44, 51, 61))
    for index, (track, pf, cm) in enumerate(decks):
        rgb = overlay_marks(fn(cm, track['signals'], pf), track, pf)
        im.paste(Image.fromarray(to_u8(rgb)), (0, index * (ROW_H + 2)))
    return labelled(im, title)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('db')
    parser.add_argument('analysis')
    parser.add_argument('page_png')
    parser.add_argument('out_dir', type=Path)
    parser.add_argument('--deck1', required=True)
    parser.add_argument('--deck2', required=True)
    parser.add_argument('--styles', default=','.join(STYLES))
    parser.add_argument('--sheet', action='append', default=[], metavar='NAME:STYLE,STYLE',
                        help='also write NAME.png: the labelled pages of these styles, two per row')
    parser.add_argument('--rows-sheet', action='append', default=[], metavar='NAME:STYLE,STYLE',
                        help='also write NAME.png: only the two main rows of each style')
    parser.add_argument('--prefix', default='')
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    base = Image.open(args.page_png)
    decks = []
    for spec in (args.deck1, args.deck2):
        track_id, seconds = spec.split(':')
        track = load_track(args.db, args.analysis, int(track_id))
        play_frame = float(seconds) * track['rate']
        decks.append((track, play_frame, column_maxima(track['signals'], play_frame)))
    pages = {}
    wanted = [k for k in args.styles.split(',') if k]
    for spec in args.sheet:
        wanted += [k for k in spec.split(':', 1)[1].split(',') if k not in wanted]
    for key in wanted:
        title, fn = STYLES[key]
        rows = [overlay_marks(fn(cm, track['signals'], pf), track, pf) for track, pf, cm in decks]
        pages[key] = labelled(page(base, rows), title)
        if key in args.styles.split(','):
            path = args.out_dir / f'{args.prefix}{key}.png'
            pages[key].save(path)
            print(key, '->', path)
    for spec in args.sheet:
        name, keys = spec.split(':', 1)
        grid([pages[k] for k in keys.split(',')]).save(args.out_dir / f'{name}.png')
        print(name, '->', args.out_dir / f'{name}.png')
    for spec in args.rows_sheet:
        name, keys = spec.split(':', 1)
        grid([rows_only(decks, k) for k in keys.split(',')]).save(args.out_dir / f'{name}.png')
        print(name, '->', args.out_dir / f'{name}.png')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
