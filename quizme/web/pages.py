"""Server-rendered HTML pages (FR-46..52 UI). Thin over the application layer —
POST actions do the work via the same services the JSON API uses, then redirect
back (POST-redirect-GET). Templates in ``web/templates``.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from quizme.application import action_items, quiz, review_queue
from quizme.domain.errors import DuplicateRecording
from quizme.domain.ids import new_id
from quizme.domain.ku import Actor, KUOperation, KUOpType
from quizme.domain.selection import retrievability, strength_bucket
from quizme.web.deps import get_deps

router = APIRouter(prefix="/app", tags=["ui"], include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _r(name: str, request: Request, **ctx: object) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"request": request, **ctx})


@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    deps = get_deps()
    now = deps.clock.now()
    kus = [k for k in deps.store.load_kus().values() if k.quiz_eligible]
    cards = deps.store.all_cards()
    due = sum(1 for c in cards if c.is_due(now=now) or retrievability(c, now=now) < 0.9)
    quiz_today = None
    q = deps.store.get_quiz_by_date(now.date())
    if q:
        qs = deps.store.quiz_questions(str(q["id"]))
        answered = sum(1 for x in qs if deps.store.get_grade(x["id"]))
        quiz_today = {"total": len(qs), "answered": answered}
    return _r(
        "dashboard.html",
        request,
        live_kus=len(kus),
        due_today=due,
        review_open=len(deps.store.list_review_items()),
        todo_open=len(deps.store.list_action_items(status="open")),
        mtd=deps.store.month_spend_usd(year=now.year, month=now.month),
        projected=deps.spend.projected_month_end_usd(),
        credit=deps.config.budget.monthly_credit_usd,
        throttled=deps.spend.is_throttled(),
        quiz_today=quiz_today,
        quiz_time=deps.config.quiz.send_time_local,
    )


@router.post("/quiz/build")
async def build_quiz() -> RedirectResponse:
    quiz.build_daily_quiz(get_deps())
    return RedirectResponse("/app", status_code=303)


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request) -> HTMLResponse:
    ing = get_deps().config.ingest
    return _r("upload.html", request, formats=ing.allowed_formats, max_mb=ing.max_file_mb, results=None)


@router.post("/upload", response_class=HTMLResponse)
async def do_upload(request: Request, files: list[UploadFile]) -> HTMLResponse:
    deps = get_deps()
    ing = deps.config.ingest
    results = []
    for f in files:
        ext = (f.filename or "").rsplit(".", 1)[-1].lower()
        content = await f.read()
        if ext not in ing.allowed_formats:
            results.append({"filename": f.filename, "status": "rejected", "reason": f".{ext} not allowed"})
        elif len(content) > ing.max_file_mb * 1024 * 1024:
            results.append({"filename": f.filename, "status": "rejected", "reason": "over size limit"})
        else:
            try:
                acc = deps.intake.accept_upload(filename=f.filename or "upload", content=content)
                results.append({"filename": f.filename, "status": "accepted", "recording_id": acc.recording_id})
            except DuplicateRecording as dup:
                results.append({"filename": f.filename, "status": "duplicate", "recording_id": dup.recording_id})
    return _r("upload.html", request, formats=ing.allowed_formats, max_mb=ing.max_file_mb, results=results)


@router.get("/ingestion", response_class=HTMLResponse)
async def ingestion_page(request: Request) -> HTMLResponse:
    return _r("ingestion.html", request, recordings=get_deps().store.ingestion_status())


@router.post("/ingestion/{recording_id}/retry")
async def ingestion_retry(recording_id: str) -> RedirectResponse:
    get_deps().intake.reenqueue(recording_id)
    return RedirectResponse("/app/ingestion", status_code=303)


@router.get("/review", response_class=HTMLResponse)
async def review_page(request: Request) -> HTMLResponse:
    return _r("review.html", request, items=review_queue.list_open(get_deps()))


@router.post("/review/{item_id}/resolve")
async def review_resolve(item_id: str, resolution: str = Form(...)) -> RedirectResponse:
    deps = get_deps()
    payload = {"value": "correct"} if resolution == "overturn" else None
    if resolution != "uphold":
        review_queue.resolve(deps, item_id=item_id, resolution=resolution, payload=payload)
    else:
        deps.store.resolve_review_item(item_id, resolution="uphold")
    return RedirectResponse("/app/review", status_code=303)


@router.get("/kb", response_class=HTMLResponse)
async def kb_page(request: Request, q: str | None = None) -> HTMLResponse:
    deps = get_deps()
    kus = [k for k in deps.store.load_kus().values() if k.quiz_eligible]
    if q:
        ql = q.lower()
        hits = [
            {
                "id": k.id,
                "canonical": k.canonical,
                "alt_phrasings": list(k.alt_phrasings),
                "sources": [{"recording_id": s.recording_id, "start": s.start} for s in k.sources],
            }
            for k in kus
            if ql in k.canonical.lower() or any(ql in a.lower() for a in k.alt_phrasings)
        ][:50]
        return _r("kb.html", request, q=q, hits=hits, topics=[])
    tids = sorted({t for k in kus for t in k.topic_ids})
    labels = deps.store.topic_labels(tids)
    topics = [
        {
            "id": tid,
            "label": labels.get(tid, tid),
            "ku_count": sum(1 for k in kus if tid in k.topic_ids),
            "note": (deps.store.get_topic_note(tid) or {}).get("markdown"),
        }
        for tid in tids
    ]
    return _r("kb.html", request, q=None, hits=None, topics=topics)


@router.post("/kb/{ku_id}/archive")
async def kb_archive(ku_id: str) -> RedirectResponse:
    deps = get_deps()
    deps.store.append_ops(
        [
            KUOperation(
                op_id=new_id(),
                ts=deps.clock.now(),
                actor=Actor.USER,
                type=KUOpType.ARCHIVE,
                ku_ids_in=(ku_id,),
                payload={"ku_id": ku_id},
                rationale="archived from web",
            )
        ]
    )
    return RedirectResponse("/app/kb", status_code=303)


@router.get("/todo", response_class=HTMLResponse)
async def todo_page(request: Request, status: str = "open") -> HTMLResponse:
    return _r("todo.html", request, items=action_items.list_items(get_deps(), status=status))


@router.post("/todo/{item_id}/act")
async def todo_act(item_id: str, how: str = Form(...)) -> RedirectResponse:
    deps = get_deps()
    items = deps.store.list_action_items()
    match = next((i for i in items if i.id == item_id), None)
    if match:
        action_items.set_status(deps, dedup_key=match.dedup_key, how=how)
    return RedirectResponse("/app/todo", status_code=303)


@router.get("/retention", response_class=HTMLResponse)
async def retention_page(request: Request) -> HTMLResponse:
    deps = get_deps()
    now = deps.clock.now()
    kus = {k.id: k for k in deps.store.load_kus().values() if k.quiz_eligible}
    labels = deps.store.topic_labels(sorted({t for k in kus.values() for t in k.topic_ids}))
    per: dict[str, Counter] = {}
    for c in deps.store.all_cards():
        ku = kus.get(c.ku_id)
        if not ku:
            continue
        b = strength_bucket(c, now=now)
        for tid in ku.topic_ids:
            per.setdefault(tid, Counter())[b] += 1
    topics = [{"topic": labels.get(tid, tid), **dict(cnt)} for tid, cnt in per.items()]
    return _r("retention.html", request, topics=topics)
