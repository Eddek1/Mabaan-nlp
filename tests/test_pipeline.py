"""
Unit tests for the ingest and corpus layers (no LLM calls required).
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from mabaan.pipeline.ingest import load_file, IngestionError
from mabaan.corpus.store import CorpusStore
from mabaan.config import DATA_LEXICON


# --- Ingest tests ---

def _write(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.write_text(content, encoding="utf-8")
    return p


def test_load_txt_plain(tmp_path):
    # 4 lines — not divisible by 3, so IGT detection is skipped
    f = _write(tmp_path, "words.txt", "àbùr\nwɛ́l\nkɛ̀r\nɗùmù\n")
    entries = load_file(f)
    assert len(entries) == 4
    assert entries[0]["text"] == "àbùr"


def test_load_txt_igt(tmp_path):
    content = "màbáán kɛ̀r àbùr\nMabaan PST water\nThe Mabaan fetched water.\n"
    f = _write(tmp_path, "igt.txt", content)
    entries = load_file(f)
    assert len(entries) == 1
    assert "line1" in entries[0]
    assert "line2" in entries[0]
    assert "line3" in entries[0]


def test_load_csv(tmp_path):
    content = "form,gloss\nàbùr,water\nwɛ́l,man\n"
    f = _write(tmp_path, "lex.csv", content)
    entries = load_file(f)
    assert len(entries) == 2
    assert entries[0]["form"] == "àbùr"


def test_load_json_list(tmp_path):
    data = [{"headword": "àbùr", "gloss": "water"}]
    f = _write(tmp_path, "data.json", json.dumps(data))
    entries = load_file(f)
    assert entries[0]["headword"] == "àbùr"


def test_load_json_entries_key(tmp_path):
    data = {"entries": [{"headword": "wɛ́l"}]}
    f = _write(tmp_path, "data.json", json.dumps(data))
    entries = load_file(f)
    assert entries[0]["headword"] == "wɛ́l"


def test_unsupported_extension(tmp_path):
    f = _write(tmp_path, "data.xml", "<root/>")
    with pytest.raises(IngestionError):
        load_file(f)


# --- Corpus store tests ---

def test_corpus_upsert_and_search(tmp_path, monkeypatch):
    monkeypatch.setattr("mabaan.corpus.store.DATA_LEXICON", tmp_path)
    store = CorpusStore("test_lexicon")
    store.upsert({"headword": "àbùr", "gloss_en": "water", "pos": "noun"})
    store.upsert({"headword": "wɛ́l", "gloss_en": "man", "pos": "noun"})
    store._save()

    assert len(store) == 2
    results = store.search("water")
    assert any(r["headword"] == "àbùr" for r in results)


def test_corpus_deduplication(tmp_path, monkeypatch):
    monkeypatch.setattr("mabaan.corpus.store.DATA_LEXICON", tmp_path)
    store = CorpusStore("test_dedup")
    store.upsert({"headword": "àbùr", "gloss_en": "water"})
    store.upsert({"headword": "àbùr", "gloss_en": "water (updated)"})
    assert len(store) == 1
    assert store._data["entries"]["àbùr"]["gloss_en"] == "water (updated)"
