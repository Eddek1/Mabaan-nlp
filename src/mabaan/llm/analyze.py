"""
Language analysis functions — every call retrieves relevant Bible passages
and injects them as grounding context before asking Claude to process.
"""

from __future__ import annotations

import json
from typing import Any

from mabaan.llm.client import call_json

_bible_available = True

def _get_context(query: str, top_k: int = 6) -> str:
    global _bible_available
    if not _bible_available:
        return "(Bible index not loaded — install it with: mabaan bible import <file>)"
    try:
        from mabaan.bible.store import get_store
        return get_store().get_context_block(query, top_k)
    except FileNotFoundError:
        _bible_available = False
        return "(Bible index not loaded — install it with: mabaan bible import <file>)"


def gloss_entries(entries: list[str]) -> dict[str, Any]:
    context = _get_context(" ".join(entries))
    payload = json.dumps({"task": "GLOSS", "items": entries}, ensure_ascii=False)
    prompt = f"""
{context}

Using only the passages above as linguistic evidence, process task: GLOSS.

For each item produce:
{{
  "id": <index>,
  "source": "<original form>",
  "morphemes": ["<m1>", "<m2>", ...],
  "glosses":   ["<g1>", "<g2>", ...],
  "free_translation": "<English translation>",
  "tone_pattern": "<H/L/F/R sequence or null>",
  "evidence_verse_ids": ["<verse_id>", ...],
  "confidence": "high|medium|low",
  "status": "ok|error",
  "notes": "<explain low confidence or missing evidence>"
}}

Input batch:
{payload}
"""
    return call_json(prompt)


def extract_lexicon_entries(raw_notes: list[str]) -> dict[str, Any]:
    context = _get_context(" ".join(raw_notes))
    payload = json.dumps({"task": "LEXICON_ENTRY", "items": raw_notes}, ensure_ascii=False)
    prompt = f"""
{context}

Using only the passages above as linguistic evidence, process task: LEXICON_ENTRY.

For each item produce:
{{
  "id": <index>,
  "headword": "<canonical Mabaan form>",
  "pos": "<noun|verb|adj|adv|...>",
  "gloss_en": "<English gloss>",
  "gloss_ar": "<Arabic gloss if derivable, else null>",
  "example_sentence": "<attested example from Bible passages or null>",
  "example_verse_id": "<verse ID of example or null>",
  "semantic_domain": "<domain label>",
  "evidence_verse_ids": ["<verse_id>", ...],
  "confidence": "high|medium|low",
  "status": "ok|error",
  "notes": "<optional>"
}}

Input batch:
{payload}
"""
    return call_json(prompt)


def normalize_orthography(forms: list[str]) -> dict[str, Any]:
    context = _get_context(" ".join(forms))
    payload = json.dumps({"task": "NORMALIZE", "items": forms}, ensure_ascii=False)
    prompt = f"""
{context}

Using attested spellings in the passages above as the canonical reference,
process task: NORMALIZE.

For each item produce:
{{
  "id": <index>,
  "original": "<input form>",
  "normalized": "<form as it appears in attested passages, or best estimate>",
  "attested_in": "<verse ID where the normalized form appears, or null>",
  "changes": ["<change description>", ...],
  "confidence": "high|medium|low",
  "status": "ok|error"
}}

Input batch:
{payload}
"""
    return call_json(prompt)


def validate_igt(igt_entries: list[dict[str, str]]) -> dict[str, Any]:
    context = _get_context(" ".join(e.get("line1", "") for e in igt_entries))
    payload = json.dumps({"task": "VALIDATE", "items": igt_entries}, ensure_ascii=False)
    prompt = f"""
{context}

Using the passages above as reference, process task: VALIDATE.

For each IGT entry (line1=surface, line2=gloss, line3=translation) check:
- Morpheme count matches gloss count (alignment)
- Glosses use Leipzig conventions
- Translation is consistent with glosses and attested passage meanings

For each item produce:
{{
  "id": <index>,
  "valid": true|false,
  "alignment_ok": true|false,
  "gloss_issues": ["<issue>", ...],
  "suggested_corrections": {{}},
  "evidence_verse_ids": ["<verse_id>", ...],
  "confidence": "high|medium|low",
  "status": "ok|error"
}}

Input batch:
{payload}
"""
    return call_json(prompt)


def translate_entries(entries: list[str]) -> dict[str, Any]:
    context = _get_context(" ".join(entries))
    payload = json.dumps({"task": "TRANSLATE", "items": entries}, ensure_ascii=False)
    prompt = f"""
{context}

Using only the passages above as evidence, process task: TRANSLATE.

For each item produce:
{{
  "id": <index>,
  "source": "<Mabaan text>",
  "translation": "<English translation>",
  "evidence_verse_ids": ["<verse_id>", ...],
  "confidence": "high|medium|low",
  "status": "ok|error",
  "notes": "<explain if translation is uncertain>"
}}

Input batch:
{payload}
"""
    return call_json(prompt)


def summarize_corpus(sample_entries: list[str], corpus_name: str = "Mabaan corpus") -> dict[str, Any]:
    context = _get_context(" ".join(sample_entries[:30]))
    payload = json.dumps(
        {"task": "SUMMARIZE", "corpus": corpus_name, "sample": sample_entries[:50]},
        ensure_ascii=False,
    )
    prompt = f"""
{context}

Using the Bible passages above alongside the sample corpus below,
process task: SUMMARIZE.

Produce a single object:
{{
  "task": "SUMMARIZE",
  "corpus": "<corpus name>",
  "entry_count_sampled": N,
  "phonological_observations": ["..."],
  "morphological_observations": ["..."],
  "semantic_domains_detected": ["..."],
  "data_quality_notes": ["..."],
  "bible_coverage": "<how well Bible passages covered the sample vocabulary>",
  "recommended_next_steps": ["..."]
}}

Input:
{payload}
"""
    return call_json(prompt)
