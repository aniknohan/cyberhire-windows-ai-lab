// Hand-written mirrors of backend/models/schemas.py — keep in sync.
export type RoundType = "hr" | "technical" | "scenario" | "manager";

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  target_role: string;
  experience_level: string;
  resume_summary: string;
  resume_filename: string;
}

export interface Persona {
  id: string;
  name: string;
  title: string;
  round_type: RoundType;
  image_url: string;
  voice: string;
  personality: string;
  speaking_style: string;
  focus: string[];
  voice_style: string;
}

export interface ProcessNode {
  depth: number;
  name: string;
  pid: number;
  cmd: string;
}

export interface PublicScenario {
  id: string;
  title: string;
  severity: string;
  source: string;
  fields: string[][];
  process_tree: ProcessNode[];
  raw_log: string;
}

export interface Scenario extends PublicScenario {
  environments: string[];
  level: string;
  mitre: string[];
  interviewer_notes: string;
}

export interface Question {
  id: string;
  text: string;
  primary_role: string;
  soc_level: string;
  round: RoundType;
  difficulty: "beginner" | "intermediate" | "advanced";
  category: string;
  subcategory: string;
  expected_concepts: string[];
  rubric: string;
  follow_ups: string[];
  scenario_capable: boolean;
  communication_skills: string[];
  technical_depth: number;
  est_answer_seconds: number;
}

export type QuestionIn = Omit<Question, "id"> & { id?: string | null };

export interface QuestionWithStats extends Question {
  times_asked: number;
  avg_technical: number | null;
}

export interface ImportResult {
  inserted: number;
  updated: number;
}

export interface CompanyTemplate {
  id: string;
  industry: string;
  environment: string;
  name_parts: string[][];
  stack_pool: string[];
  focus: string[];
  employees: number[];
}

export interface AvatarConfig {
  active_provider: string;
  live_avatar_available: boolean;
  lip_sync: boolean;
  providers: { id: string; name: string; status: string }[];
}

export interface InterviewCreate {
  position: string;
  experience: string;
  difficulty: string;
  environment: string;
  mode: "full" | "quick" | "communication" | "technical";
  coach_mode: boolean;
  focus: FocusTopic | null;
}

export interface Company {
  name: string;
  industry: string;
  environment: string;
  employees: number;
  stack: string[];
  focus: string[];
  soc_description: string;
  position_title: string;
}

export interface RoundOut {
  index: number;
  type: RoundType;
  label: string;
  persona: Persona;
  status: "pending" | "active" | "completed";
  target_questions: number;
  main_questions: number;
  evidence_shown: boolean;
  scenario: PublicScenario | null;
  score: number | null;
  summary: string;
  evaluating: boolean;
  started_at: string | null;
  completed_at: string | null;
}

export interface Turn {
  id: string;
  round_index: number;
  speaker: "interviewer" | "candidate";
  text: string;
  response_id: string | null;
  created_at: string;
}

export interface PriorityItem {
  title: string;
  why: string;
  module: string;
}

export interface Report {
  decision: string;
  job_readiness: number;
  communication: number;
  decision_reasoning: string;
  strengths: string[];
  weaknesses: string[];
  hiring_summary: string;
  priorities: PriorityItem[];
  round_scores: { round: string; label: string; score: number | null }[];
  tech_dims: Record<string, number>;
  comm_dims: Record<string, number>;
  technical_avg: number | null;
  technical_communication_avg: number | null;
  filler_total: number;
  filler_top: string | null;
  filler_breakdown: Record<string, number>;
  avg_wpm: number | null;
  clarity_avg: number | null;
}

export interface Interview {
  id: string;
  position: string;
  soc_level: string;
  experience: string;
  difficulty: string;
  environment: string;
  mode: string;
  coach_mode: boolean;
  focus: string | null;
  record_audio: boolean;
  company: Company;
  rounds: RoundOut[];
  current_round: number;
  status: "setup" | "in_progress" | "evaluating" | "completed" | "failed";
  created_at: string;
  completed_at: string | null;
  duration_seconds: number;
  report: Report | null;
}

export interface InterviewSummary {
  id: string;
  position: string;
  soc_level: string;
  company_name: string;
  industry: string;
  mode: string;
  status: string;
  created_at: string;
  decision: string | null;
  job_readiness: number | null;
  communication: number | null;
  interviewers: string[];
  duration_seconds: number;
}

export interface InterviewerReply {
  turn: Turn;
  round_complete: boolean;
  show_evidence: boolean;
}

