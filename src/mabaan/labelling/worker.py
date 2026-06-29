"""
Interactive labeller CLI — work through assigned items one at a time.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from mabaan.labelling.queue import (
    get_labeller_queue,
    submit_review,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_NEEDS_REVISION,
)

console = Console()


def _show_item(item: dict[str, Any], index: int, total: int) -> None:
    console.rule(f"[bold cyan]Item {index}/{total}[/]  ID: {item['id'][:8]}…")

    # Source input
    src = item.get("source", {})
    if src:
        console.print(Panel(json.dumps(src, ensure_ascii=False, indent=2), title="[yellow]Source Input[/]", expand=False))

    # AI output
    ai = item.get("ai_output", {})
    conf = ai.get("confidence", "?")
    conf_color = {"high": "green", "medium": "yellow", "low": "red"}.get(conf, "white")
    console.print(Panel(
        json.dumps(ai, ensure_ascii=False, indent=2),
        title=f"[bold]AI Output[/]  confidence=[{conf_color}]{conf}[/{conf_color}]",
        expand=False,
    ))

    # Evidence
    verse_ids = ai.get("evidence_verse_ids", [])
    if verse_ids:
        console.print(f"[dim]Evidence verses: {', '.join(verse_ids)}[/]")


def _prompt_decision() -> str:
    console.print(
        "\n[bold green]a[/] approve   "
        "[bold red]r[/] reject   "
        "[bold yellow]e[/] edit & approve   "
        "[bold blue]s[/] skip   "
        "[bold white]q[/] quit"
    )
    while True:
        choice = Prompt.ask("Decision", choices=["a", "r", "e", "s", "q"], default="s")
        return choice


def _prompt_edit(ai_output: dict[str, Any]) -> dict[str, Any]:
    console.print("[dim]Enter corrected JSON (empty fields = keep AI value). Ctrl+C to cancel.[/]")
    console.print("[dim]Fields you can edit:[/]")
    editable = {k: v for k, v in ai_output.items() if not k.startswith("_") and k != "id"}
    for k, v in editable.items():
        console.print(f"  [cyan]{k}[/]: {json.dumps(v, ensure_ascii=False)}")

    edit: dict[str, Any] = {}
    for key, current in editable.items():
        new_val = Prompt.ask(f"  [cyan]{key}[/]", default="")
        if new_val.strip():
            # Try to parse as JSON value; fall back to plain string
            try:
                edit[key] = json.loads(new_val)
            except json.JSONDecodeError:
                edit[key] = new_val
    return edit


def run_session(labeller: str) -> None:
    """Work through all items assigned to this labeller interactively."""
    queue = get_labeller_queue(labeller)
    if not queue:
        console.print(f"[green]No pending items for {labeller}.[/] Ask a coordinator to assign more.")
        return

    console.print(f"\n[bold]Labeller:[/] {labeller}   [bold]Items in queue:[/] {len(queue)}\n")
    total = len(queue)

    for i, item in enumerate(queue, 1):
        _show_item(item, i, total)
        choice = _prompt_decision()

        if choice == "q":
            console.print("[yellow]Session ended early.[/]")
            break

        if choice == "s":
            continue

        note = ""
        edit = None

        if choice == "a":
            decision = STATUS_APPROVED
            note = Prompt.ask("Note (optional)", default="")

        elif choice == "r":
            decision = STATUS_REJECTED
            note = Prompt.ask("Reason for rejection", default="")

        elif choice == "e":
            edit = _prompt_edit(item.get("ai_output", {}))
            note = Prompt.ask("Note (optional)", default="")
            decision = STATUS_APPROVED

        else:
            continue

        submit_review(item["id"], decision, edit=edit, note=note)
        status_label = {
            STATUS_APPROVED: "[green]Approved[/]",
            STATUS_REJECTED: "[red]Rejected[/]",
        }.get(decision, decision)
        console.print(f"  → {status_label}\n")

    console.print(f"\n[bold green]Session complete.[/] Remaining: {len(get_labeller_queue(labeller))}")
