"""
Annotation queue — file-based task management for human labellers.

Queue file: data/labelling/queue.json
Each item has a status lifecycle:
  pending → assigned → approved | rejected | needs_revision
"""

from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path
from typing import Any

from mabaan.config import DATA_LABELLING

QUEUE_FILE = DATA_LABELLING / "queue.json"
STATUS_PENDING          = "pending"
STATUS_ASSIGNED         = "assigned"
STATUS_APPROVED         = "approved"
STATUS_REJECTED         = "rejected"
STATUS_NEEDS_REVISION   = "needs_revision"


def _load() -> dict[str, Any]:
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    return {"items": {}}


def _save(data: dict[str, Any]) -> None:
    DATA_LABELLING.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_from_pipeline(processed_json: Path, task: str) -> int:
    """
    Import AI-generated results from a pipeline output file into the queue.
    Returns number of items added.
    """
    raw = json.loads(processed_json.read_text(encoding="utf-8"))
    results = raw.get("results", [])
    data = _load()
    added = 0
    for result in results:
        item_id = str(uuid.uuid4())
        data["items"][item_id] = {
            "id": item_id,
            "task": task,
            "ai_output": result,
            "source": result.get("_input", {}),
            "status": STATUS_PENDING,
            "assigned_to": None,
            "assigned_at": None,
            "reviewed_at": None,
            "reviewer_decision": None,
            "reviewer_edit": None,
            "reviewer_note": None,
            "ai_confidence": result.get("confidence", "unknown"),
        }
        added += 1
    _save(data)
    return added


def assign_batch(labeller: str, count: int, prefer_low_confidence: bool = True) -> list[str]:
    """
    Assign up to `count` pending items to a labeller.
    Prioritizes low-confidence AI outputs first.
    Returns list of assigned item IDs.
    """
    data = _load()
    pending = [
        item for item in data["items"].values()
        if item["status"] == STATUS_PENDING
    ]
    if prefer_low_confidence:
        order = {"low": 0, "medium": 1, "high": 2, "unknown": 1}
        pending.sort(key=lambda x: order.get(x.get("ai_confidence", "unknown"), 1))

    batch = pending[:count]
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    assigned_ids = []
    for item in batch:
        item["status"]      = STATUS_ASSIGNED
        item["assigned_to"] = labeller
        item["assigned_at"] = now
        data["items"][item["id"]] = item
        assigned_ids.append(item["id"])
    _save(data)
    return assigned_ids


def get_labeller_queue(labeller: str) -> list[dict[str, Any]]:
    """Return all items assigned to a labeller that are not yet reviewed."""
    data = _load()
    return [
        item for item in data["items"].values()
        if item["assigned_to"] == labeller and item["status"] == STATUS_ASSIGNED
    ]


def submit_review(
    item_id: str,
    decision: str,
    edit: dict[str, Any] | None = None,
    note: str = "",
) -> None:
    """
    Record a labeller's review decision.
    decision: 'approved' | 'rejected' | 'needs_revision'
    edit: corrected fields (merged onto ai_output)
    """
    if decision not in (STATUS_APPROVED, STATUS_REJECTED, STATUS_NEEDS_REVISION):
        raise ValueError(f"Invalid decision: {decision}")
    data = _load()
    if item_id not in data["items"]:
        raise KeyError(f"Item {item_id} not found in queue")
    item = data["items"][item_id]
    item["status"]            = decision
    item["reviewed_at"]       = datetime.datetime.now(datetime.timezone.utc).isoformat()
    item["reviewer_decision"] = decision
    item["reviewer_edit"]     = edit
    item["reviewer_note"]     = note
    _save(data)


def stats() -> dict[str, Any]:
    data = _load()
    items = list(data["items"].values())
    counts: dict[str, int] = {}
    for item in items:
        s = item["status"]
        counts[s] = counts.get(s, 0) + 1
    by_labeller: dict[str, dict[str, int]] = {}
    for item in items:
        name = item.get("assigned_to") or "unassigned"
        if name not in by_labeller:
            by_labeller[name] = {"assigned": 0, "approved": 0, "rejected": 0, "needs_revision": 0}
        if item["status"] == STATUS_ASSIGNED:
            by_labeller[name]["assigned"] += 1
        elif item["status"] in by_labeller[name]:
            by_labeller[name][item["status"]] += 1
    return {
        "total": len(items),
        "by_status": counts,
        "by_labeller": by_labeller,
    }


def export_approved(out_path: Path | None = None) -> Path:
    """Export all approved items (with reviewer edits applied) to JSON."""
    data = _load()
    approved = []
    for item in data["items"].values():
        if item["status"] == STATUS_APPROVED:
            final = dict(item["ai_output"])
            if item.get("reviewer_edit"):
                final.update(item["reviewer_edit"])
            final["_reviewed_by"] = item["assigned_to"]
            final["_reviewed_at"] = item["reviewed_at"]
            approved.append(final)
    out = out_path or DATA_LABELLING / "approved_export.json"
    out.write_text(json.dumps(approved, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
