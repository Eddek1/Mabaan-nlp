"""
Corpus store: append processed results into a growing lexicon / corpus JSON.
Supports deduplication by headword and merging updates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mabaan.config import DATA_LEXICON


class CorpusStore:
    def __init__(self, name: str = "mabaan_lexicon") -> None:
        self.path = DATA_LEXICON / f"{name}.json"
        self._data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"entries": {}, "meta": {"total": 0, "last_updated": ""}}

    def _save(self) -> None:
        import datetime
        self._data["meta"]["total"] = len(self._data["entries"])
        self._data["meta"]["last_updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upsert(self, entry: dict[str, Any]) -> None:
        """Insert or update a lexicon entry keyed by headword."""
        key = entry.get("headword") or entry.get("source") or entry.get("text", "")
        if not key:
            return
        if key in self._data["entries"]:
            self._data["entries"][key].update(entry)
        else:
            self._data["entries"][key] = entry

    def bulk_upsert(self, entries: list[dict[str, Any]]) -> int:
        before = len(self._data["entries"])
        for e in entries:
            self.upsert(e)
        self._save()
        return len(self._data["entries"]) - before

    def search(self, query: str) -> list[dict[str, Any]]:
        q = query.lower()
        return [
            e for e in self._data["entries"].values()
            if q in json.dumps(e, ensure_ascii=False).lower()
        ]

    def export_csv(self, output_path: Path | None = None) -> Path:
        import csv
        entries = list(self._data["entries"].values())
        out = output_path or DATA_LEXICON / "mabaan_lexicon.csv"
        if not entries:
            out.write_text("", encoding="utf-8")
            return out
        fieldnames = sorted({k for e in entries for k in e})
        with out.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(entries)
        return out

    def __len__(self) -> int:
        return len(self._data["entries"])
