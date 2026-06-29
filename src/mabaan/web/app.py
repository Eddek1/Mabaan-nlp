"""
FastAPI web app for the human labelling workflow.
Run with:  mabaan serve
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from mabaan.labelling.queue import (
    get_labeller_queue,
    submit_review,
    stats as queue_stats,
    STATUS_APPROVED, STATUS_REJECTED,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title="Mabaan Labeller", docs_url=None, redoc_url=None)


def _html(request: Request, template: str, **ctx: Any) -> HTMLResponse:
    return templates.TemplateResponse(request, template, ctx)


def _preview(item: dict[str, Any]) -> str:
    """Short preview string for the queue list."""
    ai = item.get("ai_output", {})
    src = item.get("source", {})
    for key in ("source", "text", "mabaan", "headword", "line1"):
        val = ai.get(key) or src.get(key)
        if val:
            return str(val)[:60]
    return str(list(ai.values())[:1])[1:61]


def _bible_verses(verse_ids: list[str]) -> list[dict[str, Any]]:
    try:
        from mabaan.bible.store import get_store
        store = get_store()
        by_id = {v["id"]: v for v in store.verses}
        return [by_id[vid] for vid in verse_ids if vid in by_id]
    except Exception:
        return []


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, labeller: str = Cookie(default="")):
    if labeller:
        return RedirectResponse(f"/queue/{labeller}")
    return _html(request, "login.html", labeller="")


@app.post("/login")
async def login(labeller: str = Form(...)):
    name = labeller.strip()
    if not name:
        return RedirectResponse("/", status_code=302)
    resp = RedirectResponse(f"/queue/{name}", status_code=302)
    resp.set_cookie("labeller", name, max_age=86400 * 30)
    return resp


@app.get("/queue/{labeller}", response_class=HTMLResponse)
async def queue_view(request: Request, labeller: str):
    items = get_labeller_queue(labeller)
    enriched = [item | {"preview": _preview(item)} for item in items]

    s = queue_stats()
    by_l = s["by_labeller"].get(labeller, {})
    done = by_l.get("approved", 0) + by_l.get("rejected", 0)
    total = done + len(items)
    done_pct = int(done / total * 100) if total else 0

    return _html(request, "queue.html",
                 labeller=labeller, items=enriched,
                 done=done, done_pct=done_pct)


@app.get("/review/{item_id}", response_class=HTMLResponse)
async def review_get(request: Request, item_id: str, labeller: str = "", flash: str = ""):
    from mabaan.labelling.queue import _load
    data = _load()
    item = data["items"].get(item_id)
    if not item:
        return HTMLResponse("Item not found", status_code=404)

    ai = item.get("ai_output", {})
    src = item.get("source", {})
    verse_ids = ai.get("evidence_verse_ids", [])
    editable = {k: json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
                for k, v in ai.items()
                if not k.startswith("_") and k not in ("id", "status")}

    return _html(request, "review.html",
                 labeller=labeller or item.get("assigned_to", ""),
                 item=item,
                 source_json=json.dumps(src, ensure_ascii=False, indent=2),
                 ai_json=json.dumps(ai, ensure_ascii=False, indent=2),
                 evidence_verses=_bible_verses(verse_ids),
                 editable_fields=editable,
                 flash=flash)


@app.post("/review/{item_id}")
async def review_post(
    request: Request,
    item_id: str,
    labeller: str = Form(""),
    decision: str = Form(""),
    note: str = Form(""),
):
    from mabaan.labelling.queue import _load
    data = _load()
    item = data["items"].get(item_id)
    if not item or decision not in (STATUS_APPROVED, STATUS_REJECTED):
        return RedirectResponse(f"/queue/{labeller}", status_code=302)

    form = await request.form()
    ai = item.get("ai_output", {})
    edit: dict[str, Any] = {}
    for key in ai:
        form_key = f"edit_{key}"
        val = form.get(form_key, "")
        if val and val != json.dumps(ai.get(key), ensure_ascii=False).strip('"'):
            try:
                edit[key] = json.loads(val)
            except json.JSONDecodeError:
                edit[key] = val

    submit_review(item_id, decision, edit=edit or None, note=note)

    # Go to next item in queue
    remaining = get_labeller_queue(labeller)
    if remaining:
        return RedirectResponse(
            f"/review/{remaining[0]['id']}?labeller={labeller}&flash=Saved",
            status_code=302,
        )
    return RedirectResponse(f"/queue/{labeller}", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    s = queue_stats()
    by_status = s["by_status"]
    stat_cards = [
        ("Total items",  s["total"],                       "#1a1a1a"),
        ("Pending",      by_status.get("pending", 0),      "#92400e"),
        ("Assigned",     by_status.get("assigned", 0),     "#1d4ed8"),
        ("Approved",     by_status.get("approved", 0),     "#155724"),
        ("Rejected",     by_status.get("rejected", 0),     "#721c24"),
    ]
    labellers = []
    for name, counts in s["by_labeller"].items():
        if name == "unassigned":
            continue
        assigned  = counts.get("assigned", 0)
        approved  = counts.get("approved", 0)
        rejected  = counts.get("rejected", 0)
        labellers.append({
            "name": name,
            "assigned": assigned + approved + rejected,
            "approved": approved,
            "rejected": rejected,
            "remaining": assigned,
        })
    return _html(request, "dashboard.html",
                 labeller="coordinator",
                 stat_cards=stat_cards,
                 labellers=labellers)
