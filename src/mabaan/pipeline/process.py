"""
Processing pipeline: batch raw entries through the LLM (Recipe-powered)
and write structured results to data/processed/.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import track

from mabaan.config import BATCH_SIZE, DATA_PROCESSED
from mabaan.llm import analyze

console = Console()


class Task(str, Enum):
    GLOSS    = "gloss"
    LEXICON  = "lexicon"
    NORMALIZE = "normalize"
    VALIDATE = "validate"
    SUMMARIZE = "summarize"


def _chunk(lst: list[Any], size: int) -> list[list[Any]]:
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def _extract_text(entry: dict[str, Any]) -> str:
    """Pull the primary text field out of a raw entry regardless of schema."""
    for key in ("text", "mabaan", "line1", "form", "word", "surface"):
        if key in entry and entry[key]:
            return str(entry[key])
    # fallback: first non-private string value
    for k, v in entry.items():
        if not k.startswith("_") and isinstance(v, str) and v:
            return v
    return ""


def run(
    entries: list[dict[str, Any]],
    task: Task,
    output_name: str = "output",
) -> Path:
    """
    Process a list of ingested entries with the given task.
    Writes results to data/processed/<output_name>_<task>.json.
    Returns the output path.
    """
    console.print(f"[bold cyan]Task:[/] {task.value}  [bold cyan]Entries:[/] {len(entries)}")

    all_results: list[dict[str, Any]] = []
    batches = _chunk(entries, BATCH_SIZE)

    for batch in track(batches, description=f"Processing {task.value}..."):
        if task == Task.GLOSS:
            texts = [_extract_text(e) for e in batch]
            response = analyze.gloss_entries(texts)

        elif task == Task.LEXICON:
            texts = [_extract_text(e) for e in batch]
            response = analyze.extract_lexicon_entries(texts)

        elif task == Task.NORMALIZE:
            texts = [_extract_text(e) for e in batch]
            response = analyze.normalize_orthography(texts)

        elif task == Task.VALIDATE:
            igt_batch = [
                {
                    "line1": e.get("line1", _extract_text(e)),
                    "line2": e.get("line2", ""),
                    "line3": e.get("line3", ""),
                }
                for e in batch
            ]
            response = analyze.validate_igt(igt_batch)

        elif task == Task.SUMMARIZE:
            texts = [_extract_text(e) for e in batch]
            response = analyze.summarize_corpus(texts)
            all_results.append(response)
            break  # summarize is a single-shot task over the whole batch

        else:
            raise ValueError(f"Unknown task: {task}")

        results = response.get("results", [response])
        for i, result in enumerate(results):
            result["_input"] = batch[i] if i < len(batch) else {}
        all_results.extend(results)

    output_path = DATA_PROCESSED / f"{output_name}_{task.value}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"task": task.value, "results": all_results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    success = sum(1 for r in all_results if r.get("status") != "error")
    errors  = len(all_results) - success
    console.print(f"[green]Done.[/] {success} ok, {errors} errors → [bold]{output_path}[/]")
    return output_path
