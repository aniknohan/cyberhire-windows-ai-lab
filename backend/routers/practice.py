"""Communication practice modules: evaluate a single spoken/typed answer, pronunciation drills."""
import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException

from lib.answers import process_answer
from lib.auth import current_user
from routers.billing import require_pro, require_ai
from lib.db import db
from lib.llm import llm_json
from lib.scoring import PRACTICE_MODULES, audio_metrics_line, clean_eval, evaluate_responses, filler_score, pace_score
from models.schemas import Drill, DrillAnswerIn, DrillCreate, DrillItem, DrillResult, Evaluation, PracticeIn, PracticeResult

router = APIRouter(prefix="/practice", tags=["practice"])

MODULE_CONTEXT = {
    "tell_me_about_yourself": "Module: 'Tell me about yourself' opening for a SOC Analyst interview. Judge length (ideal 60-120s), confidence, grammar, professional tone, relevance and structure (present-past-future).",
    "behavioral_star": "Module: Behavioral interview practice. Evaluate STAR structure strictly. Add to the answer object a field \"star\": {\"situation\": bool, \"task\": bool, \"action\": bool, \"result\": bool}.",
    "technical_explanation": "Module: Technical explanation practice. Score technical correctness AND communication separately and explicitly.",
    "non_technical_audience": "Module: Explain to a specific audience. Evaluate how well the candidate adapted vocabulary, depth and framing to the stated audience (executives need business impact and plain language; analysts need precise technical detail).",
    "rapid_interview": "Module: Rapid interview question under time pressure. Value concise, direct, structured answers.",
}


