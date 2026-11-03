import ReportAi from "@/components/ReportAi";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Mic, MicOff, Camera, CameraOff, Captions, CaptionsOff, Volume2, VolumeX, Settings, PhoneOff, Pause, Play,
  RotateCcw, Send, Wifi, Circle, Loader2, Keyboard, GraduationCap, X, LogOut,
} from "lucide-react";
import { toast } from "sonner";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { useSpeaker, useVoiceRecorder } from "@/lib/audio";
import type { AvatarConfig, Evaluation, Interview, InterviewerReply, RespondOut, Turn } from "@/lib/types";
import { fmtDuration } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { EvidencePanel, InterviewerStage } from "@/components/interview/Stage";
import { readPrefs } from "@/pages/Lobby";

type Phase = "waiting" | "joining" | "speaking" | "listening" | "processing" | "paused" | "ended";

function CtrlButton({ on, onClick, label, children, danger, testId }: { on?: boolean; onClick: () => void; label: string; children: React.ReactNode; danger?: boolean; testId: string }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      data-testid={testId}
      className={cn(
        "flex size-11 items-center justify-center rounded-full transition-[background-color,transform] duration-150 active:scale-95 sm:size-12",
        danger ? "bg-red-600 text-white hover:bg-red-500" : on === false ? "bg-red-500/15 text-red-300 hover:bg-red-500/25" : "bg-white/[0.08] text-white hover:bg-white/[0.14]",
      )}
    >
      {children}
    </button>
  );
}

