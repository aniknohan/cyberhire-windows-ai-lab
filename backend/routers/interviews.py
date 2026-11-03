"""Interview sessions: setup, rounds, live conversation turns, evaluation, report, review & retry."""
import asyncio
import base64
import logging
import os
import random
import uuid
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from lib.answers import delete_audio, process_answer, save_audio
from lib.auth import current_user
from routers.billing import require_interview_allowance, require_ai
from lib.companies import generate_company
from lib.db import db
from lib.interview_engine import MODE_ROUNDS, next_turn, pick_seed_questions, round_meta, soc_level, track_of
from lib.scoring import clean_eval, audio_metrics_line, evaluate_responses, filler_score, final_decision, pace_score
from models.schemas import (AnswerIn, AudioOut, Evaluation, InterviewCreate, InterviewerReply, InterviewOut,
                            InterviewSummary, JoinIn, OkOut, Persona, PublicScenario, RespondIn, RespondOut,
                            ResponseOut, RetryResult, RoundOut, Turn)

router = APIRouter(tags=["interviews"])
logger = logging.getLogger(__name__)
_tasks: set[asyncio.Task] = set()


def _spawn(coro):
    t = asyncio.create_task(coro)
    _tasks.add(t)
    t.add_done_callback(_tasks.discard)


def now():
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _get_iv(iid: str, user: dict) -> dict:
    iv = await db.interviews.find_one({"id": iid, "user_id": user["id"]}, {"_id": 0})
    if not iv:
        raise HTTPException(status_code=404, detail="Interview not found")
    return iv


def _duration(iv: dict) -> float:
    total = 0.0
    for r in iv["rounds"]:
        s, e = _aware(r.get("started_at")), _aware(r.get("completed_at"))
        if s and e:
            total += (e - s).total_seconds()
    return total


async def _to_out(iv: dict) -> InterviewOut:
    pids = [r["persona_id"] for r in iv["rounds"]]
    personas = {p["id"]: p for p in await db.personas.find({"id": {"$in": pids}}, {"_id": 0}).to_list(50)}
    sids = [r["scenario_id"] for r in iv["rounds"] if r.get("scenario_id")]
    scen = {s["id"]: s for s in await db.scenarios.find({"id": {"$in": sids}}, {"_id": 0}).to_list(50)}
    rounds = []
    for r in iv["rounds"]:
        s = scen.get(r.get("scenario_id") or "")
        rounds.append(RoundOut(
            index=r["index"], type=r["type"], label=r["label"], persona=Persona(**personas[r["persona_id"]]),
            status=r["status"], target_questions=r["target_questions"], main_questions=r.get("main_questions", 0),
            evidence_shown=r.get("evidence_shown", False),
            scenario=PublicScenario(**s) if s else None, score=r.get("score"), summary=r.get("summary", ""),
            evaluating=r.get("evaluating", False), started_at=_aware(r.get("started_at")), completed_at=_aware(r.get("completed_at")),
        ))
    return InterviewOut(
        **{k: iv[k] for k in ("id", "position", "soc_level", "experience", "difficulty", "environment", "mode",
                               "coach_mode", "company", "current_round", "status")},
        focus=iv.get("focus"), record_audio=iv.get("record_audio", False), rounds=rounds, created_at=_aware(iv["created_at"]),
        completed_at=_aware(iv.get("completed_at")), duration_seconds=_duration(iv), report=iv.get("report"),
    )


def _turn(t: dict) -> Turn:
    return Turn(**{**{k: t.get(k) for k in Turn.model_fields}, "created_at": _aware(t["created_at"])})


