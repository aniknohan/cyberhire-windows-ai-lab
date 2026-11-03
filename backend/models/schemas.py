"""Pydantic v2 models — mirrored by hand in frontend/src/lib/types.ts. Change both together."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- auth / profile ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1)
    target_role: str = "SOC Analyst L1"
    experience_level: str = "Entry Level"


class GoogleSessionIn(BaseModel):
    session_id: str = Field(min_length=4, max_length=500)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    target_role: str = ""
    experience_level: str = ""
    resume_summary: str = ""
    resume_filename: str = ""


class ResumeUploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    pdf_b64: str = Field(min_length=10)


class ProfileUpdate(BaseModel):
    name: str
    target_role: str
    experience_level: str
    resume_summary: str = ""


# ---------- shared content ----------
class Persona(BaseModel):
    id: str
    name: str
    title: str
    round_type: Literal["hr", "technical", "scenario", "manager"]
    image_url: str
    voice: str
    personality: str
    speaking_style: str
    focus: list[str] = []
    voice_style: str = ""


class ProcessNode(BaseModel):
    depth: int
    name: str
    pid: int = 0
    cmd: str = ""


class Scenario(BaseModel):
    id: str
    title: str
    severity: str
    source: str
    environments: list[str] = []
    level: str = "L1+"
    fields: list[list[str]] = []
    process_tree: list[ProcessNode] = []
    raw_log: str = ""
    mitre: list[str] = []
    interviewer_notes: str = ""


class PublicScenario(BaseModel):
    """What the candidate sees: no MITRE answers, no interviewer notes."""
    id: str
    title: str
    severity: str
    source: str
    fields: list[list[str]] = []
    process_tree: list[ProcessNode] = []
    raw_log: str = ""


class Question(BaseModel):
    id: str
    text: str
    primary_role: str = "SOC Analyst"
    soc_level: str = "All"
    round: Literal["hr", "technical", "scenario", "manager"]
    difficulty: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    category: str
    subcategory: str = ""
    expected_concepts: list[str] = []
    rubric: str = ""
    follow_ups: list[str] = []
    scenario_capable: bool = False
    communication_skills: list[str] = []
    technical_depth: int = 3
    est_answer_seconds: int = 90


class QuestionIn(BaseModel):
    id: Optional[str] = None
    text: str = Field(min_length=5)
    primary_role: str = "SOC Analyst"
    soc_level: str = "All"
    round: Literal["hr", "technical", "scenario", "manager"]
    difficulty: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    category: str = "General"
    subcategory: str = ""
    expected_concepts: list[str] = []
    rubric: str = ""
    follow_ups: list[str] = []
    scenario_capable: bool = False
    communication_skills: list[str] = []
    technical_depth: int = 3
    est_answer_seconds: int = 90


class QuestionWithStats(Question):
    times_asked: int = 0
    avg_technical: Optional[float] = None


class ImportResult(BaseModel):
    inserted: int
    updated: int


class CompanyTemplate(BaseModel):
    id: str
    industry: str
    environment: str
    name_parts: list[list[str]]
    stack_pool: list[str]
    focus: list[str]
    employees: list[int]


class AvatarProvider(BaseModel):
    id: str
    name: str
    status: str


class AvatarConfig(BaseModel):
    active_provider: str
    live_avatar_available: bool
    lip_sync: bool
    providers: list[AvatarProvider]


# ---------- interview ----------
class InterviewCreate(BaseModel):
    position: str
    experience: str
    difficulty: str
    environment: str = "random"
    mode: Literal["full", "quick", "communication", "technical"] = "full"
    coach_mode: bool = False
    focus: Optional[Literal["Splunk", "Wireshark", "Nmap", "Active Directory", "Python"]] = None


class Company(BaseModel):
    name: str
    industry: str
    environment: str
    employees: int
    stack: list[str]
    focus: list[str]
    soc_description: str
    position_title: str


class RoundOut(BaseModel):
    index: int
    type: Literal["hr", "technical", "scenario", "manager"]
    label: str
    persona: Persona
    status: Literal["pending", "active", "completed"]
    target_questions: int
    main_questions: int = 0
    evidence_shown: bool = False
    scenario: Optional[PublicScenario] = None
    score: Optional[float] = None
    summary: str = ""
    evaluating: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Turn(BaseModel):
    id: str
    round_index: int
    speaker: Literal["interviewer", "candidate"]
    text: str
    response_id: Optional[str] = None
    created_at: datetime


class PriorityItem(BaseModel):
    title: str
    why: str
    module: str


class RoundScore(BaseModel):
    round: str
    label: str
    score: Optional[float] = None


class Report(BaseModel):
    decision: str
    job_readiness: float
    communication: float
    decision_reasoning: str
    strengths: list[str]
    weaknesses: list[str]
    hiring_summary: str
    priorities: list[PriorityItem]
    round_scores: list[RoundScore]
    tech_dims: dict[str, float] = {}
    comm_dims: dict[str, float] = {}
    technical_avg: Optional[float] = None
    technical_communication_avg: Optional[float] = None
    filler_total: int = 0
    filler_top: Optional[str] = None
    filler_breakdown: dict[str, int] = {}
    avg_wpm: Optional[float] = None
    clarity_avg: Optional[float] = None


class InterviewOut(BaseModel):
    id: str
    position: str
    soc_level: str
    experience: str
    difficulty: str
    environment: str
    mode: str
    coach_mode: bool
    focus: Optional[str] = None
    record_audio: bool
    company: Company
    rounds: list[RoundOut]
    current_round: int
    status: Literal["setup", "in_progress", "evaluating", "completed", "failed"]
    created_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0
    report: Optional[Report] = None


class InterviewSummary(BaseModel):
    id: str
    position: str
    soc_level: str
    company_name: str
    industry: str
    mode: str
    status: str
    created_at: datetime
    decision: Optional[str] = None
    job_readiness: Optional[float] = None
    communication: Optional[float] = None
    interviewers: list[str] = []
    duration_seconds: float = 0


class JoinIn(BaseModel):
    record_audio: bool = False


class InterviewerReply(BaseModel):
    turn: Turn
    round_complete: bool
    show_evidence: bool


class RespondIn(BaseModel):
    audio_b64: Optional[str] = None
    mime: str = "audio/webm"
    text: Optional[str] = None


class RespondOut(BaseModel):
    candidate: Optional[Turn] = None
    interviewer: Optional[InterviewerReply] = None
    empty: bool = False


class GrammarFix(BaseModel):
    said: str
    better: str
    why: str = ""


class Evaluation(BaseModel):
    evaluable: bool = True
    topic: str = ""
    technical_score: float = 0
    communication_score: float = 0
    technical_communication: float = 0
    comm_dims: dict[str, float] = {}
    grammar: list[GrammarFix] = []
    pronunciation_note: str = ""
    fluency_note: str = ""
    confidence_note: str = ""
    structure_note: str = ""
    conciseness_note: str = ""
    did_well: list[str] = []
    improve: list[str] = []
    stronger_answer: str = ""
    missing_concepts: list[str] = []
    study_topics: list[str] = []


class RetryResult(BaseModel):
    transcript: str
    technical_score: float
    communication_score: float
    improve: list[str] = []
    did_well: list[str] = []
    wpm: Optional[float] = None
    created_at: datetime


class ResponseOut(BaseModel):
    id: str
    round_index: int
    round_type: str
    interviewer_name: str
    question: str
    transcript: str
    duration: float = 0
    wpm: Optional[float] = None
    fillers: dict[str, int] = {}
    clarity: Optional[float] = None
    long_pauses: int = 0
    has_audio: bool = False
    evaluation: Optional[Evaluation] = None
    retries: list[RetryResult] = []


class AudioOut(BaseModel):
    audio_b64: str
    mime: str


class TTSIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    persona_id: Optional[str] = None
    voice: Optional[str] = None


class TTSOut(BaseModel):
    audio_b64: str


class AnswerIn(BaseModel):
    audio_b64: Optional[str] = None
    mime: str = "audio/webm"
    text: Optional[str] = None


class OkOut(BaseModel):
    ok: bool = True


# ---------- practice ----------
class PracticeIn(BaseModel):
    module: str
    prompt: str
    audience: Optional[str] = None
    audio_b64: Optional[str] = None
    mime: str = "audio/webm"
    text: Optional[str] = None


class PracticeResult(BaseModel):
    id: str
    module: str
    prompt: str
    transcript: str
    duration: float = 0
    wpm: Optional[float] = None
    fillers: dict[str, int] = {}
    clarity: Optional[float] = None
    technical_score: Optional[float] = None
    communication_score: float = 0
    pronunciation_score: Optional[float] = None
    previous_score: Optional[float] = None
    feedback: Optional[Evaluation] = None
    star: dict[str, bool] = {}
    created_at: datetime


# ---------- stats ----------
class ProgressPoint(BaseModel):
    n: int
    interview_id: str
    date: datetime
    technical: Optional[float] = None
    communication: Optional[float] = None
    decision: Optional[str] = None


class SkillScore(BaseModel):
    name: str
    score: float


class Overview(BaseModel):
    total_interviews: int
    interview_hours: float
    hiring_rate: Optional[float] = None
    questions_answered: int
    job_readiness: Optional[float] = None
    communication_readiness: Optional[float] = None
    technical_score: Optional[float] = None
    communication_score: Optional[float] = None
    strongest: list[SkillScore]
    weakest: list[SkillScore]
    recent: list[InterviewSummary]
    progress: list[ProgressPoint]
    priorities: list[PriorityItem] = []


class DimStat(BaseModel):
    key: str
    label: str
    current: Optional[float] = None
    average: Optional[float] = None
    series: list[Optional[float]] = []


class CommStats(BaseModel):
    dims: list[DimStat]
    labels: list[str]
    filler_series: list[float]
    wpm_series: list[Optional[float]]
    filler_breakdown: dict[str, int]
    practice_count: int


class TopicStat(BaseModel):
    topic: str
    current: Optional[float] = None
    trend: Optional[float] = None
    answered: int = 0
    weak: bool = False
    missing: list[str] = []


class TechStats(BaseModel):
    topics: list[TopicStat]


# ---------- weakness drills ----------
class DrillCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    why: str = ""
    module: str = "technical_explanation"


class DrillItem(BaseModel):
    module: str
    prompt: str
    audience: Optional[str] = None
    focus: str = ""
    minutes: float = 2


class DrillResult(BaseModel):
    index: int
    practice_id: str
    communication_score: float
    technical_score: Optional[float] = None
    pronunciation_score: Optional[float] = None


class Drill(BaseModel):
    id: str
    title: str
    why: str = ""
    minutes: int = 10
    items: list[DrillItem]
    results: list[DrillResult] = []
    completed: bool = False
    created_at: datetime


class DrillAnswerIn(BaseModel):
    audio_b64: Optional[str] = None
    mime: str = "audio/webm"
    text: Optional[str] = None


# ---------- billing ----------
class BillingStatus(BaseModel):
    mode: Literal["web", "desktop"] = "desktop"
    plan: Literal["none", "trial", "pro", "expired"]
    trial_available: bool = False
    interviews_used: int = 0
    interviews_limit: Optional[int] = None
    is_pro: bool
    has_access: bool
    on_trial: bool
    trial_until: Optional[datetime] = None
    trial_days: int
    pro_until: Optional[datetime] = None
    provider: Optional[str] = None
    interval: Optional[Literal["month", "year"]] = None
    cancel_at_period_end: bool = False
    monthly_price_label: str
    yearly_price_label: str
    stripe_enabled: bool
    play_enabled: bool = False
    play_product_id: str = ""
    paypal_enabled: bool


class CheckoutIn(BaseModel):
    origin_url: str = Field(min_length=8, max_length=300)
    interval: Literal["month", "year"] = "month"


class PlayVerifyIn(BaseModel):
    purchase_token: str = Field(min_length=10, max_length=1000)
    product_id: Optional[str] = None


class PortalOut(BaseModel):
    url: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class DeleteAccountIn(BaseModel):
    password: Optional[str] = None
    confirm: str = Field(min_length=1, max_length=20)


class PublicConfig(BaseModel):
    mode: Literal["web", "desktop"]
    trial_days: int
    monthly_price_label: str
    yearly_price_label: str
    google_login: bool = False
    support_email: str = ""
    web_checkout: bool = False
    play_store_url: str = ""


class CheckoutOut(BaseModel):
    checkout_url: str
    session_id: str


class PaymentStatusOut(BaseModel):
    session_id: str
    status: str
    payment_status: str
