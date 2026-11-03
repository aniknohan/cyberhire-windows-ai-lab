import { useState } from "react";
import { Flag, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { apiPost } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

/** "Report an AI response": lets anyone flag offensive or harmful AI output without leaving the app. */
export default function ReportAi({ interviewId, className }: { interviewId?: string; className?: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    setBusy(true);
    try {
      await apiPost("/reports", { text, interview_id: interviewId ?? null, page: window.location.pathname });
      toast.success("Thanks. Your report was sent and will be reviewed.");
      setOpen(false);
      setText("");
    } catch {
      toast.error("Couldn't send the report. Please try again.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn("rounded-lg p-2 text-slate-400 transition-colors hover:bg-white/[0.04] hover:text-white", className)}
        aria-label="Report an AI response"
        title="Report an AI response"
        data-testid="report-ai-button"
      >
        <Flag className="size-4" />
      </button>
      {open && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true" data-testid="report-ai-dialog">
          <div className="w-full max-w-md space-y-4 rounded-2xl border border-white/10 bg-[#0B111E] p-5 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-heading text-lg font-semibold text-white">Report an AI response</div>
                <p className="mt-1 text-sm text-slate-400">Tell us what the interviewer or feedback said that was offensive, harmful or wrong. We review every report.</p>
              </div>
              <button type="button" onClick={() => setOpen(false)} className="text-slate-400 hover:text-white" aria-label="Close"><X className="size-4" /></button>
            </div>
            <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="What happened? You can paste the message here." className="min-h-28" data-testid="report-ai-text" />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={send} disabled={busy || text.trim().length < 3} data-testid="report-ai-send">{busy && <Loader2 className="animate-spin" />} Send report</Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
