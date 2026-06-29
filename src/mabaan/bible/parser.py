"""
Parse a Mabaan Bible file into searchable verse objects.

Supported input formats:
  1. CSV  — columns: book, chapter, verse, mabaan_text, english_text (optional)
  2. TSV  — same columns, tab-separated
  3. USFM — standard Bible markup (\id, \c N, \v N text)
  4. Parallel TXT — alternating lines: mabaan / english (pairs)

Run:  mabaan bible import data/bible/mabaan_bible.csv
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


class ParseError(Exception):
    pass


def parse(path: Path) -> list[dict[str, Any]]:
    """Dispatch to the correct parser by file extension."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _parse_delimited(path, delimiter=",")
    if suffix == ".tsv":
        return _parse_delimited(path, delimiter="\t")
    if suffix in (".usfm", ".sfm", ".ptx"):
        return _parse_usfm(path)
    if suffix == ".txt":
        return _parse_txt(path)
    raise ParseError(f"Unsupported Bible file format: {suffix}. Use .csv, .tsv, .usfm, or .txt")


def _parse_delimited(path: Path, delimiter: str) -> list[dict[str, Any]]:
    verses: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for i, row in enumerate(reader):
            row = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
            book    = row.get("book", "UNK")
            chapter = row.get("chapter", "0")
            verse   = row.get("verse", str(i + 1))
            mabaan  = row.get("mabaan_text") or row.get("mabaan") or row.get("text", "")
            english = row.get("english_text") or row.get("english") or row.get("en", "")
            if not mabaan:
                continue
            verses.append({
                "id": f"{book}.{chapter}.{verse}",
                "book": book,
                "chapter": int(chapter) if chapter.isdigit() else 0,
                "verse": int(verse) if verse.isdigit() else i + 1,
                "mabaan": mabaan,
                "english": english,
            })
    return verses


def _parse_usfm(path: Path) -> list[dict[str, Any]]:
    """Parse USFM markers: \id, \c N, \v N text..."""
    verses: list[dict[str, Any]] = []
    book = "UNK"
    chapter = 0
    text = path.read_text(encoding="utf-8")

    id_match = re.search(r"\\id\s+(\w+)", text)
    if id_match:
        book = id_match.group(1)

    chapter_re = re.compile(r"\\c\s+(\d+)")
    verse_re   = re.compile(r"\\v\s+(\d+)\s+(.*?)(?=\\v\s|\Z)", re.DOTALL)
    marker_re  = re.compile(r"\\\w+\*?\s*")

    for c_match in chapter_re.finditer(text):
        chapter = int(c_match.group(1))
        chunk_start = c_match.end()
        next_chapter = chapter_re.search(text, chunk_start)
        chunk = text[chunk_start: next_chapter.start() if next_chapter else len(text)]
        for v_match in verse_re.finditer(chunk):
            v_num = int(v_match.group(1))
            raw   = v_match.group(2).strip()
            clean = marker_re.sub("", raw).strip()
            if not clean:
                continue
            verses.append({
                "id": f"{book}.{chapter}.{v_num}",
                "book": book,
                "chapter": chapter,
                "verse": v_num,
                "mabaan": clean,
                "english": "",
            })
    return verses


def _parse_txt(path: Path) -> list[dict[str, Any]]:
    """
    Alternating-line format:
      Line 1: Mabaan text
      Line 2: English translation (optional — if missing, alternate detection is skipped)
    """
    lines = [l.rstrip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    verses: list[dict[str, Any]] = []

    # Detect paired format (even total lines, interleaved mabaan/english)
    # Simple heuristic: if lines alternate between scripts/languages
    if len(lines) % 2 == 0:
        for i in range(0, len(lines), 2):
            verses.append({
                "id": f"TXT.1.{i // 2 + 1}",
                "book": "TXT",
                "chapter": 1,
                "verse": i // 2 + 1,
                "mabaan": lines[i],
                "english": lines[i + 1],
            })
    else:
        for i, line in enumerate(lines):
            verses.append({
                "id": f"TXT.1.{i + 1}",
                "book": "TXT",
                "chapter": 1,
                "verse": i + 1,
                "mabaan": line,
                "english": "",
            })
    return verses


def save(verses: list[dict[str, Any]], out_path: Path) -> None:
    out_path.write_text(
        json.dumps({"count": len(verses), "verses": verses}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