def _clean(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()


def pronunciation_match(target: str, transcript: str) -> float:
    t, words = " ".join(_clean(target)), _clean(transcript)
    if not words:
        return 0.0
    n = len(t.split())
    best = 0.0
    for size in {max(1, n - 1), n, n + 1}:
        for i in range(0, max(1, len(words) - size + 1)):
            best = max(best, SequenceMatcher(None, t, " ".join(words[i:i + size])).ratio())
    return round(best * 100, 1)


@router.post("/evaluate", response_model=PracticeResult)
async def evaluate(body: PracticeIn, user: dict = Depends(require_ai)):
    return await _evaluate(body, user)


async def _evaluate(body: PracticeIn, user: dict) -> PracticeResult:
    ans = await process_answer(body.audio_b64, body.mime, body.text)
    if not ans["transcript"]:
        raise HTTPException(status_code=422, detail="We couldn't hear anything — check your microphone and try again")
    prev = await db.practice_sessions.find_one({"user_id": user["id"], "module": body.module, "prompt": body.prompt},
                                               {"_id": 0}, sort=[("created_at", -1)])
    result = {"id": str(uuid.uuid4()), "user_id": user["id"], "module": body.module, "prompt": body.prompt,
              "created_at": datetime.now(timezone.utc), "feedback": None, "star": {}, "technical_score": None,
              "pronunciation_score": None, **{k: ans[k] for k in ("transcript", "duration", "wpm", "fillers", "clarity")}}
    if body.module == "pronunciation":
        match = pronunciation_match(body.prompt, ans["transcript"])
        score = round(0.75 * match + 0.25 * ans["clarity"], 1) if ans["clarity"] is not None else match
        result.update(pronunciation_score=score, communication_score=score,
                      previous_score=(prev or {}).get("pronunciation_score"))
    else:
        ctx = MODULE_CONTEXT.get(body.module, "Module: interview practice.")
        if body.audience:
            ctx += f" Target audience: {body.audience}."
        res = await evaluate_responses(ctx, [{"id": "practice", "question": body.prompt, "transcript": ans["transcript"],
                                              "metrics": audio_metrics_line(ans)}])
        a = (res.get("answers") or [{}])[0]
        dims = {k: float(v) for k, v in (a.get("comm_dims") or {}).items() if isinstance(v, (int, float))}
        if ans["clarity"] is not None:
            dims["pronunciation_clarity"] = ans["clarity"]
        if (ps := pace_score(ans["wpm"])) is not None:
            dims["speaking_pace"] = ps
        dims["filler_words"] = filler_score(ans["fillers"], ans["words"])
        a["comm_dims"] = dims
        fb = Evaluation(**{k: v for k, v in clean_eval(a).items() if k in Evaluation.model_fields})
        star = a.get("star") if isinstance(a.get("star"), dict) else {}
        result.update(feedback=fb.model_dump(), communication_score=fb.communication_score,
                      technical_score=fb.technical_score if body.module in ("technical_explanation", "non_technical_audience", "rapid_interview") else None,
                      star={k: bool(v) for k, v in star.items()}, previous_score=(prev or {}).get("communication_score"))
    await db.practice_sessions.insert_one(dict(result))
    return PracticeResult(**result)


@router.get("/history", response_model=list[PracticeResult])
async def history(module: str | None = None, user: dict = Depends(current_user)):
    q = {"user_id": user["id"]}
    if module:
        q["module"] = module
    rows = await db.practice_sessions.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [PracticeResult(**r) for r in rows]


# ---------------- weakness drills ----------------
DRILL_MODULES = [m for m in PRACTICE_MODULES if m != "rapid_interview"]


@router.post("/drills", response_model=Drill)
async def create_drill(body: DrillCreate, user: dict = Depends(require_ai)):
    last = await db.interviews.find_one({"user_id": user["id"], "status": "completed"}, {"_id": 0, "position": 1, "report": 1}, sort=[("created_at", -1)])
    role = (last or {}).get("position") or user.get("target_role") or "SOC Analyst"
    weak = ((last or {}).get("report") or {}).get("weaknesses", [])[:5]
    out = await llm_json(
        "You design short, targeted interview-practice drills for SOC analyst candidates. Respond ONLY with JSON.",
        f"""Candidate role: {role}. Priority to improve: "{body.title}" — {body.why}. Suggested module: {body.module}.
Recent weaknesses: {weak}.
Design a 10-minute drill of exactly 5 spoken exercises (about 2 minutes each) that directly train this priority, escalating in difficulty.
Allowed modules: {DRILL_MODULES}. Use mostly the module that fits the priority; mix in others only if they help.
- pronunciation: prompt is ONE cybersecurity term or short phrase to say clearly.
- non_technical_audience: include "audience" (e.g. "CFO (non-technical executive)" or "Senior SOC Analyst").
- others: prompt is an interview question the candidate answers out loud.
Return JSON: {{"items": [{{"module": "...", "prompt": "...", "audience": null, "focus": "what this exercise trains, 1 short sentence"}}]}}""",
    )
    items = []
    for it in (out.get("items") or [])[:5]:
        if not isinstance(it, dict) or not it.get("prompt"):
            continue
        mod = it.get("module") if it.get("module") in DRILL_MODULES else body.module if body.module in DRILL_MODULES else "technical_explanation"
        items.append(DrillItem(module=mod, prompt=str(it["prompt"])[:400], audience=it.get("audience") or None, focus=str(it.get("focus") or "")[:200]))
    if len(items) < 3:
        raise HTTPException(status_code=502, detail="Could not build a drill — please try again")
    drill = {"id": str(uuid.uuid4()), "user_id": user["id"], "title": body.title, "why": body.why, "minutes": 10,
             "items": [i.model_dump() for i in items], "results": [], "completed": False, "created_at": datetime.now(timezone.utc)}
    await db.drills.insert_one(dict(drill))
    return Drill(**drill)


@router.get("/drills", response_model=list[Drill])
async def list_drills(user: dict = Depends(current_user)):
    return [Drill(**d) for d in await db.drills.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(20)]


@router.get("/drills/{did}", response_model=Drill)
async def get_drill(did: str, user: dict = Depends(current_user)):
    d = await db.drills.find_one({"id": did, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Drill not found")
    return Drill(**d)


@router.post("/drills/{did}/items/{idx}", response_model=PracticeResult)
async def answer_drill_item(did: str, idx: int, body: DrillAnswerIn, user: dict = Depends(require_ai)):
    d = await db.drills.find_one({"id": did, "user_id": user["id"]}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Drill not found")
    if idx < 0 or idx >= len(d["items"]):
        raise HTTPException(status_code=400, detail="No such exercise")
    item = d["items"][idx]
    res = await _evaluate(PracticeIn(module=item["module"], prompt=item["prompt"], audience=item.get("audience"),
                                     audio_b64=body.audio_b64, mime=body.mime, text=body.text), user)
    r = DrillResult(index=idx, practice_id=res.id, communication_score=res.communication_score,
                    technical_score=res.technical_score, pronunciation_score=res.pronunciation_score).model_dump()
    results = [x for x in d.get("results", []) if x["index"] != idx] + [r]
    await db.drills.update_one({"id": did}, {"$set": {"results": results, "completed": len({x["index"] for x in results}) == len(d["items"])}})
    return res
