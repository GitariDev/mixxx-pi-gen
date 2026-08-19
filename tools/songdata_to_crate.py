#!/usr/bin/env python3
"""Convert a SongData.io playlist PDF export into a clean crate PDF and JSON."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

import pdfplumber
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle


def _join(words: list[dict]) -> str:
    ordered = sorted(words, key=lambda word: (round(word["top"], 1), word["x0"]))
    text = " ".join(word["text"] for word in ordered)
    return re.sub(r"\s+([,.)])", r"\1", re.sub(r"([(])\s+", r"\1", text)).strip()


def extract_songdata(pdf_path: Path) -> dict:
    tracks: list[dict] = []
    playlist_name = pdf_path.stem.replace(" Playlist _ SongData.io", "")
    spotify_id = ""

    with pdfplumber.open(pdf_path) as pdf:
        all_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        id_match = re.search(r"songdata\.io/playlist/([A-Za-z0-9]+)", all_text)
        if id_match:
            spotify_id = id_match.group(1)

        for page_index, page in enumerate(pdf.pages):
            words = page.extract_words()
            anchors = [
                word for word in words
                if 238 <= word["x0"] <= 252
                and word["text"].isdigit()
                and word["top"] < 820
                and (page_index > 0 or word["top"] > 155)
            ]
            anchors.sort(key=lambda word: word["top"])
            for index, anchor in enumerate(anchors):
                previous_top = anchors[index - 1]["top"] if index else (145 if page_index == 0 else 20)
                next_top = anchors[index + 1]["top"] if index + 1 < len(anchors) else min(825, anchor["top"] + 24)
                low = (previous_top + anchor["top"]) / 2
                high = (anchor["top"] + next_top) / 2
                row = [word for word in words if low <= word["top"] < high and word["x0"] >= 270]

                def column(left: float, right: float) -> str:
                    return _join([word for word in row if left <= word["x0"] < right])

                key = column(394, 421)
                track = {
                    "crate_position": len(tracks) + 1,
                    "playlist_position": int(anchor["text"]),
                    "track": column(270, 340),
                    "artist": column(340, 394),
                    "key": key,
                    "camelot": column(421, 444),
                    "bpm": int(column(444, 470)),
                    "energy": int(column(470, 492)),
                }
                if track["track"] and track["artist"] and track["camelot"]:
                    tracks.append(track)

    positions = [track["playlist_position"] for track in tracks]
    expected = set(range(1, max(positions, default=0) + 1))
    if len(positions) != len(set(positions)) or set(positions) != expected:
        missing = sorted(expected - set(positions))
        raise ValueError(f"Incomplete or duplicate playlist extraction; missing positions: {missing}")

    return {
        "name": playlist_name,
        "source": f'Spotify playlist "{playlist_name}" via SongData.io',
        "spotify_id": spotify_id,
        "exported": date.today().isoformat(),
        "order": "Harmonic (SongData display order); mix-compatible Camelot keys sit together.",
        "tracks": tracks,
    }


def write_pdf(crate: dict, output_path: Path) -> None:
    font_path = Path("/Users/gitaritirima/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/poppler/fonts/DejaVuSans.ttf")
    if not font_path.exists():
        font_path = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
    body_font = "Helvetica"
    if font_path.exists():
        pdfmetrics.registerFont(TTFont("CrateUnicode", str(font_path)))
        body_font = "CrateUnicode"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=f'Crate: {crate["name"]}', author="Codex playlist-building skill",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("CrateTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=19, leading=23, alignment=TA_LEFT, spaceAfter=5)
    meta = ParagraphStyle("Meta", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=colors.HexColor("#384150"))
    cell = ParagraphStyle("Cell", parent=styles["BodyText"], fontName=body_font, fontSize=7.4, leading=9)
    cell_bold = ParagraphStyle("CellBold", parent=cell, fontName="Helvetica-Bold")

    story = [
        Paragraph(f'Crate: {crate["name"]}', title),
        Paragraph(f'{crate["source"]} - {len(crate["tracks"])} tracks - exported {crate["exported"]}.', meta),
        Paragraph(f'Order: {crate["order"]} En = energy 1-10. Pl# = original playlist position.', meta),
        Spacer(1, 5 * mm),
    ]
    rows = [[Paragraph(label, cell_bold) for label in ("#", "Track", "Artist", "Key", "Cam", "BPM", "En", "Pl#")]]
    for item in crate["tracks"]:
        rows.append([
            Paragraph(str(item["crate_position"]), cell), Paragraph(item["track"], cell),
            Paragraph(item["artist"], cell), Paragraph(item["key"], cell),
            Paragraph(item["camelot"], cell), Paragraph(str(item["bpm"]), cell),
            Paragraph(str(item["energy"]), cell), Paragraph(str(item["playlist_position"]), cell),
        ])
    table = LongTable(rows, repeatRows=1, colWidths=[8*mm, 52*mm, 46*mm, 20*mm, 14*mm, 15*mm, 10*mm, 12*mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#20252B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F4F5")]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#20252B")),
    ]))
    story.append(table)
    doc.build(story)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output_pdf", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    crate = extract_songdata(args.input_pdf)
    write_pdf(crate, args.output_pdf)
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(crate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f'Created {args.output_pdf} with {len(crate["tracks"])} tracks')


if __name__ == "__main__":
    main()
