# Mabaan NLP Pipeline

An NLP pipeline for documenting **Mabaan**, a low-resource Nilo-Saharan language spoken in South Sudan. The system uses retrieval-augmented generation (RAG) grounded in a Mabaan Bible corpus to assist linguists with glossing, lexicon building, and annotation — with a built-in human review workflow.

## The problem

Mabaan has almost no digital linguistic resources. Documenting it requires linguists to manually gloss words, build a lexicon, and validate annotations — a slow and expensive process. This pipeline automates the bottleneck using an LLM, but keeps linguists in control through a human-in-the-loop review step.

## How it works

```
Raw field data (txt / csv / tsv / json)
        |
        v
   Ingestion layer
   Normalizes any supported format into structured Python dicts
        |
        v
   Bible RAG retrieval
   Fetches the most relevant Mabaan Bible verses as linguistic evidence
        |
        v
   LLM analysis (Claude)
   Glosses, translates, normalizes, or validates — grounded in attested text only
        |
        v
   Human review queue
   Linguists approve, reject, or correct each AI-generated entry
        |
        v
   Approved lexicon export
```

The key design principle: **Claude has no prior knowledge of Mabaan**. Every prompt injects retrieved Bible passages as the only allowed evidence source. If the model cannot ground a claim in an attested verse, it must say so and mark confidence as "low".

## Features

- **Glossing** — breaks Mabaan words into morphemes using Leipzig Glossing Rules, with tone pattern detection (H/L/F/R)
- **Lexicon extraction** — produces structured entries (headword, POS, English gloss, Arabic gloss, semantic domain, example sentence) from raw field notes
- **Orthography normalization** — standardizes spelling variation against attested Bible forms
- **IGT validation** — checks Interlinear Glossed Text for morpheme/gloss alignment and Leipzig convention compliance
- **Translation** — produces English free translations with evidence verse citations
- **Corpus summarization** — identifies phonological and morphological patterns across a batch

Every output includes a `confidence` score (high / medium / low) and `evidence_verse_ids` so linguists can verify the AI's reasoning.

## Bible RAG corpus

The Mabaan Bible is the largest existing written corpus of the language. Before any LLM call, the system retrieves the top-k most relevant verses using keyword search and injects them as context.

Supported Bible import formats:
- **CSV / TSV** — columns: `book, chapter, verse, mabaan_text, english_text`
- **USFM** — standard Bible markup (`\id`, `\c`, `\v`)
- **Plain text** — alternating Mabaan / English lines

## Human-in-the-loop review

After the pipeline runs, results are loaded into an annotation queue. Linguists log in to the web app and review each AI-generated entry one at a time — they can approve it, reject it, or edit individual fields before approving. The queue prioritizes low-confidence items first.

Web app routes:
- `/queue/<name>` — a labeller's personal review queue
- `/review/<item_id>` — single-item review with source data, AI output, and supporting Bible verses side by side
- `/dashboard` — coordinator view of all labeller progress

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env
# Fill in your ANTHROPIC_API_KEY in .env
```

## CLI reference

```bash
# Import a Mabaan Bible file as the RAG knowledge base
mabaan bible import data/bible/mabaan.csv

# Search the Bible index
mabaan bible search "word or phrase"

# Show Bible index stats (verse count, books)
mabaan bible info

# Process a file through the AI pipeline
mabaan process data/raw/sample_words.txt --task gloss
mabaan process data/raw/sample_words.txt --task lexicon
mabaan process data/raw/sample_igt.txt   --task validate
mabaan process data/raw/notes.txt        --task normalize
mabaan process data/raw/notes.txt        --task translate
mabaan process data/raw/notes.txt        --task summarize

# Process and load results straight into the review queue
mabaan process data/raw/sample_words.txt --task gloss --queue

# Assign queue items to a labeller (prioritizes low-confidence items)
mabaan label assign alice --count 20

# Start a terminal-based review session
mabaan label work alice

# Show a labeller's pending queue
mabaan label queue alice

# Export all human-approved entries to JSON
mabaan label export --output data/lexicon/approved.json

# Search the approved lexicon
mabaan search "word"

# Export the full lexicon to CSV
mabaan export --output data/lexicon/full.csv

# Show corpus and queue statistics
mabaan stats

# Start the web review interface
mabaan serve --port 8000
```

## Input formats

| Format | Notes |
|--------|-------|
| `.txt` | One entry per line. If line count is divisible by 3, auto-detected as IGT blocks (surface / gloss / translation) |
| `.csv` | Any column layout — parsed as key-value dicts |
| `.tsv` | Same as CSV, tab-separated |
| `.json` | List of objects, or `{"entries": [...]}` |

## Output format

Every pipeline task returns a JSON envelope:

```json
{
  "task": "gloss",
  "model": "claude-opus-4-8",
  "results": [
    {
      "id": 0,
      "source": "original Mabaan word",
      "morphemes": ["m1", "m2"],
      "glosses": ["g1", "g2"],
      "free_translation": "English translation",
      "tone_pattern": "H-L",
      "evidence_verse_ids": ["GEN.1.1", "GEN.1.3"],
      "confidence": "high",
      "status": "ok",
      "notes": ""
    }
  ],
  "batch_meta": {
    "input_count": 20,
    "success_count": 19,
    "error_count": 1,
    "low_confidence_count": 4,
    "warnings": []
  }
}
```

## Stack

- **Claude** (Anthropic API) — LLM backbone with prompt caching for cost efficiency
- **FastAPI + Jinja2** — web review interface
- **Typer + Rich** — CLI with formatted terminal output
- **Python 3.11+**