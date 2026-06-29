"""
Data ingestion layer: read raw files into normalized Python dicts
before they enter the LLM processing pipeline.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from mabaan.config import SUPPORTED_EXTENSIONS


class IngestionError(Exception):
    pass


def load_file(path: Path) -> list[dict[str, Any]]:
    """Route a file to the correct loader by extension."""
    if path.suffix not in SUPPORTED_EXTENSIONS:
        raise IngestionError(f"Unsupported file type: {path.suffix}. Supported: {SUPPORTED_EXTENSIONS}")

    loaders = {
        ".txt": _load_txt,
        ".csv": _load_csv,
        ".tsv": _load_tsv,
        ".json": _load_json,
    }
    return loaders[path.suffix](path)


def _load_txt(path: Path) -> list[dict[str, Any]]:
    """
    Plain text: one entry per non-empty line.
    IGT blocks of 3 consecutive lines are auto-detected.
    """
    lines = [l.rstrip() for l in path.read_text(encoding="utf-8").splitlines()]
    non_empty = [l for l in lines if l]

    # Detect IGT blocks (groups of 3)
    if len(non_empty) % 3 == 0:
        it = iter(non_empty)
        return [
            {"line1": a, "line2": b, "line3": c, "_source": str(path)}
            for a, b, c in zip(it, it, it)
        ]

    return [{"text": l, "_source": str(path)} for l in non_empty]


def _load_csv(path: Path) -> list[dict[str, Any]]:
    return _load_delimited(path, delimiter=",")


def _load_tsv(path: Path) -> list[dict[str, Any]]:
    return _load_delimited(path, delimiter="\t")


def _load_delimited(path: Path, delimiter: str) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return [
            {k: (v or "") for k, v in row.items()} | {"_source": str(path)}
            for row in reader
        ]


def _load_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        for item in data:
            item.setdefault("_source", str(path))
        return data
    if isinstance(data, dict) and "entries" in data:
        for item in data["entries"]:
            item.setdefault("_source", str(path))
        return data["entries"]
    raise IngestionError(f"JSON must be a list or {{entries: []}}. Got: {type(data)}")


def load_directory(directory: Path) -> list[dict[str, Any]]:
    """Load all supported files from a directory (non-recursive)."""
    all_entries: list[dict[str, Any]] = []
    for f in sorted(directory.iterdir()):
        if f.is_file() and f.suffix in SUPPORTED_EXTENSIONS:
            all_entries.extend(load_file(f))
    return all_entries