# ---------------- setup ----------------
@router.post("/interviews", response_model=InterviewOut)
async def create_interview(body: InterviewCreate, user: dict = Depends(current_user)):
    await require_interview_allowance(user)
    level = soc_level(body.position, body.experience)
    track = track_of(body.position)
    company = await generate_company(body.environment, body.position)
    personas = await db.personas.find({}, {"_id": 0}).to_list(200)
    last = await db.interviews.find_one({"user_id": user["id"], "status": "completed"}, {"_id": 0, "report": 1}, sort=[("created_at", -1)])
    weak = [p["title"] for p in ((last or {}).get("report") or {}).get("priorities", [])[:3]]
    rounds = []
    for i, (rtype, target) in enumerate(MODE_ROUNDS[body.mode]):
        pool = [p for p in personas if p["round_type"] == rtype and (p.get("track") or ("all" if rtype == "hr" else "soc")) in ("all", track)] or \
            [p for p in personas if p["round_type"] == rtype] or personas
        persona = random.choice(pool)
        scenario_id = None
        if rtype == "scenario" and track == "soc":
            scs = await db.scenarios.find({}, {"_id": 0}).to_list(200)
            fit = [s for s in scs if company["environment"] in s.get("environments", [])] or scs
            if level == "L1":
                fit = [s for s in fit if s.get("level", "L1+") == "L1+"] or fit
            scenario_id = random.choice(fit)["id"] if fit else None
        if body.difficulty == "Hard Mode":
            target += 1
        seeds = await pick_seed_questions(user["id"], rtype, level, track=track, focus=body.focus)
        rounds.append({
            "index": i, "type": rtype, "label": round_meta(track)[rtype]["label"], "persona_id": persona["id"],
            "status": "pending", "target_questions": target, "main_questions": 0, "evidence_shown": False,
            "scenario_id": scenario_id, "seed_question_ids": [q["id"] for q in seeds],
            "adaptive": {"Beginner": -1, "Advanced": 1, "Hard Mode": 2}.get(body.difficulty, 0),
            "score": None, "summary": "", "evaluating": False, "started_at": None, "completed_at": None,
        })
    iv = {
        "id": str(uuid.uuid4()), "user_id": user["id"], **body.model_dump(), "soc_level": level,
        "company": company, "rounds": rounds, "current_round": 0, "status": "setup", "record_audio": False,
        "memory": [], "weak_topics": weak, "created_at": now(), "completed_at": None, "report": None,
    }
    await db.interviews.insert_one(dict(iv))
    return await _to_out(iv)


@router.get("/interviews", response_model=list[InterviewSummary])
async def list_interviews(user: dict = Depends(current_user)):
    ivs = await db.interviews.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    pmap = {p["id"]: p["name"] for p in await db.personas.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(200)}
    out = []
    for iv in ivs:
        rep = iv.get("report") or {}
        out.append(InterviewSummary(
            id=iv["id"], position=iv["position"], soc_level=iv["soc_level"], company_name=iv["company"]["name"],
            industry=iv["company"]["industry"], mode=iv["mode"], status=iv["status"], created_at=_aware(iv["created_at"]),
            decision=rep.get("decision"), job_readiness=rep.get("job_readiness"), communication=rep.get("communication"),
            interviewers=[pmap.get(r["persona_id"], "") for r in iv["rounds"]], duration_seconds=_duration(iv),
        ))
    return out


@router.get("/interviews/{iid}", response_model=InterviewOut)
async def get_interview(iid: str, user: dict = Depends(current_user)):
    return await _to_out(await _get_iv(iid, user))


@router.delete("/interviews/{iid}", response_model=OkOut)
async def delete_interview(iid: str, user: dict = Depends(current_user)):
    await _get_iv(iid, user)
    async for r in db.responses.find({"interview_id": iid, "user_id": user["id"]}, {"audio_path": 1}):
        delete_audio(r.get("audio_path"))
    await db.responses.delete_many({"interview_id": iid, "user_id": user["id"]})
    await db.turns.delete_many({"interview_id": iid, "user_id": user["id"]})
    await db.interviews.delete_one({"id": iid, "user_id": user["id"]})
    return OkOut()


@router.post("/interviews/{iid}/join", response_model=InterviewOut)
async def join_interview(iid: str, body: JoinIn, user: dict = Depends(require_ai)):
    iv = await _get_iv(iid, user)
    upd = {"record_audio": body.record_audio}
    if iv["status"] == "setup":
        upd["status"] = "in_progress"
    await db.interviews.update_one({"id": iid}, {"$set": upd})
    return await _to_out({**iv, **upd})


