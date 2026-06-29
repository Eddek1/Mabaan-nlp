"""
Searchable Bible verse store used as the RAG knowledge base.

Claude doesn't know Mabaan — we ground every LLM call with retrieved
Bible passages so Claude reasons from real evidence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mabaan.config import DATA_BIBLE

_INDEX_PATH = DATA_BIBLE / "index.json"
_store: "BibleStore | None" = None


class BibleStore:
    def __init__(self, path: Path = _INDEX_PATH) -> None:
        if not path.exists():
            raise FileNotFoundError(
                f"Bible index not found at {path}. "
                "Run: mabaan bible import <your_bible_file>"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        self.verses: list[dict[str, Any]] = data["verses"]
        self._tokens: list[set[str]] = [_tokenize(v["mabaan"]) for v in self.verses]

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Return the top_k verses most lexically similar to query."""
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        scored = [
            (len(q_tokens & v_tokens) / max(len(q_tokens | v_tokens), 1), i)
            for i, v_tokens in enumerate(self._tokens)
        ]
        scored.sort(reverse=True)
        return [self.verses[i] for score, i in scored[:top_k] if score > 0]

    def get_context_block(self, query: str, top_k: int = 5) -> str:
        """
        Return a formatted context block of retrieved verses,
        ready to inject into an LLM prompt.
        """
        hits = self.search(query, top_k)
        if not hits:
            return "(No matching Bible passages found for this query.)"
        lines = ["Relevant Mabaan Bible passages (use these as linguistic evidence):"]
        for v in hits:
            ref = v["id"]
            mab = v["mabaan"]
            eng = f'  [{v["english"]}]' if v.get("english") else ""
            lines.append(f"  {ref}: {mab}{eng}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.verses)


def get_store() -> BibleStore:
    """Lazy singleton — loads once, reused across calls."""
    global _store
    if _store is None:
        _store = BibleStore()
    return _store


def reset_store() -> None:
    """Force reload (e.g. after import)."""
    global _store
    _store = None


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\wɐ-ʯ̀-ͯḀ-ỿ]+", text.lower()))
