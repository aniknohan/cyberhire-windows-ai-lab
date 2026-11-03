"""Content & admin: personas, question bank (CRUD + import + performance), scenarios, company templates,
avatar provider config and the TTS voice endpoint."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from lib import avatar
from routers.billing import require_ai
from lib.auth import admin_user, current_user
from lib.db import db
from lib.voice import synthesize
from models.schemas import (AvatarConfig, CompanyTemplate, ImportResult, OkOut, Persona, Question, QuestionIn,
                            QuestionWithStats, Scenario, TTSIn, TTSOut)

router = APIRouter(tags=["content"])


@router.post("/voice/tts", response_model=TTSOut)
async def tts(body: TTSIn, user: dict = Depends(require_ai)):
    voice, style = body.voice or "alloy", ""
    if body.persona_id:
        p = await db.personas.find_one({"id": body.persona_id}, {"_id": 0})
        if p:
            voice, style = p["voice"], p.get("voice_style", "")
    return TTSOut(audio_b64=await synthesize(body.text, voice, style))


@router.get("/avatar/config", response_model=AvatarConfig)
async def avatar_config(user: dict = Depends(current_user)):
    return AvatarConfig(**avatar.config())


# ---------- personas ----------
@router.get("/personas", response_model=list[Persona])
async def list_personas(user: dict = Depends(current_user)):
    return [Persona(**p) for p in await db.personas.find({}, {"_id": 0}).to_list(200)]


@router.post("/admin/personas", response_model=Persona)
async def upsert_persona(body: Persona, admin: dict = Depends(admin_user)):
    data = body.model_dump()
    if not data["id"]:
        data["id"] = f"p-{uuid.uuid4().hex[:8]}"
    await db.personas.update_one({"id": data["id"]}, {"$set": data}, upsert=True)
    return Persona(**data)


@router.delete("/admin/personas/{pid}", response_model=OkOut)
async def delete_persona(pid: str, admin: dict = Depends(admin_user)):
    p = await db.personas.find_one({"id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Persona not found")
    if await db.personas.count_documents({"round_type": p["round_type"]}) <= 1:
        raise HTTPException(status_code=400, detail="Each round type needs at least one interviewer")
    await db.personas.delete_one({"id": pid})
    return OkOut()


# ---------- questions ----------
@router.get("/admin/questions", response_model=list[QuestionWithStats])
async def list_questions(admin: dict = Depends(admin_user)):
    qs = await db.questions.find({}, {"_id": 0}).sort("id", 1).to_list(5000)
    agg = await db.responses.aggregate([
        {"$match": {"seed_question_id": {"$ne": None}}},
        {"$group": {"_id": "$seed_question_id", "n": {"$sum": 1}, "avg": {"$avg": "$evaluation.technical_score"}}},
    ]).to_list(5000)
    stats = {a["_id"]: a for a in agg}
    return [QuestionWithStats(**q, times_asked=stats.get(q["id"], {}).get("n", 0),
                              avg_technical=round(stats[q["id"]]["avg"], 1) if stats.get(q["id"], {}).get("avg") is not None else None)
            for q in qs]


async def _upsert_question(q: QuestionIn) -> bool:
    data = q.model_dump()
    is_new = not data.get("id")
    if is_new:
        data["id"] = f"q-{uuid.uuid4().hex[:8]}"
    res = await db.questions.update_one({"id": data["id"]}, {"$set": data, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}}, upsert=True)
    return res.upserted_id is not None


@router.post("/admin/questions", response_model=Question)
async def create_question(body: QuestionIn, admin: dict = Depends(admin_user)):
    body.id = None
    await _upsert_question(body)
    doc = await db.questions.find_one({"text": body.text}, {"_id": 0}, sort=[("created_at", -1)])
    return Question(**doc)


@router.put("/admin/questions/{qid}", response_model=Question)
async def update_question(qid: str, body: QuestionIn, admin: dict = Depends(admin_user)):
    if not await db.questions.find_one({"id": qid}):
        raise HTTPException(status_code=404, detail="Question not found")
    body.id = qid
    await _upsert_question(body)
    return Question(**await db.questions.find_one({"id": qid}, {"_id": 0}))


@router.delete("/admin/questions/{qid}", response_model=OkOut)
async def delete_question(qid: str, admin: dict = Depends(admin_user)):
    res = await db.questions.delete_one({"id": qid})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Question not found")
    return OkOut()


@router.post("/admin/questions/import", response_model=ImportResult)
async def import_questions(body: list[QuestionIn], admin: dict = Depends(admin_user)):
    inserted = updated = 0
    for q in body:
        if await _upsert_question(q):
            inserted += 1
        else:
            updated += 1
    return ImportResult(inserted=inserted, updated=updated)


# ---------- scenarios ----------
@router.get("/admin/scenarios", response_model=list[Scenario])
async def list_scenarios(admin: dict = Depends(admin_user)):
    return [Scenario(**s) for s in await db.scenarios.find({}, {"_id": 0}).to_list(500)]


@router.post("/admin/scenarios", response_model=Scenario)
async def upsert_scenario(body: Scenario, admin: dict = Depends(admin_user)):
    data = body.model_dump()
    if not data["id"]:
        data["id"] = f"sc-{uuid.uuid4().hex[:8]}"
    await db.scenarios.update_one({"id": data["id"]}, {"$set": data}, upsert=True)
    return Scenario(**data)


@router.delete("/admin/scenarios/{sid}", response_model=OkOut)
async def delete_scenario(sid: str, admin: dict = Depends(admin_user)):
    if await db.scenarios.count_documents({}) <= 1:
        raise HTTPException(status_code=400, detail="At least one scenario is required")
    await db.scenarios.delete_one({"id": sid})
    return OkOut()


# ---------- company templates ----------
@router.get("/admin/companies", response_model=list[CompanyTemplate])
async def list_companies(admin: dict = Depends(admin_user)):
    return [CompanyTemplate(**c) for c in await db.company_templates.find({}, {"_id": 0}).to_list(200)]


@router.post("/admin/companies", response_model=CompanyTemplate)
async def upsert_company(body: CompanyTemplate, admin: dict = Depends(admin_user)):
    data = body.model_dump()
    if not data["id"]:
        data["id"] = f"ct-{uuid.uuid4().hex[:8]}"
    if len(data["name_parts"]) != 2 or not all(data["name_parts"]) or len(data["employees"]) != 2:
        raise HTTPException(status_code=422, detail="name_parts needs 2 non-empty lists and employees needs [min, max]")
    await db.company_templates.update_one({"id": data["id"]}, {"$set": data}, upsert=True)
    return CompanyTemplate(**data)


@router.delete("/admin/companies/{cid}", response_model=OkOut)
async def delete_company(cid: str, admin: dict = Depends(admin_user)):
    if await db.company_templates.count_documents({}) <= 1:
        raise HTTPException(status_code=400, detail="At least one template is required")
    await db.company_templates.delete_one({"id": cid})
    return OkOut()