# ---------------- live conversation ----------------
async def _context(iv: dict, idx: int):
    rnd = iv["rounds"][idx]
    persona = await db.personas.find_one({"id": rnd["persona_id"]}, {"_id": 0})
    scenario = await db.scenarios.find_one({"id": rnd["scenario_id"]}, {"_id": 0}) if rnd.get("scenario_id") else None
    turns = await db.turns.find({"interview_id": iv["id"], "round_index": idx}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return rnd, persona, scenario, turns


async def _interviewer_turn(iv: dict, user: dict, idx: int) -> InterviewerReply:
    rnd, persona, scenario, turns = await _context(iv, idx)
    out = await next_turn(iv, rnd, persona, user, turns, scenario)
    show = bool(out.get("show_evidence")) and bool(scenario)
    sig = {"up": 1, "down": -1}.get(out.get("performance_signal"), 0)
    upd = {
        f"rounds.{idx}.main_questions": rnd.get("main_questions", 0) + (1 if out.get("counts_as_main_question") else 0),
        f"rounds.{idx}.adaptive": max(-2, min(2, rnd.get("adaptive", 0) + sig)) if turns else rnd.get("adaptive", 0),
    }
    if show:
        upd[f"rounds.{idx}.evidence_shown"] = True
    ops = {"$set": upd}
    mem = [m for m in (out.get("new_memory") or []) if isinstance(m, str) and m.strip()]
    if mem:
        ops["$push"] = {"memory": {"$each": mem}}
    await db.interviews.update_one({"id": iv["id"]}, ops)
    t = {"id": str(uuid.uuid4()), "interview_id": iv["id"], "user_id": user["id"], "round_index": idx,
         "speaker": "interviewer", "text": out["say"], "response_id": None,
         "seed_question_id": out.get("seed_question_id"), "created_at": now(),
         "round_complete": bool(out.get("round_complete")), "show_evidence": show}
    await db.turns.insert_one(dict(t))
    return InterviewerReply(turn=_turn(t), round_complete=t["round_complete"], show_evidence=show)


@router.post("/interviews/{iid}/rounds/{idx}/start", response_model=InterviewerReply)
async def start_round(iid: str, idx: int, user: dict = Depends(require_ai)):
    iv = await _get_iv(iid, user)
    if idx >= len(iv["rounds"]) or idx != iv["current_round"]:
        raise HTTPException(status_code=400, detail="This round is not available")
    if iv["rounds"][idx]["status"] == "completed":
        raise HTTPException(status_code=400, detail="Round already completed")
    last = await db.turns.find_one({"interview_id": iid, "round_index": idx}, {"_id": 0}, sort=[("created_at", -1)])
    if last and last["speaker"] == "interviewer":  # idempotent resume
        return InterviewerReply(turn=_turn(last), round_complete=last.get("round_complete", False), show_evidence=last.get("show_evidence", False))
    if iv["rounds"][idx]["status"] == "pending":
        await db.interviews.update_one({"id": iid}, {"$set": {f"rounds.{idx}.status": "active", f"rounds.{idx}.started_at": now(), "status": "in_progress"}})
        iv["rounds"][idx]["status"] = "active"
    return await _interviewer_turn(iv, user, idx)


@router.get("/interviews/{iid}/turns", response_model=list[Turn])
async def list_turns(iid: str, user: dict = Depends(current_user)):
    await _get_iv(iid, user)
    ts = await db.turns.find({"interview_id": iid, "user_id": user["id"]}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    return [_turn(t) for t in ts]


@router.post("/interviews/{iid}/respond", response_model=RespondOut)
async def respond(iid: str, body: RespondIn, user: dict = Depends(require_ai)):
    iv = await _get_iv(iid, user)
    idx = iv["current_round"]
    rnd = iv["rounds"][idx]
    if rnd["status"] != "active":
        raise HTTPException(status_code=400, detail="Round is not active")
    ans = await process_answer(body.audio_b64, body.mime, body.text)
    if not ans["transcript"]:
        return RespondOut(empty=True)
    q = await db.turns.find_one({"interview_id": iid, "round_index": idx, "speaker": "interviewer"}, {"_id": 0}, sort=[("created_at", -1)])
    persona = await db.personas.find_one({"id": rnd["persona_id"]}, {"_id": 0, "name": 1})
    rid = str(uuid.uuid4())
    audio_path = save_audio(rid, body.audio_b64, body.mime) if (body.audio_b64 and iv.get("record_audio")) else None
    resp = {"id": rid, "interview_id": iid, "user_id": user["id"], "round_index": idx, "round_type": rnd["type"],
            "interviewer_name": persona["name"] if persona else "", "question": q["text"] if q else "",
            "seed_question_id": (q or {}).get("seed_question_id"), "audio_path": audio_path, "audio_mime": body.mime,
            "evaluation": None, "retries": [], "created_at": now(),
            **{k: ans[k] for k in ("transcript", "duration", "wpm", "fillers", "clarity", "long_pauses")}}
    await db.responses.insert_one(dict(resp))
    ct = {"id": str(uuid.uuid4()), "interview_id": iid, "user_id": user["id"], "round_index": idx,
          "speaker": "candidate", "text": ans["transcript"], "response_id": rid, "created_at": now()}
    await db.turns.insert_one(dict(ct))
    try:
        reply = await _interviewer_turn(iv, user, idx)
    except Exception:
        await db.turns.delete_one({"id": ct["id"]})
        await db.responses.delete_one({"id": rid})
        delete_audio(audio_path)
        raise
    return RespondOut(candidate=_turn(ct), interviewer=reply)


@router.post("/interviews/{iid}/undo-last", response_model=InterviewerReply)
async def undo_last(iid: str, user: dict = Depends(require_ai)):
    """Coach mode 'try again': remove the last answer + reply, return the question to re-answer."""
    iv = await _get_iv(iid, user)
    if not iv.get("coach_mode"):
        raise HTTPException(status_code=400, detail="Retry is only available in Coach Mode")
    idx = iv["current_round"]
    ts = await db.turns.find({"interview_id": iid, "round_index": idx}, {"_id": 0}).sort("created_at", -1).to_list(3)
    if len(ts) < 3 or ts[0]["speaker"] != "interviewer" or ts[1]["speaker"] != "candidate":
        raise HTTPException(status_code=400, detail="Nothing to retry yet")
    resp = await db.responses.find_one({"id": ts[1]["response_id"]}, {"_id": 0, "audio_path": 1})
    delete_audio((resp or {}).get("audio_path"))
    await db.responses.delete_one({"id": ts[1]["response_id"]})
    await db.turns.delete_many({"id": {"$in": [ts[0]["id"], ts[1]["id"]]}})
    return InterviewerReply(turn=_turn(ts[2]), round_complete=False, show_evidence=False)


# ---------------- evaluation ----------------
def _ctx_line(iv: dict) -> str:
    c = iv["company"]
    return (f"Role: {iv['position']} ({iv['soc_level']}), candidate experience: {iv['experience']}, difficulty: {iv['difficulty']}. "
            f"Company: {c['name']} ({c['industry']}), stack: {', '.join(c['stack'])}.")


async def _apply_evals(answers: list[dict], by_id: dict) -> None:
    for a in answers:
        rid = a.get("response_id")
        if rid not in by_id:
            continue
        r = by_id[rid]
        dims = {k: float(v) for k, v in (a.get("comm_dims") or {}).items() if isinstance(v, (int, float))}
        if r.get("clarity") is not None:
            dims["pronunciation_clarity"] = float(r["clarity"])
        ps = pace_score(r.get("wpm"))
        if ps is not None:
            dims["speaking_pace"] = ps
        dims["filler_words"] = filler_score(r.get("fillers") or {}, len(r["transcript"].split()))
        a["comm_dims"] = dims
        ev = Evaluation(**{k: v for k, v in clean_eval(a).items() if k in Evaluation.model_fields})
        await db.responses.update_one({"id": rid}, {"$set": {"evaluation": ev.model_dump()}})


async def _evaluate_round(iid: str, idx: int) -> None:
    await db.interviews.update_one({"id": iid}, {"$set": {f"rounds.{idx}.evaluating": True}})
    try:
        iv = await db.interviews.find_one({"id": iid}, {"_id": 0})
        if not iv:
            return
        rs = await db.responses.find({"interview_id": iid, "round_index": idx}, {"_id": 0}).sort("created_at", 1).to_list(200)
        if not rs:
            await db.interviews.update_one({"id": iid}, {"$set": {f"rounds.{idx}.evaluating": False, f"rounds.{idx}.score": None,
                                                                  f"rounds.{idx}.summary": "No answers were recorded in this round."}})
            return
        seeds = {q["id"]: q for q in await db.questions.find({"id": {"$in": [r.get("seed_question_id") for r in rs]}}, {"_id": 0}).to_list(200)}
        items = [{"id": r["id"], "question": r["question"], "transcript": r["transcript"], "metrics": audio_metrics_line(r),
                  "seed": seeds.get(r.get("seed_question_id") or "")} for r in rs]
        res = await evaluate_responses(f"{_ctx_line(iv)} Round: {iv['rounds'][idx]['label']}.", items)
        await _apply_evals(res.get("answers", []), {r["id"]: r for r in rs})
        await db.interviews.update_one({"id": iid}, {"$set": {
            f"rounds.{idx}.score": float(res.get("round_score") or 0), f"rounds.{idx}.summary": res.get("round_summary", ""),
            f"rounds.{idx}.evaluating": False}})
    except Exception as e:
        logger.error("evaluate_round %s/%s failed: %s", iid, idx, e)
        await db.interviews.update_one({"id": iid}, {"$set": {f"rounds.{idx}.evaluating": False, f"rounds.{idx}.summary": "Evaluation failed"}})


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


async def _finalize(iid: str) -> None:
    try:
        for _ in range(150):
            iv = await db.interviews.find_one({"id": iid}, {"_id": 0})
            if not iv:
                return  # deleted while evaluating
            if not any(r.get("evaluating") for r in iv["rounds"]):
                break
            await asyncio.sleep(2)
        for r in iv["rounds"]:
            if r["status"] == "completed" and r.get("score") is None and r.get("summary") in ("", "Evaluation failed"):
                await _evaluate_round(iid, r["index"])
        iv = await db.interviews.find_one({"id": iid}, {"_id": 0})
        if not iv:
            return
        rs = await db.responses.find({"interview_id": iid}, {"_id": 0}).to_list(500)
        evs = [r for r in rs if r.get("evaluation") and r["evaluation"].get("evaluable", True)]
        tech_by_topic: dict[str, list[float]] = {}
        comm_by_dim: dict[str, list[float]] = {}
        for r in evs:
            e = r["evaluation"]
            tech_by_topic.setdefault(e.get("topic") or "General", []).append(e["technical_score"])
            for k, v in (e.get("comm_dims") or {}).items():
                comm_by_dim.setdefault(k, []).append(v)
        fill = Counter()
        for r in rs:
            fill.update(r.get("fillers") or {})
        tech_dims = {k: _avg(v) for k, v in tech_by_topic.items()}
        comm_dims = {k: _avg(v) for k, v in comm_by_dim.items()}
        round_scores = [{"round": r["type"], "label": r["label"], "score": r.get("score")} for r in iv["rounds"]]
        stats = "\n".join([
            f"Round scores: {[(x['label'], x['score']) for x in round_scores]}",
            f"Round evaluator notes: {[r.get('summary') for r in iv['rounds']]}",
            f"Average technical score per answer: {_avg([r['evaluation']['technical_score'] for r in evs])}",
            f"Average communication score per answer: {_avg([r['evaluation']['communication_score'] for r in evs])}",
            f"Technical topic averages: {tech_dims}", f"Communication dimension averages: {comm_dims}",
            f"Missing concepts noted: {sorted({m for r in evs for m in r['evaluation'].get('missing_concepts', [])})[:25]}",
            f"Filler words: {dict(fill)}; avg wpm {_avg([r.get('wpm') for r in rs])}; answers given {len(rs)}",
        ])
        dec = await final_decision(_ctx_line(iv), stats)
        decision = str(dec.get("decision", "BORDERLINE")).upper()
        if decision not in ("STRONG HIRE", "HIRE", "BORDERLINE", "NO HIRE"):
            decision = "BORDERLINE"
        report = {
            "decision": decision, "job_readiness": float(dec.get("job_readiness") or 0),
            "communication": float(dec.get("communication") or 0), "decision_reasoning": dec.get("decision_reasoning", ""),
            "strengths": dec.get("strengths", []), "weaknesses": dec.get("weaknesses", []),
            "hiring_summary": dec.get("hiring_summary", ""), "priorities": dec.get("priorities", [])[:5],
            "round_scores": round_scores, "tech_dims": {k: v for k, v in tech_dims.items() if v is not None},
            "comm_dims": {k: v for k, v in comm_dims.items() if v is not None},
            "technical_avg": _avg([r["evaluation"]["technical_score"] for r in evs]),
            "technical_communication_avg": _avg([r["evaluation"].get("technical_communication") for r in evs]),
            "filler_total": sum(fill.values()), "filler_top": fill.most_common(1)[0][0] if fill else None,
            "filler_breakdown": dict(fill), "avg_wpm": _avg([r.get("wpm") for r in rs]),
            "clarity_avg": _avg([r.get("clarity") for r in rs]),
        }
        await db.interviews.update_one({"id": iid}, {"$set": {"report": report, "status": "completed", "completed_at": now()}})
    except Exception as e:
        logger.error("finalize %s failed: %s", iid, e)
        await db.interviews.update_one({"id": iid}, {"$set": {"status": "failed"}})


@router.post("/interviews/{iid}/rounds/{idx}/complete", response_model=InterviewOut)
async def complete_round(iid: str, idx: int, user: dict = Depends(require_ai)):
    iv = await _get_iv(iid, user)
    if idx != iv["current_round"] or iv["rounds"][idx]["status"] == "completed":
        return await _to_out(iv)
    if iv["rounds"][idx]["status"] == "pending":
        raise HTTPException(status_code=400, detail="Round has not started")
    last = idx == len(iv["rounds"]) - 1
    upd = {f"rounds.{idx}.status": "completed", f"rounds.{idx}.completed_at": now(), f"rounds.{idx}.evaluating": True}
    if last:
        upd["status"] = "evaluating"
    else:
        upd["current_round"] = idx + 1
    await db.interviews.update_one({"id": iid}, {"$set": upd})
    _spawn(_evaluate_round(iid, idx))
    if last:
        _spawn(_finalize(iid))
    return await _to_out(await _get_iv(iid, user))


@router.post("/interviews/{iid}/end", response_model=InterviewOut)
async def end_early(iid: str, user: dict = Depends(require_ai)):
    """Candidate leaves early: complete the current round and evaluate what was answered."""
    iv = await _get_iv(iid, user)
    if iv["status"] in ("completed", "evaluating"):
        return await _to_out(iv)
    idx = iv["current_round"]
    upd = {"status": "evaluating"}
    for r in iv["rounds"]:
        if r["index"] == idx and r["status"] == "active":
            upd.update({f"rounds.{idx}.status": "completed", f"rounds.{idx}.completed_at": now(), f"rounds.{idx}.evaluating": True})
    await db.interviews.update_one({"id": iid}, {"$set": upd})
    if f"rounds.{idx}.evaluating" in upd:
        _spawn(_evaluate_round(iid, idx))
    _spawn(_finalize(iid))
    return await _to_out(await _get_iv(iid, user))


@router.post("/interviews/{iid}/finalize", response_model=InterviewOut)
async def refinalize(iid: str, user: dict = Depends(require_ai)):
    iv = await _get_iv(iid, user)
    if iv["status"] == "failed":
        await db.interviews.update_one({"id": iid}, {"$set": {"status": "evaluating"}})
        _spawn(_finalize(iid))
    return await _to_out(await _get_iv(iid, user))


# ---------------- review / retry / recordings ----------------
def _resp_out(r: dict) -> ResponseOut:
    return ResponseOut(**{k: r.get(k) for k in ResponseOut.model_fields if k not in ("has_audio",) and r.get(k) is not None},
                       has_audio=bool(r.get("audio_path") and os.path.exists(r["audio_path"])))


@router.get("/interviews/{iid}/responses", response_model=list[ResponseOut])
async def list_responses(iid: str, user: dict = Depends(current_user)):
    await _get_iv(iid, user)
    rs = await db.responses.find({"interview_id": iid, "user_id": user["id"]}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return [_resp_out(r) for r in rs]


async def _get_resp(rid: str, user: dict) -> dict:
    r = await db.responses.find_one({"id": rid, "user_id": user["id"]}, {"_id": 0})
    if not r:
        raise HTTPException(status_code=404, detail="Response not found")
    return r


@router.post("/responses/{rid}/coach", response_model=Evaluation)
async def coach_feedback(rid: str, user: dict = Depends(require_ai)):
    r = await _get_resp(rid, user)
    if r.get("evaluation"):
        return Evaluation(**r["evaluation"])
    iv = await db.interviews.find_one({"id": r["interview_id"]}, {"_id": 0})
    seed = await db.questions.find_one({"id": r.get("seed_question_id") or ""}, {"_id": 0})
    res = await evaluate_responses(_ctx_line(iv), [{"id": rid, "question": r["question"], "transcript": r["transcript"],
                                                     "metrics": audio_metrics_line(r), "seed": seed}])
    await _apply_evals(res.get("answers", []), {rid: r})
    r = await _get_resp(rid, user)
    if not r.get("evaluation"):
        raise HTTPException(status_code=502, detail="Could not evaluate answer")
    return Evaluation(**r["evaluation"])


@router.post("/responses/{rid}/retry", response_model=RetryResult)
async def retry_answer(rid: str, body: AnswerIn, user: dict = Depends(require_ai)):
    r = await _get_resp(rid, user)
    ans = await process_answer(body.audio_b64, body.mime, body.text)
    if not ans["transcript"]:
        raise HTTPException(status_code=422, detail="We couldn't hear an answer — please try again")
    iv = await db.interviews.find_one({"id": r["interview_id"]}, {"_id": 0})
    seed = await db.questions.find_one({"id": r.get("seed_question_id") or ""}, {"_id": 0})
    res = await evaluate_responses(_ctx_line(iv) + " This is a practice retry of an earlier answer.",
                                   [{"id": "retry", "question": r["question"], "transcript": ans["transcript"],
                                     "metrics": audio_metrics_line(ans), "seed": seed}])
    a = (res.get("answers") or [{}])[0]
    rr = RetryResult(transcript=ans["transcript"], technical_score=float(a.get("technical_score") or 0),
                     communication_score=float(a.get("communication_score") or 0), improve=a.get("improve", []),
                     did_well=a.get("did_well", []), wpm=ans["wpm"], created_at=now())
    await db.responses.update_one({"id": rid}, {"$push": {"retries": rr.model_dump()}})
    return rr


@router.get("/responses/{rid}/audio", response_model=AudioOut)
async def get_audio(rid: str, user: dict = Depends(current_user)):
    r = await _get_resp(rid, user)
    p = r.get("audio_path")
    if not p or not os.path.exists(p):
        raise HTTPException(status_code=404, detail="No recording for this answer")
    with open(p, "rb") as f:
        return AudioOut(audio_b64=base64.b64encode(f.read()).decode(), mime=r.get("audio_mime") or "audio/webm")


@router.delete("/interviews/{iid}/recordings", response_model=OkOut)
async def delete_recordings(iid: str, user: dict = Depends(current_user)):
    await _get_iv(iid, user)
    async for r in db.responses.find({"interview_id": iid, "user_id": user["id"]}, {"audio_path": 1, "id": 1}):
        delete_audio(r.get("audio_path"))
    await db.responses.update_many({"interview_id": iid, "user_id": user["id"]}, {"$set": {"audio_path": None}})
    return OkOut()