export interface RespondOut {
  candidate: Turn | null;
  interviewer: InterviewerReply | null;
  empty: boolean;
}

export interface GrammarFix {
  said: string;
  better: string;
  why: string;
}

export interface Evaluation {
  evaluable: boolean;
  topic: string;
  technical_score: number;
  communication_score: number;
  technical_communication: number;
  comm_dims: Record<string, number>;
  grammar: GrammarFix[];
  pronunciation_note: string;
  fluency_note: string;
  confidence_note: string;
  structure_note: string;
  conciseness_note: string;
  did_well: string[];
  improve: string[];
  stronger_answer: string;
  missing_concepts: string[];
  study_topics: string[];
}

export interface RetryResult {
  transcript: string;
  technical_score: number;
  communication_score: number;
  improve: string[];
  did_well: string[];
  wpm: number | null;
  created_at: string;
}

export interface ResponseOut {
  id: string;
  round_index: number;
  round_type: string;
  interviewer_name: string;
  question: string;
  transcript: string;
  duration: number;
  wpm: number | null;
  fillers: Record<string, number>;
  clarity: number | null;
  long_pauses: number;
  has_audio: boolean;
  evaluation: Evaluation | null;
  retries: RetryResult[];
}

export interface AudioOut {
  audio_b64: string;
  mime: string;
}

export interface TTSOut {
  audio_b64: string;
}

export interface OkOut {
  ok: boolean;
}

export interface PracticeResult {
  id: string;
  module: string;
  prompt: string;
  transcript: string;
  duration: number;
  wpm: number | null;
  fillers: Record<string, number>;
  clarity: number | null;
  technical_score: number | null;
  communication_score: number;
  pronunciation_score: number | null;
  previous_score: number | null;
  feedback: Evaluation | null;
  star: Record<string, boolean>;
  created_at: string;
}

export interface ProgressPoint {
  n: number;
  interview_id: string;
  date: string;
  technical: number | null;
  communication: number | null;
  decision: string | null;
}

export interface SkillScore {
  name: string;
  score: number;
}

export interface Overview {
  total_interviews: number;
  interview_hours: number;
  hiring_rate: number | null;
  questions_answered: number;
  job_readiness: number | null;
  communication_readiness: number | null;
  technical_score: number | null;
  communication_score: number | null;
  strongest: SkillScore[];
  weakest: SkillScore[];
  recent: InterviewSummary[];
  progress: ProgressPoint[];
  priorities: PriorityItem[];
}

export interface DimStat {
  key: string;
  label: string;
  current: number | null;
  average: number | null;
  series: (number | null)[];
}

export interface CommStats {
  dims: DimStat[];
  labels: string[];
  filler_series: number[];
  wpm_series: (number | null)[];
  filler_breakdown: Record<string, number>;
  practice_count: number;
}

export interface TopicStat {
  topic: string;
  current: number | null;
  trend: number | null;
  answered: number;
  weak: boolean;
  missing: string[];
}

export interface TechStats {
  topics: TopicStat[];
}

export interface DrillItem {
  module: string;
  prompt: string;
  audience: string | null;
  focus: string;
  minutes: number;
}

export interface DrillResult {
  index: number;
  practice_id: string;
  communication_score: number;
  technical_score: number | null;
  pronunciation_score: number | null;
}

export interface Drill {
  id: string;
  title: string;
  why: string;
  minutes: number;
  items: DrillItem[];
  results: DrillResult[];
  completed: boolean;
  created_at: string;
}

export interface PublicConfig {
  mode: "web" | "desktop";
  trial_days: number;
  monthly_price_label: string;
  yearly_price_label: string;
  google_login: boolean;
  support_email: string;
}

export interface PortalOut {
  url: string;
}

export interface BillingStatus {
  mode: "web" | "desktop";
  plan: "none" | "trial" | "pro" | "expired";
  trial_available: boolean;
  interviews_used: number;
  interviews_limit: number | null;
  is_pro: boolean;
  has_access: boolean;
  on_trial: boolean;
  trial_until: string | null;
  trial_days: number;
  pro_until: string | null;
  provider: string | null;
  interval: "month" | "year" | null;
  cancel_at_period_end: boolean;
  monthly_price_label: string;
  yearly_price_label: string;
  stripe_enabled: boolean;
  paypal_enabled: boolean;
}

export interface CheckoutOut {
  checkout_url: string;
  session_id: string;
}

export interface PaymentStatusOut {
  session_id: string;
  status: string;
  payment_status: string;
}

export type FocusTopic = "Splunk" | "Wireshark" | "Nmap" | "Active Directory" | "Python";
