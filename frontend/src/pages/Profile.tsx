import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { ApiError, apiDelete, apiPost, apiPut } from "@/lib/api";
import { blobToBase64 } from "@/lib/audio";
import { useMe } from "@/lib/auth";
import { handleUpgradeError } from "@/lib/billing";
import { useNavigate } from "react-router-dom";
import type { User } from "@/lib/types";
import { EXPERIENCE, POSITIONS } from "@/lib/constants";
import AppShell, { PageHeader } from "@/components/AppShell";
import { Eyebrow, Panel, PositionOptions } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DeleteAccountPanel, SubscriptionPanel } from "@/pages/Account";

function ResumeCard({ me, onSummary }: { me: User; onSummary: (s: string) => void }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const nav = useNavigate();
  const upload = useMutation({
    mutationFn: async (f: File) => apiPost<User>("/auth/resume", { filename: f.name, pdf_b64: await blobToBase64(f) }),
    onSuccess: (u) => {
      qc.setQueryData(["me"], u);
      onSummary(u.resume_summary);
      toast.success("Resume added", { description: "Your recruiter will now ask about your real jobs and certifications." });
    },
    onError: (e) => handleUpgradeError(e, nav) || toast.error(e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? "Upload failed") : "Upload failed"),
  });
  const remove = useMutation({
    mutationFn: () => apiDelete<User>("/auth/resume"),
    onSuccess: (u) => {
      qc.setQueryData(["me"], u);
      onSummary("");
      toast.success("Resume removed");
    },
  });
  return (
    <Panel className="max-w-2xl space-y-3" data-testid="resume-card">
      <Eyebrow>Resume (PDF)</Eyebrow>
      {me.resume_filename ? (
        <div className="flex items-center gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] p-3">
          <FileText className="size-5 text-sky-400" />
          <span className="flex-1 truncate text-sm text-white" data-testid="resume-filename">{me.resume_filename}</span>
          <Button size="sm" variant="ghost" onClick={() => remove.mutate()} disabled={remove.isPending} data-testid="resume-remove-button"><Trash2 /> Remove</Button>
        </div>
      ) : (
        <p className="text-sm text-slate-400">Upload your resume and interviewers will ask about your actual roles, employers, certifications and projects.</p>
      )}
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        data-testid="resume-file-input"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) upload.mutate(f);
          e.target.value = "";
        }}
      />
      <Button variant="secondary" onClick={() => input.current?.click()} disabled={upload.isPending} data-testid="resume-upload-button">
        {upload.isPending ? <Loader2 className="animate-spin" /> : <Upload />} {upload.isPending ? "Reading your resume…" : me.resume_filename ? "Replace resume" : "Upload PDF resume"}
      </Button>
      <p className="text-xs text-slate-500">PDF up to 5 MB. Only the facts written in your resume are used — interviewers never invent experience. Stored privately on your account.</p>
    </Panel>
  );
}

function ProfileForm({ me }: { me: User }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ name: me.name, target_role: me.target_role || POSITIONS[0], experience_level: me.experience_level || EXPERIENCE[1], resume_summary: me.resume_summary });
  const save = useMutation({
    mutationFn: () => apiPut<User>("/auth/profile", f),
    onSuccess: (u) => {
      qc.setQueryData(["me"], { ...u, resume_filename: me.resume_filename });
      toast.success("Profile saved");
    },
  });
  return (
    <div className="space-y-6">
      <ResumeCard me={me} onSummary={(s) => setF((x) => ({ ...x, resume_summary: s }))} />
      <Panel className="max-w-2xl space-y-4">
        <div className="space-y-1.5"><Label>Full name</Label><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="profile-name-input" /></div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5"><Label>Target role</Label>
            <Select value={f.target_role} onValueChange={(v: string) => setF({ ...f, target_role: v })}><SelectTrigger className="w-full" data-testid="profile-role-select"><SelectValue /></SelectTrigger><SelectContent><PositionOptions /></SelectContent></Select></div>
          <div className="space-y-1.5"><Label>Experience</Label>
            <Select value={f.experience_level} onValueChange={(v: string) => setF({ ...f, experience_level: v })}><SelectTrigger className="w-full" data-testid="profile-experience-select"><SelectValue /></SelectTrigger><SelectContent>{EXPERIENCE.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent></Select></div>
        </div>
        <div className="space-y-1.5">
          <Label>Background summary {me.resume_filename && <span className="text-xs text-sky-400">(from your resume — edit if anything's off)</span>}</Label>
          <Textarea value={f.resume_summary} onChange={(e) => setF({ ...f, resume_summary: e.target.value })} className="min-h-44" placeholder="e.g. 2 years IT help desk, CompTIA Security+, home lab with Splunk and Sysmon, transitioning into SOC…" data-testid="profile-resume-input" />
          <p className="text-xs text-slate-500">This is exactly what interviewers know about you.</p>
        </div>
        <Button onClick={() => save.mutate()} disabled={save.isPending} data-testid="profile-save-button">{save.isPending && <Loader2 className="animate-spin" />} Save profile</Button>
      </Panel>
    </div>
  );
}

export default function Profile() {
  const { data: me } = useMe();
  return (
    <AppShell>
      <PageHeader eyebrow="Candidate profile" title="Your profile" desc={me?.email} />
      {me && (
        <div className="space-y-6">
          <SubscriptionPanel />
          <ProfileForm key={me.resume_filename + me.id} me={me} />
          {me.role !== "admin" && <DeleteAccountPanel />}
        </div>
      )}
    </AppShell>
  );
}
