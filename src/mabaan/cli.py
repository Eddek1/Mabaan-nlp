"""
Main CLI: mabaan <command> [options]
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Mabaan language data processing pipeline.", no_args_is_help=True)
bible_app  = typer.Typer(help="Manage the Mabaan Bible knowledge base.")
label_app  = typer.Typer(help="Human annotation / labelling workflow.")
app.add_typer(bible_app,  name="bible")
app.add_typer(label_app,  name="label")

console = Console()


# ── Pipeline ──────────────────────────────────────────────────────────────────

@app.command()
def process(
    input_path: Path = typer.Argument(..., help="File or directory to process"),
    task: str = typer.Option("gloss", "--task", "-t",
        help="Task: gloss | lexicon | normalize | validate | translate | summarize"),
    output: str = typer.Option("output", "--output", "-o", help="Output file name prefix"),
    queue: bool = typer.Option(False, "--queue", "-q",
        help="Load results into the labelling queue after processing"),
):
    """Process Mabaan language data through the AI + Bible RAG pipeline."""
    from mabaan.pipeline.ingest import load_file, load_directory
    from mabaan.pipeline.process import Task, run as process_run

    if input_path.is_dir():
        entries = load_file(input_path) if input_path.is_file() else \
                  __import__("mabaan.pipeline.ingest", fromlist=["load_directory"]).load_directory(input_path)
    else:
        entries = load_file(input_path)

    console.print(f"Loaded [bold]{len(entries)}[/] entries from [cyan]{input_path}[/]")
    output_path = process_run(entries, Task(task), output_name=output)

    if queue:
        from mabaan.labelling.queue import load_from_pipeline
        added = load_from_pipeline(output_path, task)
        console.print(f"[green]Added {added} items to labelling queue.[/]")


@app.command()
def search(query: str = typer.Argument(..., help="Search term")):
    """Search the local lexicon corpus."""
    from mabaan.corpus.store import CorpusStore
    corpus = CorpusStore()
    hits = corpus.search(query)
    if not hits:
        console.print("[yellow]No results found.[/]")
        return
    table = Table(title=f'Results for "{query}"', show_lines=True)
    keys = list(hits[0].keys())[:6]
    for k in keys:
        table.add_column(k, overflow="fold")
    for hit in hits[:20]:
        table.add_row(*[str(hit.get(k, "")) for k in keys])
    console.print(table)


@app.command()
def export(output: Optional[Path] = typer.Option(None, "--output", "-o")):
    """Export the lexicon corpus to CSV."""
    from mabaan.corpus.store import CorpusStore
    corpus = CorpusStore()
    path = corpus.export_csv(output)
    console.print(f"Exported {len(corpus)} entries to [bold]{path}[/]")


@app.command()
def stats():
    """Show corpus and labelling queue statistics."""
    from mabaan.corpus.store import CorpusStore
    from mabaan.labelling.queue import stats as q_stats

    corpus = CorpusStore()
    meta = corpus._data.get("meta", {})
    console.print(f"\n[bold cyan]Corpus[/]")
    console.print(f"  Total entries : {meta.get('total', len(corpus))}")
    console.print(f"  Last updated  : {meta.get('last_updated', 'never')}")

    console.print(f"\n[bold cyan]Labelling Queue[/]")
    s = q_stats()
    console.print(f"  Total items   : {s['total']}")
    for status, count in s["by_status"].items():
        console.print(f"  {status:<20}: {count}")

    if s["by_labeller"]:
        console.print(f"\n[bold cyan]By Labeller[/]")
        t = Table(show_header=True)
        t.add_column("Labeller")
        t.add_column("Assigned")
        t.add_column("Approved")
        t.add_column("Rejected")
        for name, counts in s["by_labeller"].items():
            t.add_row(name, str(counts.get("assigned", 0)),
                      str(counts.get("approved", 0)), str(counts.get("rejected", 0)))
        console.print(t)


# ── Bible ─────────────────────────────────────────────────────────────────────

@bible_app.command("import")
def bible_import(
    bible_file: Path = typer.Argument(..., help="Bible file (.csv, .tsv, .usfm, .txt)"),
):
    """Import a Mabaan Bible file as the RAG knowledge base."""
    from mabaan.bible.parser import parse, save
    from mabaan.bible.store import reset_store
    from mabaan.config import DATA_BIBLE

    console.print(f"Parsing [cyan]{bible_file}[/]…")
    verses = parse(bible_file)
    if not verses:
        console.print("[red]No verses found. Check your file format.[/]")
        raise typer.Exit(1)

    DATA_BIBLE.mkdir(parents=True, exist_ok=True)
    out = DATA_BIBLE / "index.json"
    save(verses, out)
    reset_store()
    console.print(f"[green]Imported {len(verses)} verses → {out}[/]")


@bible_app.command("search")
def bible_search(
    query: str = typer.Argument(..., help="Mabaan word or phrase to search"),
    top: int = typer.Option(5, "--top", "-n"),
):
    """Search the Bible verse index for matching passages."""
    from mabaan.bible.store import get_store
    store = get_store()
    hits = store.search(query, top_k=top)
    if not hits:
        console.print("[yellow]No matching verses.[/]")
        return
    t = Table(show_lines=True)
    t.add_column("Ref", style="cyan")
    t.add_column("Mabaan")
    t.add_column("English")
    for v in hits:
        t.add_row(v["id"], v["mabaan"], v.get("english", ""))
    console.print(t)


@bible_app.command("info")
def bible_info():
    """Show Bible index statistics."""
    from mabaan.bible.store import get_store
    store = get_store()
    books: set[str] = {v["book"] for v in store.verses}
    console.print(f"Total verses : [bold]{len(store)}[/]")
    console.print(f"Books        : {len(books)}")
    console.print(f"Books list   : {', '.join(sorted(books)[:10])}{'…' if len(books) > 10 else ''}")


# ── Labelling ─────────────────────────────────────────────────────────────────

@label_app.command("assign")
def label_assign(
    labeller: str = typer.Argument(..., help="Labeller name"),
    count: int = typer.Option(20, "--count", "-n", help="Number of items to assign"),
    high_priority: bool = typer.Option(True, "--priority/--no-priority",
        help="Prioritize low-confidence AI items"),
):
    """Assign pending queue items to a labeller."""
    from mabaan.labelling.queue import assign_batch
    ids = assign_batch(labeller, count, prefer_low_confidence=high_priority)
    if ids:
        console.print(f"[green]Assigned {len(ids)} items to {labeller}.[/]")
    else:
        console.print("[yellow]No pending items available to assign.[/]")


@label_app.command("work")
def label_work(
    labeller: str = typer.Argument(..., help="Your labeller name"),
):
    """Start an interactive review session for your assigned items."""
    from mabaan.labelling.worker import run_session
    run_session(labeller)


@label_app.command("queue")
def label_queue(
    labeller: str = typer.Argument(..., help="Labeller name to inspect"),
):
    """Show the pending queue for a specific labeller."""
    from mabaan.labelling.queue import get_labeller_queue
    items = get_labeller_queue(labeller)
    if not items:
        console.print(f"[green]No pending items for {labeller}.[/]")
        return
    t = Table(title=f"{labeller}'s queue ({len(items)} items)", show_lines=True)
    t.add_column("ID", style="dim")
    t.add_column("Task")
    t.add_column("AI Confidence")
    t.add_column("Status")
    for item in items:
        conf = item.get("ai_confidence", "?")
        conf_style = {"high": "green", "medium": "yellow", "low": "red"}.get(conf, "")
        t.add_row(
            item["id"][:8] + "…",
            item.get("task", ""),
            f"[{conf_style}]{conf}[/{conf_style}]",
            item["status"],
        )
    console.print(t)


@label_app.command("export")
def label_export(
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
):
    """Export all approved (human-verified) items to JSON."""
    from mabaan.labelling.queue import export_approved
    path = export_approved(output)
    console.print(f"[green]Exported approved items → {path}[/]")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind (0.0.0.0 = all interfaces)"),
    port: int = typer.Option(8000, "--port", "-p"),
):
    """Start the web labelling interface. Share http://<your-ip>:<port> with labellers."""
    import uvicorn
    import socket
    local_ip = socket.gethostbyname(socket.gethostname())
    console.print(f"\n[bold green]Mabaan Labeller running[/]")
    console.print(f"  Local   : [cyan]http://localhost:{port}[/]")
    console.print(f"  Network : [cyan]http://{local_ip}:{port}[/]  ← share this with labellers")
    console.print(f"  Dashboard: [cyan]http://{local_ip}:{port}/dashboard[/]\n")
    console.print("Press [bold]Ctrl+C[/] to stop.\n")
    uvicorn.run("mabaan.web.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