export default function Room() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: me } = useMe();
  const { data: iv } = useQuery({ queryKey: ["interview", id], queryFn: () => apiGet<Interview>(`/interviews/${id}`) });
  const { data: avatarCfg } = useQuery({ queryKey: ["avatar-config"], queryFn: () => apiGet<AvatarConfig>("/avatar/config") });
  const prefs = readPrefs();
  const [camOn, setCamOn] = useState(prefs.cam);
  const [micOn, setMicOn] = useState(prefs.mic);
  const [captionsOn, setCaptionsOn] = useState(prefs.captions);
  const [mediaOk, setMediaOk] = useState<boolean | null>(null);
  const [phase, setPhase] = useState<Phase>("waiting");
  const [lines, setLines] = useState<Turn[]>([]);
  const [showEvidence, setShowEvidence] = useState(false);
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [endOpen, setEndOpen] = useState(false);
  const [coachEval, setCoachEval] = useState<Evaluation | null>(null);
  const [coachLoading, setCoachLoading] = useState(false);
  const [coachOpen, setCoachOpen] = useState(false);
  const [joinedAt] = useState(() => Date.now());
  const [now, setNow] = useState(Date.now());
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const startedRef = useRef(false);
  const pausedRef = useRef(false);
  const micOnRef = useRef(micOn);
  const typingRef = useRef(typing);
  typingRef.current = typing;
  const phaseRef = useRef<Phase>(phase);
  phaseRef.current = phase;
  micOnRef.current = micOn;
  const speaker = useSpeaker();
  const round = iv ? iv.rounds[iv.current_round] : undefined;
  const isLastRound = iv ? iv.current_round === iv.rounds.length - 1 : false;

  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  // Camera + mic for the candidate tile and speech capture.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: { echoCancellation: true, noiseSuppression: true } });
        if (cancelled) return s.getTracks().forEach((t) => t.stop());
        streamRef.current = s;
        if (videoRef.current) videoRef.current.srcObject = s;
        setMediaOk(true);
      } catch {
        try {
          const s = await navigator.mediaDevices.getUserMedia({ audio: true });
          if (cancelled) return s.getTracks().forEach((t) => t.stop());
          streamRef.current = s;
          setMediaOk(true);
          setCamOn(false);
        } catch {
          if (!cancelled) {
            setMediaOk(false);
            setTyping(true);
          }
        }
      }
    })();
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  useEffect(() => {
    streamRef.current?.getVideoTracks().forEach((t) => (t.enabled = camOn));
  }, [camOn, mediaOk]);
  useEffect(() => {
    streamRef.current?.getAudioTracks().forEach((t) => (t.enabled = micOn));
  }, [micOn, mediaOk]);

  const respond = useMutation({
    mutationFn: (body: { audio_b64?: string; mime?: string; text?: string }) => apiPost<RespondOut>(`/interviews/${id}/respond`, body),
  });

  const recorder = useVoiceRecorder((a) => {
    if (a.seconds < 0.8) return listen();
    submitAnswer({ audio_b64: a.b64, mime: a.mime });
  });

  const listen = useCallback(() => {
    if (pausedRef.current) return setPhase("paused");
    setPhase("listening");
    if (streamRef.current && micOnRef.current && !typingRef.current) {
      recorder.start(streamRef.current).catch(() => {
        setTyping(true);
        toast("Microphone unavailable — you can type your answer instead.");
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleReply = useCallback(
    async (reply: InterviewerReply) => {
      if (!round) return;
      setLines((l) => (l.some((x) => x.id === reply.turn.id) ? l : [...l, reply.turn]));
      if (reply.show_evidence) setShowEvidence(true);
      setPhase("speaking");
      await speaker.speak(reply.turn.text, round.persona.id);
      if (reply.round_complete) {
        setPhase("ended");
        return;
      }
      listen();
    },
    [listen, round, speaker],
  );

  const submitAnswer = (body: { audio_b64?: string; mime?: string; text?: string }) => {
    setPhase("processing");
    respond.mutate(body, {
      onSuccess: (res) => {
        if (res.empty || !res.candidate || !res.interviewer) {
          toast("Sorry, I didn't quite catch that.", { description: "Please answer again." });
          return listen();
        }
        setLines((l) => [...l, res.candidate as Turn]);
        if (iv?.coach_mode && res.candidate.response_id) {
          setCoachEval(null);
          setCoachLoading(true);
          apiPost<Evaluation>(`/responses/${res.candidate.response_id}/coach`)
            .then(setCoachEval)
            .catch(() => toast.error("Coach feedback unavailable for this answer."))
            .finally(() => setCoachLoading(false));
        }
        void handleReply(res.interviewer);
      },
      onError: (e) => {
        const msg = e instanceof ApiError && e.status === 502 ? "The interviewer had a connection issue." : "Something went wrong.";
        toast.error(msg, { description: "Please repeat your answer." });
        listen();
      },
    });
  };

  // Natural join sequence.
  const start = useMutation({ mutationFn: (idx: number) => apiPost<InterviewerReply>(`/interviews/${id}/rounds/${idx}/start`) });
  useEffect(() => {
    if (!iv || !round || startedRef.current) return;
    if (iv.status === "completed" || iv.status === "evaluating") {
      nav(`/interview/${id}/report`, { replace: true });
      return;
    }
    startedRef.current = true;
    apiGet<Turn[]>(`/interviews/${id}/turns`)
      .then((ts) => setLines(ts.filter((t) => t.round_index === round.index)))
      .catch(() => undefined);
    if (round.evidence_shown) setShowEvidence(true);
    const t = window.setTimeout(() => {
      setPhase("joining");
      toast(`${round.persona.name} joined the meeting`, { duration: 2500 });
      start.mutate(round.index, {
        onSuccess: (reply) => void handleReply(reply),
        onError: () => toast.error("Couldn't connect to the interviewer. Please rejoin."),
      });
    }, 2200);
    return () => {
      clearTimeout(t);
      startedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [iv?.id, round?.index]);

  const complete = useMutation({
    mutationFn: () => apiPost<Interview>(`/interviews/${id}/rounds/${round?.index}/complete`),
    onSuccess: (data) => {
      qc.setQueryData(["interview", id], data);
      qc.invalidateQueries({ queryKey: ["interviews"] });
      nav(isLastRound ? `/interview/${id}/report` : `/interview/${id}/waiting`);
    },
    onError: () => toast.error("Couldn't leave the meeting cleanly. Try again."),
  });

  const endEarly = useMutation({
    mutationFn: () => apiPost<Interview>(`/interviews/${id}/end`),
    onSuccess: (data) => {
      speaker.stop();
      recorder.cancel();
      qc.setQueryData(["interview", id], data);
      qc.invalidateQueries({ queryKey: ["interviews"] });
      nav(`/interview/${id}/report`);
    },
  });

  const toggleMic = () => {
    const next = !micOn;
    setMicOn(next);
    if (!next) recorder.cancel();
    else if (phaseRef.current === "listening" && !typing) setTimeout(() => listen(), 50);
  };

  const togglePause = () => {
    if (pausedRef.current) {
      pausedRef.current = false;
      listen();
    } else {
      pausedRef.current = true;
      recorder.cancel();
      speaker.stop();
      setPhase("paused");
    }
  };

  const retryAnswer = async () => {
    recorder.cancel();
    speaker.stop();
    try {
      const reply = await apiPost<InterviewerReply>(`/interviews/${id}/undo-last`);
      setLines((l) => {
        const idx = l.findIndex((x) => x.id === reply.turn.id);
        return idx >= 0 ? l.slice(0, idx) : l;
      });
      setCoachEval(null);
      pausedRef.current = false;
      void handleReply(reply);
    } catch (e) {
      toast.error(e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? "Nothing to retry") : "Nothing to retry");
    }
  };

  const sendTyped = () => {
    if (!typed.trim() || phase !== "listening") return;
    recorder.cancel();
    const text = typed.trim();
    setTyped("");
    submitAnswer({ text });
  };

  if (!iv || !round) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#05080F]" data-testid="room-loading">
        <Loader2 className="size-6 animate-spin text-sky-400" />
      </div>
    );
  }

  const lastInterviewer = [...lines].reverse().find((l) => l.speaker === "interviewer");
  const lastCandidate = lines.length && lines[lines.length - 1].speaker === "candidate" ? lines[lines.length - 1] : null;
  const evidenceVisible = showEvidence && round.scenario;
  const statusText: Record<Phase, string> = {
    waiting: "Waiting for interviewer…",
    joining: `${round.persona.name} is joining…`,
    speaking: `${round.persona.name.split(" ")[0]} is speaking`,
    listening: recorder.state === "speaking" ? "Listening…" : typing ? "Your turn — type your answer" : micOn ? "Your turn — speak when ready" : "Your mic is muted",
    processing: "…",
    paused: "Paused",
    ended: "Round complete",
  };

  return (
    <div className="flex h-[100dvh] flex-col bg-[#05080F] text-white" data-testid="interview-room">
      {/* Top bar */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-white/[0.06] px-4 py-2.5 text-xs sm:px-6">
        <div className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-red-500 anim-live-dot" />
          <span className="font-mono text-slate-300" data-testid="meeting-timer">{fmtDuration((now - joinedAt) / 1000)}</span>
        </div>
        <span className="font-medium text-white" data-testid="room-company">{iv.company.name}</span>
        <span className="hidden text-slate-400 sm:inline" data-testid="room-position">{iv.position}</span>
        <span className="rounded-md border border-white/10 px-1.5 py-0.5 font-mono text-[10px] tracking-wider text-slate-300" data-testid="room-round">
          ROUND {round.index + 1}/{iv.rounds.length} · {round.label.toUpperCase()}
        </span>
        <span className="hidden text-slate-400 md:inline" data-testid="room-interviewer">
          {round.persona.name} · {round.persona.title}
        </span>
        <ReportAi interviewId={iv.id} className="ml-1" />
        <div className="ml-auto flex items-center gap-3 text-slate-400">
          {iv.coach_mode && (
            <span className="flex items-center gap-1 rounded-md bg-sky-500/10 px-1.5 py-0.5 text-sky-300" data-testid="room-coach-badge">
              <GraduationCap className="size-3" /> Coach Mode
            </span>
          )}
          {iv.record_audio && (
            <span className="flex items-center gap-1 text-red-300" data-testid="room-recording-indicator">
              <Circle className="size-2.5 fill-red-400" /> Audio saved
            </span>
          )}
          <span className="flex items-center gap-1" data-testid="room-connection-status">
            <Wifi className="size-3.5 text-emerald-400" /> Stable
          </span>
        </div>
      </div>

      {/* Stage */}
      <div className="relative flex min-h-0 flex-1 gap-3 p-3 sm:p-4">
        <div className={cn("relative min-h-0 flex-1", evidenceVisible && "hidden md:block md:flex-[1.1]")}>
          {phase === "waiting" ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 rounded-2xl bg-[#070B12]" data-testid="room-waiting-state">
              <Loader2 className="size-6 animate-spin text-slate-500" />
              <div className="text-sm text-slate-400">Waiting for interviewer…</div>
              <div className="text-xs text-slate-600">{round.persona.name} will join shortly</div>
            </div>
          ) : (
            <InterviewerStage
              persona={round.persona}
              speaking={speaker.speaking && phase === "speaking"}
              level={speaker.level}
              listening={phase === "listening"}
              thinking={phase === "processing" || phase === "joining"}
            />
          )}
          {captionsOn && phase !== "waiting" && (
            <div className="pointer-events-none absolute inset-x-4 bottom-20 flex justify-center sm:bottom-24" data-testid="captions-overlay">
              <div className="max-w-3xl rounded-lg bg-black/70 px-4 py-2.5 text-center text-sm leading-relaxed backdrop-blur-md sm:text-base">
                {lastCandidate && phase === "processing" ? (
                  <span className="text-slate-300" data-testid="caption-candidate">
                    <span className="text-sky-300">You: </span>
                    {lastCandidate.text}
                  </span>
                ) : lastInterviewer ? (
                  <span data-testid="caption-interviewer">
                    <span className="text-sky-300">{round.persona.name.split(" ")[0]}: </span>
                    {lastInterviewer.text}
                  </span>
                ) : (
                  <span className="text-slate-400">…</span>
                )}
              </div>
            </div>
          )}
        </div>

        {evidenceVisible && round.scenario && (
          <div className="min-h-0 flex-1 md:max-w-[46%]">
            <EvidencePanel scenario={round.scenario} />
          </div>
        )}

        {/* Candidate PIP */}
        <div
          className={cn(
            "absolute top-5 right-5 z-10 aspect-video w-32 overflow-hidden rounded-xl border bg-[#0B111E] shadow-2xl sm:top-6 sm:right-6 sm:w-56",
            recorder.state === "speaking" ? "border-emerald-400/70" : "border-white/10",
            evidenceVisible && "top-auto right-5 bottom-24 sm:bottom-28",
          )}
          data-testid="candidate-pip"
        >
          <video ref={videoRef} autoPlay muted playsInline className={cn("h-full w-full -scale-x-100 object-cover", !camOn && "invisible")} />
          {!camOn && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="flex size-10 items-center justify-center rounded-full bg-white/10 font-heading text-white">{me?.name?.[0]}</div>
            </div>
          )}
          <div className="absolute bottom-1.5 left-1.5 flex items-center gap-1 rounded bg-black/60 px-1.5 py-0.5 text-[10px]">
            {micOn && mediaOk ? <Mic className="size-2.5 text-emerald-300" /> : <MicOff className="size-2.5 text-red-300" />}
            You
          </div>
          {phase === "listening" && micOn && mediaOk && (
            <div className="absolute right-1.5 bottom-1.5 h-1 w-10 overflow-hidden rounded-full bg-white/10">
              <div className="h-full bg-emerald-400" style={{ width: `${recorder.level * 100}%`, transition: "width 90ms linear" }} />
            </div>
          )}
        </div>

        {/* Coach panel */}
        {iv.coach_mode && coachOpen && (
          <div className="absolute top-4 left-4 z-20 max-h-[70%] w-[min(380px,calc(100%-2rem))] overflow-y-auto rounded-xl border border-sky-500/20 bg-[#0B111E]/95 p-4 text-sm shadow-2xl backdrop-blur-xl" data-testid="coach-panel">
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 font-medium text-sky-300">
                <GraduationCap className="size-4" /> Coach feedback
              </span>
              <button onClick={() => setCoachOpen(false)} data-testid="coach-panel-close" aria-label="Close coach">
                <X className="size-4 text-slate-400" />
              </button>
            </div>
            {coachLoading ? (
              <div className="flex items-center gap-2 text-slate-400"><Loader2 className="size-3.5 animate-spin" /> Analyzing your last answer…</div>
            ) : coachEval ? (
              <div className="space-y-3">
                <div className="flex gap-4">
                  <div><div className="text-[10px] uppercase text-slate-500">Technical</div><div className="font-heading text-xl" data-testid="coach-technical-score">{Math.round(coachEval.technical_score)}</div></div>
                  <div><div className="text-[10px] uppercase text-slate-500">Communication</div><div className="font-heading text-xl" data-testid="coach-communication-score">{Math.round(coachEval.communication_score)}</div></div>
                </div>
                {coachEval.improve.length > 0 && (
                  <ul className="list-disc space-y-1 pl-4 text-slate-300">{coachEval.improve.slice(0, 3).map((x) => <li key={x}>{x}</li>)}</ul>
                )}
                {coachEval.grammar.slice(0, 2).map((g) => (
                  <div key={g.said} className="rounded-md bg-white/[0.03] p-2 text-xs">
                    <div className="text-red-300/80 line-through">{g.said}</div>
                    <div className="text-emerald-300">{g.better}</div>
                  </div>
                ))}
                {coachEval.stronger_answer && (
                  <div className="rounded-md border border-white/5 bg-white/[0.02] p-2 text-xs text-slate-300">
                    <div className="mb-1 text-[10px] uppercase text-slate-500">Stronger version</div>
                    {coachEval.stronger_answer}
                  </div>
                )}
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={() => speaker.speak(coachEval.stronger_answer)} data-testid="coach-listen-stronger">
                    <Volume2 /> Hear it
                  </Button>
                  <Button size="sm" variant="secondary" onClick={retryAnswer} data-testid="coach-retry-answer">
                    <RotateCcw /> Try again
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-slate-400">Answer a question to get feedback.</div>
            )}
          </div>
        )}
      </div>

      {/* Status + typed input */}
      <div className="flex flex-col items-center gap-2 px-4">
        <div className="flex items-center gap-2 text-xs text-slate-400" data-testid="room-status">
          {phase === "listening" && !typing && micOn && <span className={cn("size-2 rounded-full", recorder.state === "speaking" ? "bg-emerald-400 anim-live-dot" : "bg-slate-500")} />}
          {(phase === "processing" || phase === "joining") && <Loader2 className="size-3 animate-spin" />}
          {statusText[phase]}
          {phase === "listening" && recorder.state === "speaking" && (
            <button className="ml-2 rounded-md border border-white/10 px-2 py-0.5 text-[11px] text-slate-300 hover:bg-white/5" onClick={() => recorder.stop()} data-testid="finish-answer-button">
              I'm done
            </button>
          )}
        </div>
        {typing && phase !== "ended" && (
          <div className="flex w-full max-w-2xl items-end gap-2" data-testid="typed-answer-bar">
            <Textarea
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendTyped();
                }
              }}
              placeholder={phase === "listening" ? "Type your answer and press Enter…" : "Wait for the interviewer to finish…"}
              className="max-h-28 min-h-11 resize-none bg-white/[0.04]"
              data-testid="typed-answer-input"
            />
            <Button size="icon-lg" onClick={sendTyped} disabled={phase !== "listening" || !typed.trim()} data-testid="typed-answer-send">
              <Send />
            </Button>
          </div>
        )}
        {phase === "ended" && (
          <div className="flex flex-col items-center gap-2 py-1 anim-fade-up" data-testid="round-ended-actions">
            <div className="text-sm text-slate-300">
              {round.persona.name.split(" ")[0]} has wrapped up {isLastRound ? "the final round" : "this round"}.
            </div>
            <Button onClick={() => complete.mutate()} disabled={complete.isPending} data-testid="leave-round-button">
              {complete.isPending ? <Loader2 className="animate-spin" /> : <LogOut />} {isLastRound ? "Leave meeting & see results" : "Leave meeting"}
            </Button>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-2 px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))] sm:gap-3">
        <CtrlButton on={micOn && mediaOk !== false} onClick={toggleMic} label={micOn ? "Mute microphone" : "Unmute microphone"} testId="control-mic">
          {micOn && mediaOk !== false ? <Mic className="size-5" /> : <MicOff className="size-5" />}
        </CtrlButton>
        <CtrlButton on={camOn} onClick={() => setCamOn((c) => !c)} label={camOn ? "Turn camera off" : "Turn camera on"} testId="control-camera">
          {camOn ? <Camera className="size-5" /> : <CameraOff className="size-5" />}
        </CtrlButton>
        <CtrlButton onClick={() => setCaptionsOn((c) => !c)} label="Toggle captions" testId="control-captions">
          {captionsOn ? <Captions className="size-5" /> : <CaptionsOff className="size-5 text-slate-400" />}
        </CtrlButton>
        <CtrlButton on={!speaker.muted} onClick={() => speaker.setMuted(!speaker.muted)} label="Toggle interviewer audio" testId="control-audio">
          {speaker.muted ? <VolumeX className="size-5" /> : <Volume2 className="size-5" />}
        </CtrlButton>
        {iv.coach_mode && (
          <>
            <CtrlButton onClick={togglePause} label={phase === "paused" ? "Resume" : "Pause"} testId="control-pause">
              {phase === "paused" ? <Play className="size-5" /> : <Pause className="size-5" />}
            </CtrlButton>
            <CtrlButton onClick={() => setCoachOpen((o) => !o)} label="Coach feedback" testId="control-coach">
              <GraduationCap className="size-5" />
            </CtrlButton>
          </>
        )}
        <CtrlButton onClick={() => setSettingsOpen(true)} label="Settings" testId="control-settings">
          <Settings className="size-5" />
        </CtrlButton>
        <CtrlButton danger onClick={() => setEndOpen(true)} label="End interview" testId="control-end-interview">
          <PhoneOff className="size-5" />
        </CtrlButton>
      </div>

      <Sheet open={settingsOpen} onOpenChange={setSettingsOpen}>
        <SheetContent className="w-[340px] bg-[#0B111E]">
          <SheetHeader>
            <SheetTitle className="font-heading text-white">Meeting settings</SheetTitle>
          </SheetHeader>
          <div className="space-y-5 px-4 text-sm">
            <div className="space-y-2">
              <div className="text-xs uppercase tracking-wider text-slate-500">Answer input</div>
              <Button
                variant="secondary"
                className="w-full justify-start"
                onClick={() => {
                  const next = !typing;
                  setTyping(next);
                  if (next) recorder.cancel();
                  else if (phaseRef.current === "listening") setTimeout(() => listen(), 50);
                  setSettingsOpen(false);
                }}
                disabled={mediaOk === false}
                data-testid="settings-toggle-typing"
              >
                <Keyboard /> {typing ? "Switch to voice answers" : "Type answers instead"}
              </Button>
              <p className="text-xs text-slate-500">Voice is detected automatically: start speaking after the interviewer finishes, and pause for about two seconds when you're done.</p>
            </div>
            <div className="space-y-2" data-testid="settings-privacy">
              <div className="text-xs uppercase tracking-wider text-slate-500">Privacy</div>
              <p className="text-xs text-slate-400">Camera: {camOn ? "on (local preview only, never recorded)" : "off"}.</p>
              <p className="text-xs text-slate-400">Microphone: captured only while it's your turn to answer.</p>
              <p className="text-xs text-slate-400">Answer audio: {iv.record_audio ? "saved for your review — delete anytime from the report." : "not saved."}</p>
            </div>
            <div className="space-y-2" data-testid="settings-avatar-provider">
              <div className="text-xs uppercase tracking-wider text-slate-500">Interviewer video</div>
              <p className="text-xs text-slate-400">
                {avatarCfg?.live_avatar_available
                  ? "Live avatar provider connected."
                  : "Portrait mode: professional portrait with voice-driven speaking and listening animation. A live photorealistic avatar provider is not connected, so there is no lip-sync."}
              </p>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      <Dialog open={endOpen} onOpenChange={setEndOpen}>
        <DialogContent className="bg-[#0B111E]">
          <DialogHeader>
            <DialogTitle className="font-heading">End the interview now?</DialogTitle>
            <DialogDescription>Remaining rounds will be skipped. We'll evaluate the answers you've given so far and prepare your report.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setEndOpen(false)} data-testid="end-dialog-cancel">
              Stay in meeting
            </Button>
            <Button variant="destructive" onClick={() => endEarly.mutate()} disabled={endEarly.isPending} data-testid="end-dialog-confirm">
              {endEarly.isPending && <Loader2 className="animate-spin" />} End interview
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
