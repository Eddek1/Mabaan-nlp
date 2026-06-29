"""
Standalone script — process_corpus.py
Processes a file or directory without the CLI installer.

Usage:
    python scripts/process_corpus.py --task gloss data/raw/sample_words.txt
    python scripts/process_corpus.py --task lexicon data/raw/sample_lexicon.csv
    python scripts/process_corpus.py --task validate data/raw/sample_igt.txt
"""

import sys
from pathlib import Path

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import argparse
from mabaan.pipeline.ingest import load_file, load_directory
from mabaan.pipeline.process import Task, run as process_run
from mabaan.corpus.store import CorpusStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Mabaan NLP processing script")
    parser.add_argument("input", type=Path, help="File or directory to process")
    parser.add_argument(
        "--task", "-t",
        choices=[t.value for t in Task],
        default="gloss",
        help="Processing task (default: gloss)",
    )
    parser.add_argument("--output", "-o", default="output", help="Output file name prefix")
    parser.add_argument("--store", action="store_true", help="Save results to corpus store")
    args = parser.parse_args()

    if args.input.is_dir():
        entries = load_directory(args.input)
    else:
        entries = load_file(args.input)

    print(f"Loaded {len(entries)} entries.")
    output_path = process_run(entries, Task(args.task), output_name=args.output)

    if args.store:
        import json
        results = json.loads(output_path.read_text(encoding="utf-8")).get("results", [])
        corpus = CorpusStore()
        added = corpus.bulk_upsert(results)
        print(f"Stored {added} new entries. Corpus total: {len(corpus)}")


if __name__ == "__main__":
    main()
